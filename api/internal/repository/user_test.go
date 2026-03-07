package repository_test

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"fmt"
	"io"
	"sync/atomic"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── minimal fake SQL driver ──────────────────────────────────────────────────
// Registers a "fakedb" driver that allows tests to return pre-configured rows
// without a real database.

func init() {
	sql.Register("fakedb", &fakeDriver{})
}

// dsnCounter generates unique DSN strings so each test gets a fresh connection.
var dsnCounter int64

func nextDSN() string {
	n := atomic.AddInt64(&dsnCounter, 1)
	return fmt.Sprintf("dsn-%d", n)
}

// resultRegistry maps DSN strings to their configured query results.
var resultRegistry = map[string][]fakeQueryResult{}

type fakeQueryResult struct {
	columns     []string
	rows        [][]driver.Value
	zeroRowsAff bool // if true, Exec returns 0 rows affected instead of 1
}

// registerResults stores results under a unique DSN and returns that DSN.
// It registers a t.Cleanup to delete the entry after the test completes.
func registerResults(t *testing.T, results []fakeQueryResult) string {
	t.Helper()
	dsn := nextDSN()
	resultRegistry[dsn] = results
	t.Cleanup(func() { delete(resultRegistry, dsn) })
	return dsn
}

// ─── driver implementation ────────────────────────────────────────────────────

type fakeDriver struct{}

func (*fakeDriver) Open(name string) (driver.Conn, error) {
	results := resultRegistry[name] // nil if not registered — returns empty sets
	return &fakeConn{results: results}, nil
}

type fakeConn struct {
	results []fakeQueryResult
	pos     int
}

func (c *fakeConn) Prepare(_ string) (driver.Stmt, error) {
	var qr fakeQueryResult
	if c.pos < len(c.results) {
		qr = c.results[c.pos]
		c.pos++
	}
	return &fakeStmt{qr: qr}, nil
}
func (c *fakeConn) Close() error                 { return nil }
func (c *fakeConn) Begin() (driver.Tx, error)    { return &fakeTx{}, nil }

type fakeTx struct{}

func (*fakeTx) Commit() error   { return nil }
func (*fakeTx) Rollback() error { return nil }

type fakeStmt struct{ qr fakeQueryResult }

func (*fakeStmt) Close() error   { return nil }
func (*fakeStmt) NumInput() int  { return -1 }
func (s *fakeStmt) Exec(_ []driver.Value) (driver.Result, error) {
	if s.qr.zeroRowsAff {
		return zeroResult{}, nil
	}
	return fakeDriverResult{}, nil
}
func (s *fakeStmt) Query(_ []driver.Value) (driver.Rows, error) {
	return &fakeRows{cols: s.qr.columns, data: s.qr.rows}, nil
}

type fakeDriverResult struct{}

func (fakeDriverResult) LastInsertId() (int64, error) { return 0, nil }
func (fakeDriverResult) RowsAffected() (int64, error) { return 1, nil }

type zeroResult struct{}

func (zeroResult) LastInsertId() (int64, error) { return 0, nil }
func (zeroResult) RowsAffected() (int64, error) { return 0, nil }

type fakeRows struct {
	cols []string
	data [][]driver.Value
	pos  int
}

func (r *fakeRows) Columns() []string { return r.cols }
func (r *fakeRows) Close() error      { return nil }
func (r *fakeRows) Next(dest []driver.Value) error {
	if r.pos >= len(r.data) {
		return io.EOF
	}
	copy(dest, r.data[r.pos])
	r.pos++
	return nil
}

// ─── helpers ──────────────────────────────────────────────────────────────────

// emptyDB returns a *sql.DB that always gives no rows on SELECT.
func emptyDB() *sql.DB {
	db, _ := sql.Open("fakedb", nextDSN()) // no registered results → empty sets
	return db
}

