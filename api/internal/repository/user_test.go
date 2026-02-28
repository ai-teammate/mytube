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
	columns []string
	rows    [][]driver.Value
}

// registerResults stores results under a unique DSN and returns that DSN.
func registerResults(results []fakeQueryResult) string {
	dsn := nextDSN()
	resultRegistry[dsn] = results
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
func (*fakeStmt) Exec(_ []driver.Value) (driver.Result, error) {
	return fakeDriverResult{}, nil
}
func (s *fakeStmt) Query(_ []driver.Value) (driver.Rows, error) {
	return &fakeRows{cols: s.qr.columns, data: s.qr.rows}, nil
}

type fakeDriverResult struct{}

func (fakeDriverResult) LastInsertId() (int64, error) { return 0, nil }
func (fakeDriverResult) RowsAffected() (int64, error) { return 1, nil }

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
func userDB(u *repository.User) *sql.DB {
	avatarVal := driver.Value(nil)
	if u.AvatarURL != nil {
		avatarVal = *u.AvatarURL
	}
	dsn := registerResults([]fakeQueryResult{
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

// rowQuerier returns a fully-populated row from QueryRowContext (for found tests).
type rowQuerier struct {
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
	return userDB(q.user).QueryRowContext(
		context.Background(),
		"SELECT id, firebase_uid, username, avatar_url, created_at FROM users WHERE firebase_uid = $1",
		q.user.FirebaseUID,
	)
}

// ─── Upsert tests ─────────────────────────────────────────────────────────────

func TestUpsert_UsesEmailPrefix(t *testing.T) {
	q := &captureQuerier{}
	repo := repository.NewUserRepository(q)

	_, _ = repo.Upsert(context.Background(), "uid1", "alice@example.com")

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

	_, _ = repo.Upsert(context.Background(), "uid2", "noemail")

	got := q.capturedArgs[1].(string)
	if got != "noemail" {
		t.Errorf("expected username 'noemail', got %q", got)
	}
}

func TestUpsert_FirebaseUIDPassedToExec(t *testing.T) {
	q := &captureQuerier{}
	repo := repository.NewUserRepository(q)

	_, _ = repo.Upsert(context.Background(), "my-firebase-uid", "user@test.com")

	got := q.capturedArgs[0].(string)
	if got != "my-firebase-uid" {
		t.Errorf("expected firebase_uid 'my-firebase-uid', got %q", got)
	}
}

func TestUpsert_ExecError(t *testing.T) {
	dbErr := errors.New("db connection refused")
	q := &captureQuerier{execErr: dbErr}
	repo := repository.NewUserRepository(q)

	user, err := repo.Upsert(context.Background(), "uid3", "bob@example.com")

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

	user, err := repo.Upsert(context.Background(), "uid4", "charlie@example.com")

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

	repo := repository.NewUserRepository(&rowQuerier{user: expected})
	got, err := repo.Upsert(context.Background(), "firebase-uid-3", "carol@example.com")

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
	repo := repository.NewUserRepository(&rowQuerier{user: nil})

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

	repo := repository.NewUserRepository(&rowQuerier{user: expected})
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

	repo := repository.NewUserRepository(&rowQuerier{user: expected})
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
