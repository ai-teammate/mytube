package migration

import (
	"database/sql"
	"errors"
	"io/fs"
	"testing"
	"testing/fstest"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/lib/pq"
)

// stubMigrator is a test double for Migrator.
type stubMigrator struct {
	upErr    error
	forceErr error
	upCalls  int
}

func (s *stubMigrator) Up() error {
	s.upCalls++
	// After Force is called (upCalls > 1) succeed by default unless forceErr set.
	if s.upCalls > 1 {
		return nil
	}
	return s.upErr
}

func (s *stubMigrator) Force(_ int) error { return s.forceErr }

// noopMaker returns a stubMigrator regardless of inputs.
func noopMaker(upErr error) migrateMaker {
	return func(_ *sql.DB, _ fs.ReadDirFS) (Migrator, error) {
		return &stubMigrator{upErr: upErr}, nil
	}
}

// errorMaker simulates a failure during Migrator construction.
func errorMaker(makeErr error) migrateMaker {
	return func(_ *sql.DB, _ fs.ReadDirFS) (Migrator, error) {
		return nil, makeErr
	}
}

// emptyFS is a valid ReadDirFS with no files, used when the FS is not
// exercised by the test (maker is fully stubbed).
var emptyFS = fstest.MapFS{}

// TestRunMigrationsPublic_PropagatesError verifies that the public RunMigrations
// wrapper propagates errors from defaultMakeMigrator when given an unreachable
// database.  We open a *sql.DB without an active server so that
// postgres.WithInstance (which pings the DB) returns an error.
func TestRunMigrationsPublic_PropagatesError(t *testing.T) {
	db, err := sql.Open("postgres",
		"host=127.0.0.1 port=1 user=x password=x dbname=x sslmode=disable connect_timeout=1")
	if err != nil {
		t.Fatalf("sql.Open: %v", err)
	}
	defer db.Close()

	err = RunMigrations(db, emptyFS)
	if err == nil {
		t.Fatal("expected error for unreachable DB, got nil")
	}
}

func TestRunMigrations_Success(t *testing.T) {
	if err := runMigrations(nil, emptyFS, noopMaker(nil)); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
}

func TestRunMigrations_NoChange(t *testing.T) {
	// ErrNoChange is not a real error — migrations are already up to date.
	if err := runMigrations(nil, emptyFS, noopMaker(migrate.ErrNoChange)); err != nil {
		t.Fatalf("expected no error on ErrNoChange, got %v", err)
	}
}

func TestRunMigrations_UpError(t *testing.T) {
	upErr := errors.New("dirty database")
	err := runMigrations(nil, emptyFS, noopMaker(upErr))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, upErr) {
		t.Errorf("expected wrapped upErr, got %v", err)
	}
}

func TestRunMigrations_MakerError(t *testing.T) {
	makeErr := errors.New("driver init failed")
	err := runMigrations(nil, emptyFS, errorMaker(makeErr))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, makeErr) {
		t.Errorf("expected wrapped makeErr, got %v", err)
	}
}

func TestRunMigrations_DirtyState_RecoversAndSucceeds(t *testing.T) {
	// Simulate a dirty DB at version 1: Up() returns ErrDirty on first call,
	// Force clears it, second Up() succeeds.
	dirtyErr := migrate.ErrDirty{Version: 1}
	maker := func(_ *sql.DB, _ fs.ReadDirFS) (Migrator, error) {
		return &stubMigrator{upErr: dirtyErr}, nil
	}
	if err := runMigrations(nil, emptyFS, maker); err != nil {
		t.Fatalf("expected recovery from dirty state, got %v", err)
	}
}

func TestRunMigrations_DirtyState_ForceError(t *testing.T) {
	// When Force itself fails, the error is propagated.
	dirtyErr := migrate.ErrDirty{Version: 1}
	forceErr := errors.New("force failed")
	maker := func(_ *sql.DB, _ fs.ReadDirFS) (Migrator, error) {
		return &stubMigrator{upErr: dirtyErr, forceErr: forceErr}, nil
	}
	err := runMigrations(nil, emptyFS, maker)
	if err == nil {
		t.Fatal("expected error from Force, got nil")
	}
	if !errors.Is(err, forceErr) {
		t.Errorf("expected wrapped forceErr, got %v", err)
	}
}