// userDB returns a *sql.DB whose first QueryRowContext returns the given user.
func userDB(t *testing.T, u *repository.User) *sql.DB {
	t.Helper()
	avatarVal := driver.Value(nil)
	if u.AvatarURL != nil {
		avatarVal = *u.AvatarURL
	}
	dsn := registerResults(t, []fakeQueryResult{
		{
			columns: []string{"id", "firebase_uid", "username", "avatar_url", "created_at"},
			rows:    [][]driver.Value{{u.ID, u.FirebaseUID, u.Username, avatarVal, u.CreatedAt}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db
}

// ─── sql.Result stub ──────────────────────────────────────────────────────────

type okResult struct{}

func (okResult) LastInsertId() (int64, error) { return 0, nil }
func (okResult) RowsAffected() (int64, error) { return 1, nil }

// ─── UserQuerier stubs ────────────────────────────────────────────────────────

// captureQuerier records ExecContext arguments; QueryRowContext delegates to
// an empty fakedb DB (no rows returned).
type captureQuerier struct {
	capturedArgs []any
	execErr      error
}

func (q *captureQuerier) ExecContext(_ context.Context, _ string, args ...any) (sql.Result, error) {
	q.capturedArgs = args
	if q.execErr != nil {
		return nil, q.execErr
	}
	return okResult{}, nil
}

func (q *captureQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
}

func (q *captureQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
}

// rowQuerier returns a fully-populated row from QueryRowContext (for found tests).
type rowQuerier struct {
	t       *testing.T
	user    *repository.User
	execErr error
}

func (q *rowQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	if q.execErr != nil {
		return nil, q.execErr
	}
	return okResult{}, nil
}

func (q *rowQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.user == nil {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
	}
	return userDB(q.t, q.user).QueryRowContext(
		context.Background(),
		"SELECT id, firebase_uid, username, avatar_url, created_at FROM users WHERE firebase_uid = $1",
		q.user.FirebaseUID,
	)
}

func (q *rowQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
}

// ─── Upsert tests ─────────────────────────────────────────────────────────────

func TestUpsert_UsesEmailPrefix(t *testing.T) {
	q := &captureQuerier{}
	repo := repository.NewUserRepository(q)

	_, _ = repo.Upsert(context.Background(), "uid1", "alice@example.com", "")

	if len(q.capturedArgs) < 2 {
		t.Fatalf("expected ≥2 args, got %d", len(q.capturedArgs))
	}
	got, ok := q.capturedArgs[1].(string)
	if !ok {
		t.Fatalf("expected string arg[1], got %T", q.capturedArgs[1])
	}
	if got != "alice" {
		t.Errorf("expected username 'alice', got %q", got)
	}
}

func TestUpsert_EmailWithoutAt(t *testing.T) {
	q := &captureQuerier{}
	repo := repository.NewUserRepository(q)

	_, _ = repo.Upsert(context.Background(), "uid2", "noemail", "")

	got := q.capturedArgs[1].(string)
	if got != "noemail" {
		t.Errorf("expected username 'noemail', got %q", got)
	}
}

func TestUpsert_FirebaseUIDPassedToExec(t *testing.T) {
	q := &captureQuerier{}
	repo := repository.NewUserRepository(q)

	_, _ = repo.Upsert(context.Background(), "my-firebase-uid", "user@test.com", "")

	got := q.capturedArgs[0].(string)
	if got != "my-firebase-uid" {
		t.Errorf("expected firebase_uid 'my-firebase-uid', got %q", got)
	}
}

func TestUpsert_PictureURLPassedToExecWhenNonEmpty(t *testing.T) {
	q := &captureQuerier{}
	repo := repository.NewUserRepository(q)

	_, _ = repo.Upsert(context.Background(), "uid-pic", "user@test.com", "https://example.com/photo.jpg")

	if len(q.capturedArgs) < 3 {
		t.Fatalf("expected ≥3 args, got %d", len(q.capturedArgs))
	}
	avatarArg, ok := q.capturedArgs[2].(*string)
	if !ok {
		t.Fatalf("expected *string arg[2], got %T", q.capturedArgs[2])
	}
	if avatarArg == nil || *avatarArg != "https://example.com/photo.jpg" {
		t.Errorf("arg[2] (avatar_url): got %v, want picture URL", avatarArg)
	}
}

func TestUpsert_EmptyPictureURLPassesNilToExec(t *testing.T) {
	q := &captureQuerier{}
	repo := repository.NewUserRepository(q)

	_, _ = repo.Upsert(context.Background(), "uid-nopic", "user@test.com", "")

	if len(q.capturedArgs) < 3 {
		t.Fatalf("expected ≥3 args, got %d", len(q.capturedArgs))
	}
	avatarArg := q.capturedArgs[2]
	if avatarArg != (*string)(nil) {
		t.Errorf("expected nil *string for empty pictureURL, got %v (%T)", avatarArg, avatarArg)
	}
}

func TestUpsert_ExecError(t *testing.T) {
	dbErr := errors.New("db connection refused")
	q := &captureQuerier{execErr: dbErr}
	repo := repository.NewUserRepository(q)

	user, err := repo.Upsert(context.Background(), "uid3", "bob@example.com", "")

	if user != nil {
		t.Errorf("expected nil user on exec error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestUpsert_ReturnsNilWhenSelectNotFound(t *testing.T) {
	q := &captureQuerier{} // QueryRowContext returns no rows
	repo := repository.NewUserRepository(q)

	user, err := repo.Upsert(context.Background(), "uid4", "charlie@example.com", "")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if user != nil {
		t.Errorf("expected nil user when row not found")
	}
}

func TestUpsert_ReturnsUserWhenFound(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	expected := &repository.User{
		ID:          "00000000-0000-0000-0000-000000000003",
		FirebaseUID: "firebase-uid-3",
		Username:    "carol",
		AvatarURL:   nil,
		CreatedAt:   now,
	}

	repo := repository.NewUserRepository(&rowQuerier{t: t, user: expected})
	got, err := repo.Upsert(context.Background(), "firebase-uid-3", "carol@example.com", "")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil user")
	}
	if got.ID != expected.ID {
		t.Errorf("ID: got %q, want %q", got.ID, expected.ID)
	}
}

// ─── GetByFirebaseUID tests ───────────────────────────────────────────────────

func TestGetByFirebaseUID_NotFound(t *testing.T) {
	repo := repository.NewUserRepository(&rowQuerier{t: t, user: nil})

	user, err := repo.GetByFirebaseUID(context.Background(), "unknown-uid")

	if err != nil {
		t.Fatalf("expected nil error for not-found, got: %v", err)
	}
	if user != nil {
		t.Errorf("expected nil user, got: %+v", user)
	}
}

func TestGetByFirebaseUID_Found(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	avatarURL := "https://example.com/avatar.png"
	expected := &repository.User{
		ID:          "00000000-0000-0000-0000-000000000001",
		FirebaseUID: "firebase-uid-1",
		Username:    "alice",
		AvatarURL:   &avatarURL,
		CreatedAt:   now,
	}

	repo := repository.NewUserRepository(&rowQuerier{t: t, user: expected})
	got, err := repo.GetByFirebaseUID(context.Background(), "firebase-uid-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil user, got nil")
	}
	if got.ID != expected.ID {
		t.Errorf("ID: got %q, want %q", got.ID, expected.ID)
	}
	if got.Username != expected.Username {
		t.Errorf("Username: got %q, want %q", got.Username, expected.Username)
	}
	if got.AvatarURL == nil || *got.AvatarURL != avatarURL {
		t.Errorf("AvatarURL: got %v, want %q", got.AvatarURL, avatarURL)
	}
}

func TestGetByFirebaseUID_NilAvatarURL(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	expected := &repository.User{
		ID:          "00000000-0000-0000-0000-000000000002",
		FirebaseUID: "firebase-uid-2",
		Username:    "bob",
		AvatarURL:   nil,
		CreatedAt:   now,
	}

	repo := repository.NewUserRepository(&rowQuerier{t: t, user: expected})
	got, err := repo.GetByFirebaseUID(context.Background(), "firebase-uid-2")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil user")
	}
	if got.AvatarURL != nil {
		t.Errorf("expected nil AvatarURL, got %q", *got.AvatarURL)
	}
}

// ─── GetByUsername tests ──────────────────────────────────────────────────────

func TestGetByUsername_NotFound(t *testing.T) {
	repo := repository.NewUserRepository(&rowQuerier{t: t, user: nil})

	user, err := repo.GetByUsername(context.Background(), "unknown-user")

	if err != nil {
		t.Fatalf("expected nil error for not-found, got: %v", err)
	}
	if user != nil {
		t.Errorf("expected nil user, got: %+v", user)
	}
}

func TestGetByUsername_Found(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	avatarURL := "https://example.com/avatar.png"
	expected := &repository.User{
		ID:          "00000000-0000-0000-0000-000000000020",
		FirebaseUID: "firebase-uid-20",
		Username:    "carol",
		AvatarURL:   &avatarURL,
		CreatedAt:   now,
	}

	repo := repository.NewUserRepository(&rowQuerier{t: t, user: expected})
	got, err := repo.GetByUsername(context.Background(), "carol")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil user, got nil")
	}
	if got.ID != expected.ID {
		t.Errorf("ID: got %q, want %q", got.ID, expected.ID)
	}
	if got.Username != expected.Username {
		t.Errorf("Username: got %q, want %q", got.Username, expected.Username)
	}
	if got.AvatarURL == nil || *got.AvatarURL != avatarURL {
		t.Errorf("AvatarURL: got %v, want %q", got.AvatarURL, avatarURL)
	}
}

func TestGetByUsername_NilAvatarURL(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	expected := &repository.User{
		ID:          "00000000-0000-0000-0000-000000000021",
		FirebaseUID: "firebase-uid-21",
		Username:    "dave",
		AvatarURL:   nil,
		CreatedAt:   now,
	}

	repo := repository.NewUserRepository(&rowQuerier{t: t, user: expected})
	got, err := repo.GetByUsername(context.Background(), "dave")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil user")
	}
	if got.AvatarURL != nil {
		t.Errorf("expected nil AvatarURL, got %q", *got.AvatarURL)
	}
}

// ─── GetVideosByUserID tests ──────────────────────────────────────────────────

// videosQuerier is a UserQuerier stub that returns pre-configured video rows
// from QueryContext.
type videosQuerier struct {
	t      *testing.T
	videos []repository.Video
	qErr   error
}

func (q *videosQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	return okResult{}, nil
}

func (q *videosQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
}

func (q *videosQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	q.t.Helper()
	if q.qErr != nil {
		return nil, q.qErr
	}
	if len(q.videos) == 0 {
		return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
	}
	// Build fakedb rows for each video.
	now := time.Now().Truncate(time.Second)
	var rows [][]driver.Value
	for _, v := range q.videos {
		thumbVal := driver.Value(nil)
		if v.ThumbnailURL != nil {
			thumbVal = *v.ThumbnailURL
		}
		ts := v.CreatedAt
		if ts.IsZero() {
			ts = now
		}
		rows = append(rows, []driver.Value{v.ID, v.Title, thumbVal, v.ViewCount, ts})
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"id", "title", "thumbnail_url", "view_count", "created_at"},
			rows:    rows,
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryContext(context.Background(),
		"SELECT id, title, thumbnail_url, view_count, created_at FROM videos")
}

func TestGetVideosByUserID_Empty(t *testing.T) {
	q := &videosQuerier{t: t, videos: nil}
	repo := repository.NewUserRepository(q)

	videos, err := repo.GetVideosByUserID(context.Background(), "user-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(videos) != 0 {
		t.Errorf("expected 0 videos, got %d", len(videos))
	}
}

func TestGetVideosByUserID_ReturnsVideos(t *testing.T) {
	thumb := "https://example.com/thumb.jpg"
	now := time.Now().Truncate(time.Second)
	expected := []repository.Video{
		{ID: "v1", Title: "Hello World", ThumbnailURL: &thumb, ViewCount: 42, CreatedAt: now},
		{ID: "v2", Title: "No Thumb", ThumbnailURL: nil, ViewCount: 7, CreatedAt: now},
	}

	q := &videosQuerier{t: t, videos: expected}
	repo := repository.NewUserRepository(q)

	got, err := repo.GetVideosByUserID(context.Background(), "user-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("expected 2 videos, got %d", len(got))
	}
	if got[0].ID != "v1" {
		t.Errorf("video[0].ID: got %q, want %q", got[0].ID, "v1")
	}
	if got[0].Title != "Hello World" {
		t.Errorf("video[0].Title: got %q, want %q", got[0].Title, "Hello World")
	}
	if got[0].ThumbnailURL == nil || *got[0].ThumbnailURL != thumb {
		t.Errorf("video[0].ThumbnailURL: got %v, want %q", got[0].ThumbnailURL, thumb)
	}
	if got[0].ViewCount != 42 {
		t.Errorf("video[0].ViewCount: got %d, want 42", got[0].ViewCount)
	}
	if got[1].ThumbnailURL != nil {
		t.Errorf("video[1].ThumbnailURL: expected nil, got %q", *got[1].ThumbnailURL)
	}
}

func TestGetVideosByUserID_QueryError(t *testing.T) {
	dbErr := errors.New("query failed")
	q := &videosQuerier{t: t, qErr: dbErr}
	repo := repository.NewUserRepository(q)

	videos, err := repo.GetVideosByUserID(context.Background(), "user-1")

	if videos != nil {
		t.Errorf("expected nil videos on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

// ─── UpdateProfile querier stub ───────────────────────────────────────────────

// updateQuerier extends rowQuerier with configurable RowsAffected.
type updateQuerier struct {
	t            *testing.T
	user         *repository.User
	execErr      error
	rowsAffected int64
	// capturedExecArgs holds the args passed to ExecContext.
	capturedExecArgs []any
}

func (q *updateQuerier) ExecContext(_ context.Context, _ string, args ...any) (sql.Result, error) {
	q.capturedExecArgs = args
	if q.execErr != nil {
		return nil, q.execErr
	}
	return rowsAffectedResult{n: q.rowsAffected}, nil
}

func (q *updateQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.user == nil {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
	}
	return userDB(q.t, q.user).QueryRowContext(
		context.Background(),
		"SELECT id, firebase_uid, username, avatar_url, created_at FROM users WHERE firebase_uid = $1",
		q.user.FirebaseUID,
	)
}

func (q *updateQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
}

type rowsAffectedResult struct{ n int64 }

func (r rowsAffectedResult) LastInsertId() (int64, error) { return 0, nil }
func (r rowsAffectedResult) RowsAffected() (int64, error) { return r.n, nil }

// ─── UpdateProfile tests ──────────────────────────────────────────────────────

func TestUpdateProfile_ExecError(t *testing.T) {
	dbErr := errors.New("update failed")
	q := &updateQuerier{t: t, execErr: dbErr, rowsAffected: 0}
	repo := repository.NewUserRepository(q)

	user, err := repo.UpdateProfile(context.Background(), "uid1", "alice", nil)

	if user != nil {
		t.Errorf("expected nil user on exec error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestUpdateProfile_NoRowsAffected_ReturnsNilUser(t *testing.T) {
	q := &updateQuerier{t: t, user: nil, rowsAffected: 0}
	repo := repository.NewUserRepository(q)

	user, err := repo.UpdateProfile(context.Background(), "unknown-uid", "alice", nil)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if user != nil {
		t.Errorf("expected nil user when no rows affected")
	}
}

func TestUpdateProfile_RowAffected_ReturnsUpdatedUser(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	avatarURL := "https://example.com/new.png"
	expected := &repository.User{
		ID:          "00000000-0000-0000-0000-000000000010",
		FirebaseUID: "firebase-uid-10",
		Username:    "alice-updated",
		AvatarURL:   &avatarURL,
		CreatedAt:   now,
	}
	q := &updateQuerier{t: t, user: expected, rowsAffected: 1}
	repo := repository.NewUserRepository(q)

	got, err := repo.UpdateProfile(context.Background(), "firebase-uid-10", "alice-updated", &avatarURL)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil user")
	}
	if got.Username != "alice-updated" {
		t.Errorf("Username: got %q, want %q", got.Username, "alice-updated")
	}
	if got.AvatarURL == nil || *got.AvatarURL != avatarURL {
		t.Errorf("AvatarURL: got %v, want %q", got.AvatarURL, avatarURL)
	}
}

func TestUpdateProfile_PassesFirebaseUIDAsThirdArg(t *testing.T) {
	q := &updateQuerier{t: t, user: nil, rowsAffected: 0}
	repo := repository.NewUserRepository(q)

	_, _ = repo.UpdateProfile(context.Background(), "my-firebase-uid", "bob", nil)

	if len(q.capturedExecArgs) < 3 {
		t.Fatalf("expected ≥3 exec args, got %d", len(q.capturedExecArgs))
	}
	uid, ok := q.capturedExecArgs[2].(string)
	if !ok {
		t.Fatalf("expected string arg[2], got %T", q.capturedExecArgs[2])
	}
	if uid != "my-firebase-uid" {
		t.Errorf("arg[2] (firebase_uid): got %q, want %q", uid, "my-firebase-uid")
	}
}

func TestUpdateProfile_PassesUsernameAsFirstArg(t *testing.T) {
	q := &updateQuerier{t: t, user: nil, rowsAffected: 0}
	repo := repository.NewUserRepository(q)

	_, _ = repo.UpdateProfile(context.Background(), "uid", "newusername", nil)

	if len(q.capturedExecArgs) < 1 {
		t.Fatalf("expected ≥1 exec args, got %d", len(q.capturedExecArgs))
	}
	username, ok := q.capturedExecArgs[0].(string)
	if !ok {
		t.Fatalf("expected string arg[0], got %T", q.capturedExecArgs[0])
	}
	if username != "newusername" {
		t.Errorf("arg[0] (username): got %q, want %q", username, "newusername")
	}
}

func TestUpdateProfile_PassesAvatarURLAsSecondArg(t *testing.T) {
	avatarURL := "https://example.com/avatar.png"
	q := &updateQuerier{t: t, user: nil, rowsAffected: 0}
	repo := repository.NewUserRepository(q)

	_, _ = repo.UpdateProfile(context.Background(), "uid", "alice", &avatarURL)

	if len(q.capturedExecArgs) < 2 {
		t.Fatalf("expected ≥2 exec args, got %d", len(q.capturedExecArgs))
	}
	avatarArg, ok := q.capturedExecArgs[1].(*string)
	if !ok {
		t.Fatalf("expected *string arg[1], got %T", q.capturedExecArgs[1])
	}
	if avatarArg == nil || *avatarArg != avatarURL {
		t.Errorf("arg[1] (avatar_url): got %v, want %q", avatarArg, avatarURL)
	}
}

func TestUpdateProfile_NilAvatarURL_PassedThrough(t *testing.T) {
	q := &updateQuerier{t: t, user: nil, rowsAffected: 0}
	repo := repository.NewUserRepository(q)

	_, _ = repo.UpdateProfile(context.Background(), "uid", "alice", nil)

	if len(q.capturedExecArgs) < 2 {
		t.Fatalf("expected ≥2 exec args, got %d", len(q.capturedExecArgs))
	}
	avatarArg := q.capturedExecArgs[1]
	if avatarArg != (*string)(nil) {
		t.Errorf("expected nil *string arg[1], got %v (%T)", avatarArg, avatarArg)
	}
}
