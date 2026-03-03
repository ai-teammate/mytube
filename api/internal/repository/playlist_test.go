package repository_test

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── playlistQuerier stub ─────────────────────────────────────────────────────

// playlistQuerier is a stub PlaylistQuerier that allows tests to control
// query results without a real database connection.
type playlistQuerier struct {
	t *testing.T

	// QueryRow results
	queryRowSummary    *repository.PlaylistSummary
	queryRowOwnerID    string // for ownership checks
	queryRowErr        bool

	// QueryContext results for lists
	summaries   []repository.PlaylistSummary
	videoItems  []repository.PlaylistVideoItem
	queryErr    error

	// ExecContext results
	execErr  error
	rowsAff  int64

	// Call tracking: which method was called most recently
	lastQuerySQL string
	callCount    int
}

func (q *playlistQuerier) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	return emptyDB().BeginTx(ctx, opts)
}

// QueryRowContext returns a pre-configured single row result.
func (q *playlistQuerier) QueryRowContext(_ context.Context, sqlStr string, _ ...any) *sql.Row {
	q.lastQuerySQL = sqlStr
	q.callCount++

	if q.queryRowErr {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1 WHERE 1=0")
	}

	// When checking ownership (returns owner_id only).
	if q.queryRowOwnerID != "" && q.queryRowSummary == nil {
		dsn := registerResults(q.t, []fakeQueryResult{
			{
				columns: []string{"owner_id"},
				rows:    [][]driver.Value{{q.queryRowOwnerID}},
			},
		})
		db, _ := sql.Open("fakedb", dsn)
		return db.QueryRowContext(context.Background(), "SELECT 1")
	}

	if q.queryRowSummary == nil {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1 WHERE 1=0")
	}

	// Playlist summary row: id, title, owner_username, created_at
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"id", "title", "username", "created_at"},
			rows: [][]driver.Value{{
				q.queryRowSummary.ID,
				q.queryRowSummary.Title,
				q.queryRowSummary.OwnerUsername,
				q.queryRowSummary.CreatedAt,
			}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryRowContext(context.Background(), "SELECT 1")
}

func (q *playlistQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	if q.execErr != nil {
		return nil, q.execErr
	}
	return rowsAffectedResult{n: q.rowsAff}, nil
}

func (q *playlistQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	if q.queryErr != nil {
		return nil, q.queryErr
	}

	// If videoItems is set, return video rows.
	if q.videoItems != nil {
		var rows [][]driver.Value
		for _, v := range q.videoItems {
			thumbVal := driver.Value(nil)
			if v.ThumbnailURL != nil {
				thumbVal = *v.ThumbnailURL
			}
			rows = append(rows, []driver.Value{v.ID, v.Title, thumbVal, int64(v.Position)})
		}
		dsn := registerResults(q.t, []fakeQueryResult{
			{
				columns: []string{"id", "title", "thumbnail_url", "position"},
				rows:    rows,
			},
		})
		db, _ := sql.Open("fakedb", dsn)
		return db.QueryContext(context.Background(), "SELECT 1")
	}

	if len(q.summaries) == 0 {
		return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
	}

	var rows [][]driver.Value
	for _, p := range q.summaries {
		rows = append(rows, []driver.Value{p.ID, p.Title, p.OwnerUsername, p.CreatedAt})
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"id", "title", "username", "created_at"},
			rows:    rows,
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryContext(context.Background(), "SELECT 1")
}

// ─── Create tests ─────────────────────────────────────────────────────────────

func TestPlaylistCreate_Success(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	expected := &repository.PlaylistSummary{
		ID:            "pl-1",
		Title:         "Favourites",
		OwnerUsername: "alice",
		CreatedAt:     now,
	}
	q := &playlistQuerier{t: t, queryRowSummary: expected}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.Create(context.Background(), "user-1", "Favourites")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil playlist")
	}
	if got.ID != "pl-1" {
		t.Errorf("ID: got %q, want pl-1", got.ID)
	}
	if got.Title != "Favourites" {
		t.Errorf("Title: got %q, want Favourites", got.Title)
	}
	if got.OwnerUsername != "alice" {
		t.Errorf("OwnerUsername: got %q, want alice", got.OwnerUsername)
	}
}

