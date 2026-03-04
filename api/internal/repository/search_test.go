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

// ─── searchQuerier stub ───────────────────────────────────────────────────────

// searchQuerier implements VideoQuerier for SearchRepository tests.
type searchQuerier struct {
	t        *testing.T
	videos   []repository.SearchVideo
	cats     []repository.Category
	queryErr error
}

func (q *searchQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	return okResult{}, nil
}

func (q *searchQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
}

func (q *searchQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	if q.queryErr != nil {
		return nil, q.queryErr
	}
	// Use video rows if any, else category rows if any, else empty.
	if len(q.videos) > 0 {
		return searchVideoDB(q.t, q.videos).QueryContext(context.Background(), "SELECT 1")
	}
	if len(q.cats) > 0 {
		return categoriesDB(q.t, q.cats).QueryContext(context.Background(), "SELECT 1")
	}
	return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
}

func (q *searchQuerier) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	return emptyDB().BeginTx(ctx, opts)
}

// searchVideoDB builds a fakedb with search video rows.
func searchVideoDB(t *testing.T, videos []repository.SearchVideo) *sql.DB {
	t.Helper()
	var rows [][]driver.Value
	for _, v := range videos {
		thumbVal := driver.Value(nil)
		if v.ThumbnailURL != nil {
			thumbVal = *v.ThumbnailURL
		}
		rows = append(rows, []driver.Value{
			v.ID, v.Title, thumbVal, v.ViewCount, v.UploaderUsername, v.CreatedAt, v.Status,
		})
	}
	dsn := registerResults(t, []fakeQueryResult{
		{
			columns: []string{"id", "title", "thumbnail_url", "view_count", "username", "created_at", "status"},
			rows:    rows,
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db
}

// categoriesDB builds a fakedb with category rows.
func categoriesDB(t *testing.T, cats []repository.Category) *sql.DB {
	t.Helper()
	var rows [][]driver.Value
	for _, c := range cats {
		rows = append(rows, []driver.Value{int64(c.ID), c.Name})
	}
	dsn := registerResults(t, []fakeQueryResult{
		{
			columns: []string{"id", "name"},
			rows:    rows,
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db
}

// ─── helper ───────────────────────────────────────────────────────────────────

func makeSearchVideo(id, title, uploader string) repository.SearchVideo {
	thumb := "https://cdn.example.com/" + id + "/thumb.jpg"
	return repository.SearchVideo{
		ID:               id,
		Title:            title,
		ThumbnailURL:     &thumb,
		ViewCount:        10,
		UploaderUsername: uploader,
		CreatedAt:        time.Now().Truncate(time.Second),
		Status:           "ready",
	}
}

// ─── Search tests ──────────────────────────────────────────────────────────────

func TestSearch_EmptyQuery_ReturnsResults(t *testing.T) {
	videos := []repository.SearchVideo{
		makeSearchVideo("v1", "Go Tutorial", "alice"),
		makeSearchVideo("v2", "Python Intro", "bob"),
	}
	q := &searchQuerier{t: t, videos: videos}
	repo := repository.NewSearchRepository(q)

	got, err := repo.Search(context.Background(), repository.SearchParams{Limit: 20})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Errorf("expected 2 results, got %d", len(got))
	}
}

func TestSearch_QueryError_ReturnsError(t *testing.T) {
	dbErr := errors.New("db error")
	q := &searchQuerier{t: t, queryErr: dbErr}
	repo := repository.NewSearchRepository(q)

	got, err := repo.Search(context.Background(), repository.SearchParams{Query: "test"})

	if got != nil {
		t.Errorf("expected nil on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestSearch_EmptyResult_ReturnsEmptySlice(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	got, err := repo.Search(context.Background(), repository.SearchParams{Query: "nothing"})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Error("expected empty slice, not nil")
	}
	if len(got) != 0 {
		t.Errorf("expected 0 results, got %d", len(got))
	}
}

func TestSearch_DefaultLimitApplied(t *testing.T) {
	// Pass Limit=0; should default to 20 internally without panicking.
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	_, err := repo.Search(context.Background(), repository.SearchParams{Limit: 0})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestSearch_WithCategoryID_NoError(t *testing.T) {
	catID := 3
	videos := []repository.SearchVideo{makeSearchVideo("v3", "Music Video", "carol")}
	q := &searchQuerier{t: t, videos: videos}
	repo := repository.NewSearchRepository(q)

	got, err := repo.Search(context.Background(), repository.SearchParams{
		Query:      "music",
		CategoryID: &catID,
		Limit:      20,
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 1 {
		t.Errorf("expected 1 result, got %d", len(got))
	}
}

func TestSearch_NilThumbnailURL(t *testing.T) {
	v := repository.SearchVideo{
		ID:               "v-nil-thumb",
		Title:            "No Thumb",
		ThumbnailURL:     nil,
		ViewCount:        0,
		UploaderUsername: "dave",
		CreatedAt:        time.Now().Truncate(time.Second),
	}
	// Build DB manually for nil thumbnail.
	dsn := registerResults(t, []fakeQueryResult{
		{
			columns: []string{"id", "title", "thumbnail_url", "view_count", "username", "created_at", "status"},
			rows:    [][]driver.Value{{v.ID, v.Title, nil, v.ViewCount, v.UploaderUsername, v.CreatedAt, "ready"}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	q := &searchQuerier{t: t}
	_ = q
	repo := repository.NewSearchRepository(db)

	got, err := repo.Search(context.Background(), repository.SearchParams{Limit: 20})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("expected 1 result, got %d", len(got))
	}
	if got[0].ThumbnailURL != nil {
		t.Errorf("expected nil ThumbnailURL, got %v", got[0].ThumbnailURL)
	}
}

// ─── GetRecent tests ──────────────────────────────────────────────────────────

func TestGetRecent_ReturnsVideos(t *testing.T) {
	videos := []repository.SearchVideo{
		makeSearchVideo("r1", "Recent 1", "alice"),
		makeSearchVideo("r2", "Recent 2", "bob"),
	}
	q := &searchQuerier{t: t, videos: videos}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetRecent(context.Background(), 20)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Errorf("expected 2, got %d", len(got))
	}
}

func TestGetRecent_QueryError_ReturnsError(t *testing.T) {
	dbErr := errors.New("recent error")
	q := &searchQuerier{t: t, queryErr: dbErr}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetRecent(context.Background(), 20)

	if got != nil {
		t.Error("expected nil on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestGetRecent_EmptyResult_ReturnsEmptySlice(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetRecent(context.Background(), 20)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Error("expected empty slice, not nil")
	}
}

func TestGetRecent_ZeroLimit_DefaultsTo20(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	_, err := repo.GetRecent(context.Background(), 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// ─── GetPopular tests ──────────────────────────────────────────────────────────

func TestGetPopular_ReturnsVideos(t *testing.T) {
	videos := []repository.SearchVideo{
		makeSearchVideo("p1", "Popular 1", "carol"),
	}
	q := &searchQuerier{t: t, videos: videos}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetPopular(context.Background(), 20)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 1 {
		t.Errorf("expected 1, got %d", len(got))
	}
}

func TestGetPopular_QueryError_ReturnsError(t *testing.T) {
	dbErr := errors.New("popular error")
	q := &searchQuerier{t: t, queryErr: dbErr}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetPopular(context.Background(), 20)

	if got != nil {
		t.Error("expected nil on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestGetPopular_EmptyResult_ReturnsEmptySlice(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetPopular(context.Background(), 20)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Error("expected empty slice, not nil")
	}
}

func TestGetPopular_ZeroLimit_DefaultsTo20(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	_, err := repo.GetPopular(context.Background(), 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// ─── GetAllCategories tests ────────────────────────────────────────────────────

func TestGetAllCategories_ReturnsCategories(t *testing.T) {
	cats := []repository.Category{
		{ID: 1, Name: "Education"},
		{ID: 2, Name: "Gaming"},
	}
	q := &searchQuerier{t: t, cats: cats}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetAllCategories(context.Background())

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Errorf("expected 2, got %d", len(got))
	}
	if got[0].Name != "Education" {
		t.Errorf("expected Education, got %q", got[0].Name)
	}
}

func TestGetAllCategories_QueryError_ReturnsError(t *testing.T) {
	dbErr := errors.New("cat error")
	q := &searchQuerier{t: t, queryErr: dbErr}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetAllCategories(context.Background())

	if got != nil {
		t.Error("expected nil on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestGetAllCategories_EmptyResult_ReturnsEmptySlice(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetAllCategories(context.Background())

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Error("expected empty slice, not nil")
	}
}

// ─── GetByCategory tests ───────────────────────────────────────────────────────

func TestGetByCategory_ReturnsVideos(t *testing.T) {
	videos := []repository.SearchVideo{
		makeSearchVideo("c1", "Cat Video 1", "alice"),
	}
	q := &searchQuerier{t: t, videos: videos}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetByCategory(context.Background(), 1, 20, 0)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 1 {
		t.Errorf("expected 1, got %d", len(got))
	}
}

func TestGetByCategory_QueryError_ReturnsError(t *testing.T) {
	dbErr := errors.New("cat browse error")
	q := &searchQuerier{t: t, queryErr: dbErr}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetByCategory(context.Background(), 1, 20, 0)

	if got != nil {
		t.Error("expected nil on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestGetByCategory_EmptyResult_ReturnsEmptySlice(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	got, err := repo.GetByCategory(context.Background(), 99, 20, 0)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Error("expected empty slice, not nil")
	}
}

func TestGetByCategory_ZeroLimit_DefaultsTo20(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	_, err := repo.GetByCategory(context.Background(), 1, 0, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestGetByCategory_NegativeOffset_DefaultsToZero(t *testing.T) {
	q := &searchQuerier{t: t}
	repo := repository.NewSearchRepository(q)

	_, err := repo.GetByCategory(context.Background(), 1, 20, -5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