func TestPlaylistCreate_QueryRowError_ReturnsError(t *testing.T) {
	q := &playlistQuerier{t: t, queryRowErr: true}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.Create(context.Background(), "user-1", "Playlist")
	if got != nil {
		t.Errorf("expected nil on error")
	}
	if err == nil {
		t.Errorf("expected error")
	}
}

// ─── GetByID tests ────────────────────────────────────────────────────────────

// multiQueryPlaylistQuerier supports two sequential QueryRowContext calls
// (first for the playlist header, second is unused) plus one QueryContext call.
type multiQueryPlaylistQuerier struct {
	t            *testing.T
	summary      *repository.PlaylistSummary
	videos       []repository.PlaylistVideoItem
	firstRowErr  bool
	videoQueryErr error
	rowCallCount  int
}

func (q *multiQueryPlaylistQuerier) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	return emptyDB().BeginTx(ctx, opts)
}

func (q *multiQueryPlaylistQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	q.rowCallCount++
	if q.firstRowErr || q.summary == nil {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1 WHERE 1=0")
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"id", "title", "username"},
			rows: [][]driver.Value{{q.summary.ID, q.summary.Title, q.summary.OwnerUsername}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryRowContext(context.Background(), "SELECT 1")
}

func (q *multiQueryPlaylistQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	return rowsAffectedResult{n: 1}, nil
}

func (q *multiQueryPlaylistQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	if q.videoQueryErr != nil {
		return nil, q.videoQueryErr
	}
	if len(q.videos) == 0 {
		return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
	}
	var rows [][]driver.Value
	for _, v := range q.videos {
		thumbVal := driver.Value(nil)
		if v.ThumbnailURL != nil {
			thumbVal = *v.ThumbnailURL
		}
		rows = append(rows, []driver.Value{v.ID, v.Title, thumbVal, int64(v.Position)})
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"id", "title", "thumbnail_url", "position"},
			rows:    rows,
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryContext(context.Background(), "SELECT 1")
}

func TestPlaylistGetByID_Found_ReturnsDetail(t *testing.T) {
	thumbURL := "https://cdn.example.com/thumb.jpg"
	summary := &repository.PlaylistSummary{
		ID:            "pl-1",
		Title:         "My List",
		OwnerUsername: "alice",
	}
	videos := []repository.PlaylistVideoItem{
		{ID: "v-1", Title: "Video 1", ThumbnailURL: &thumbURL, Position: 1},
		{ID: "v-2", Title: "Video 2", ThumbnailURL: nil, Position: 2},
	}
	q := &multiQueryPlaylistQuerier{t: t, summary: summary, videos: videos}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.GetByID(context.Background(), "pl-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil detail")
	}
	if got.Title != "My List" {
		t.Errorf("Title: got %q", got.Title)
	}
	if got.OwnerUsername != "alice" {
		t.Errorf("OwnerUsername: got %q", got.OwnerUsername)
	}
	if len(got.Videos) != 2 {
		t.Errorf("Videos: expected 2, got %d", len(got.Videos))
	}
	if got.Videos[0].ID != "v-1" {
		t.Errorf("Videos[0].ID: got %q", got.Videos[0].ID)
	}
	if got.Videos[1].ThumbnailURL != nil {
		t.Errorf("Videos[1].ThumbnailURL: expected nil")
	}
}

func TestPlaylistGetByID_NotFound_ReturnsNil(t *testing.T) {
	q := &multiQueryPlaylistQuerier{t: t, summary: nil}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.GetByID(context.Background(), "missing")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != nil {
		t.Errorf("expected nil, got %+v", got)
	}
}

func TestPlaylistGetByID_VideoQueryError_ReturnsError(t *testing.T) {
	summary := &repository.PlaylistSummary{ID: "pl-1", Title: "T", OwnerUsername: "alice"}
	q := &multiQueryPlaylistQuerier{t: t, summary: summary, videoQueryErr: errors.New("db error")}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.GetByID(context.Background(), "pl-1")
	if got != nil {
		t.Errorf("expected nil on error")
	}
	if err == nil {
		t.Errorf("expected error")
	}
}

func TestPlaylistGetByID_EmptyVideos_ReturnsEmptySlice(t *testing.T) {
	summary := &repository.PlaylistSummary{ID: "pl-1", Title: "Empty", OwnerUsername: "alice"}
	q := &multiQueryPlaylistQuerier{t: t, summary: summary, videos: []repository.PlaylistVideoItem{}}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.GetByID(context.Background(), "pl-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil")
	}
	if got.Videos == nil {
		t.Error("expected non-nil empty slice for Videos")
	}
	if len(got.Videos) != 0 {
		t.Errorf("expected 0 videos, got %d", len(got.Videos))
	}
}

// ─── ListByOwnerID tests ──────────────────────────────────────────────────────

func TestPlaylistListByOwnerID_ReturnsList(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	playlists := []repository.PlaylistSummary{
		{ID: "pl-1", Title: "First", OwnerUsername: "alice", CreatedAt: now},
		{ID: "pl-2", Title: "Second", OwnerUsername: "alice", CreatedAt: now},
	}
	q := &playlistQuerier{t: t, summaries: playlists}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.ListByOwnerID(context.Background(), "user-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Errorf("expected 2 playlists, got %d", len(got))
	}
	if got[0].Title != "First" {
		t.Errorf("got[0].Title: got %q", got[0].Title)
	}
}

func TestPlaylistListByOwnerID_Empty_ReturnsEmptySlice(t *testing.T) {
	q := &playlistQuerier{t: t}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.ListByOwnerID(context.Background(), "user-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Error("expected non-nil empty slice")
	}
	if len(got) != 0 {
		t.Errorf("expected 0, got %d", len(got))
	}
}

func TestPlaylistListByOwnerID_QueryError_ReturnsError(t *testing.T) {
	q := &playlistQuerier{t: t, queryErr: errors.New("db error")}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.ListByOwnerID(context.Background(), "user-1")
	if got != nil {
		t.Errorf("expected nil on error")
	}
	if err == nil {
		t.Errorf("expected error")
	}
}

// ─── ListByOwnerUsername tests ────────────────────────────────────────────────

func TestPlaylistListByOwnerUsername_ReturnsList(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	playlists := []repository.PlaylistSummary{
		{ID: "pl-1", Title: "Alice's List", OwnerUsername: "alice", CreatedAt: now},
	}
	q := &playlistQuerier{t: t, summaries: playlists}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.ListByOwnerUsername(context.Background(), "alice")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 1 {
		t.Errorf("expected 1 playlist, got %d", len(got))
	}
}

func TestPlaylistListByOwnerUsername_QueryError_ReturnsError(t *testing.T) {
	q := &playlistQuerier{t: t, queryErr: errors.New("db error")}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.ListByOwnerUsername(context.Background(), "alice")
	if got != nil {
		t.Errorf("expected nil on error")
	}
	if err == nil {
		t.Errorf("expected error")
	}
}

// ─── UpdateTitle tests ────────────────────────────────────────────────────────

// updateTitleQuerier supports one ExecContext call then one QueryRowContext call.
type updateTitleQuerier struct {
	t           *testing.T
	execErr     error
	rowsAff     int64
	summary     *repository.PlaylistSummary
}

func (q *updateTitleQuerier) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	return emptyDB().BeginTx(ctx, opts)
}

func (q *updateTitleQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.summary == nil {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1 WHERE 1=0")
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"id", "title", "username", "created_at"},
			rows: [][]driver.Value{{
				q.summary.ID, q.summary.Title, q.summary.OwnerUsername, q.summary.CreatedAt,
			}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryRowContext(context.Background(), "SELECT 1")
}

func (q *updateTitleQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	if q.execErr != nil {
		return nil, q.execErr
	}
	return rowsAffectedResult{n: q.rowsAff}, nil
}

func (q *updateTitleQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
}

func TestPlaylistUpdateTitle_Success(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	summary := &repository.PlaylistSummary{ID: "pl-1", Title: "Renamed", OwnerUsername: "alice", CreatedAt: now}
	q := &updateTitleQuerier{t: t, rowsAff: 1, summary: summary}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.UpdateTitle(context.Background(), "pl-1", "user-1", "Renamed")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil")
	}
	if got.Title != "Renamed" {
		t.Errorf("Title: got %q", got.Title)
	}
}

func TestPlaylistUpdateTitle_NotFound_ReturnsNil(t *testing.T) {
	q := &updateTitleQuerier{t: t, rowsAff: 0}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.UpdateTitle(context.Background(), "pl-missing", "user-1", "New")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != nil {
		t.Errorf("expected nil, got %+v", got)
	}
}

func TestPlaylistUpdateTitle_ExecError_ReturnsError(t *testing.T) {
	q := &updateTitleQuerier{t: t, execErr: errors.New("db error")}
	repo := repository.NewPlaylistRepository(q)

	got, err := repo.UpdateTitle(context.Background(), "pl-1", "user-1", "New")
	if got != nil {
		t.Errorf("expected nil on error")
	}
	if err == nil {
		t.Errorf("expected error")
	}
}

// ─── Delete tests ─────────────────────────────────────────────────────────────

// ownershipQuerier handles ownership check (QueryRowContext) then deletion (ExecContext).
type ownershipQuerier struct {
	t           *testing.T
	ownerID     string // if empty, QueryRowContext returns no rows
	noOwnerRow  bool
	execErr     error
	rowsAff     int64
}

func (q *ownershipQuerier) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	return emptyDB().BeginTx(ctx, opts)
}

func (q *ownershipQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.noOwnerRow || q.ownerID == "" {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1 WHERE 1=0")
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"owner_id"},
			rows:    [][]driver.Value{{q.ownerID}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryRowContext(context.Background(), "SELECT 1")
}

func (q *ownershipQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	if q.execErr != nil {
		return nil, q.execErr
	}
	return rowsAffectedResult{n: q.rowsAff}, nil
}

func (q *ownershipQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
}

func TestPlaylistDelete_Success(t *testing.T) {
	q := &ownershipQuerier{t: t, ownerID: "user-1", rowsAff: 1}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.Delete(context.Background(), "pl-1", "user-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Errorf("expected true, got false")
	}
}

func TestPlaylistDelete_NotFound_ReturnsFalse(t *testing.T) {
	q := &ownershipQuerier{t: t, noOwnerRow: true}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.Delete(context.Background(), "pl-missing", "user-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Errorf("expected false")
	}
}

func TestPlaylistDelete_Forbidden_ReturnsErrForbidden(t *testing.T) {
	q := &ownershipQuerier{t: t, ownerID: "user-2"} // owned by someone else
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.Delete(context.Background(), "pl-1", "user-1")
	if ok {
		t.Errorf("expected false")
	}
	if !errors.Is(err, repository.ErrForbidden) {
		t.Errorf("expected ErrForbidden, got %v", err)
	}
}

func TestPlaylistDelete_ExecError_ReturnsError(t *testing.T) {
	q := &ownershipQuerier{t: t, ownerID: "user-1", execErr: errors.New("db error")}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.Delete(context.Background(), "pl-1", "user-1")
	if ok {
		t.Errorf("expected false")
	}
	if err == nil {
		t.Errorf("expected error")
	}
}

// ─── RemoveVideo tests ────────────────────────────────────────────────────────

func TestPlaylistRemoveVideo_Success(t *testing.T) {
	q := &ownershipQuerier{t: t, ownerID: "user-1", rowsAff: 1}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.RemoveVideo(context.Background(), "pl-1", "user-1", "v-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Errorf("expected true, got false")
	}
}

func TestPlaylistRemoveVideo_NotFound_ReturnsFalse(t *testing.T) {
	q := &ownershipQuerier{t: t, noOwnerRow: true}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.RemoveVideo(context.Background(), "pl-missing", "user-1", "v-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Errorf("expected false")
	}
}

func TestPlaylistRemoveVideo_Forbidden_ReturnsErrForbidden(t *testing.T) {
	q := &ownershipQuerier{t: t, ownerID: "user-2"}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.RemoveVideo(context.Background(), "pl-1", "user-1", "v-1")
	if ok {
		t.Errorf("expected false")
	}
	if !errors.Is(err, repository.ErrForbidden) {
		t.Errorf("expected ErrForbidden, got %v", err)
	}
}

func TestPlaylistRemoveVideo_ExecError_ReturnsError(t *testing.T) {
	q := &ownershipQuerier{t: t, ownerID: "user-1", execErr: errors.New("db error")}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.RemoveVideo(context.Background(), "pl-1", "user-1", "v-1")
	if ok {
		t.Errorf("expected false")
	}
	if err == nil {
		t.Errorf("expected error")
	}
}

// ─── AddVideo tests ───────────────────────────────────────────────────────────

// addVideoQuerier handles:
//   1. QueryRowContext for ownership check
//   2. BeginTx → tx.QueryRowContext for position → tx.ExecContext for INSERT
// Since BeginTx returns emptyDB().BeginTx, the tx methods go to fakedb.
// We control ownership via the standard QueryRowContext path.

type addVideoQuerier struct {
	t           *testing.T
	ownerID     string
	noOwnerRow  bool
	beginTxErr  error
}

func (q *addVideoQuerier) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	if q.beginTxErr != nil {
		return nil, q.beginTxErr
	}
	// Use a fakedb with a sequence of:
	//   1. position row (SELECT COALESCE...) → returns 1
	//   2. insert row (INSERT ... ON CONFLICT) → returns nothing (Exec)
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"pos"},
			rows:    [][]driver.Value{{int64(1)}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.BeginTx(ctx, opts)
}

func (q *addVideoQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.noOwnerRow || q.ownerID == "" {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1 WHERE 1=0")
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"owner_id"},
			rows:    [][]driver.Value{{q.ownerID}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryRowContext(context.Background(), "SELECT 1")
}

func (q *addVideoQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	return rowsAffectedResult{n: 1}, nil
}

func (q *addVideoQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
}

func TestPlaylistAddVideo_Success(t *testing.T) {
	q := &addVideoQuerier{t: t, ownerID: "user-1"}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.AddVideo(context.Background(), "pl-1", "user-1", "v-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Errorf("expected true")
	}
}

func TestPlaylistAddVideo_NotFound_ReturnsFalse(t *testing.T) {
	q := &addVideoQuerier{t: t, noOwnerRow: true}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.AddVideo(context.Background(), "pl-missing", "user-1", "v-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Errorf("expected false")
	}
}

func TestPlaylistAddVideo_Forbidden_ReturnsErrForbidden(t *testing.T) {
	q := &addVideoQuerier{t: t, ownerID: "user-2"}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.AddVideo(context.Background(), "pl-1", "user-1", "v-1")
	if ok {
		t.Errorf("expected false")
	}
	if !errors.Is(err, repository.ErrForbidden) {
		t.Errorf("expected ErrForbidden, got %v", err)
	}
}

func TestPlaylistAddVideo_BeginTxError_ReturnsError(t *testing.T) {
	q := &addVideoQuerier{t: t, ownerID: "user-1", beginTxErr: errors.New("tx error")}
	repo := repository.NewPlaylistRepository(q)

	ok, err := repo.AddVideo(context.Background(), "pl-1", "user-1", "v-1")
	if ok {
		t.Errorf("expected false")
	}
	if err == nil {
		t.Errorf("expected error")
	}
}
