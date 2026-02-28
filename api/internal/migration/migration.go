// Package migration wraps golang-migrate to run embedded SQL migration files.
package migration

import (
	"database/sql"
	"errors"
	"fmt"
	"io/fs"

	"github.com/golang-migrate/migrate/v4"
	"github.com/golang-migrate/migrate/v4/database/postgres"
	"github.com/golang-migrate/migrate/v4/source/iofs"
)

// Migrator is the interface used by RunMigrations so callers can inject a
// mock in unit tests.
type Migrator interface {
	Up() error
}

// migrateMaker is a function type that creates a Migrator from a *sql.DB and
// the migrations filesystem.  Replaced in tests to inject a mock.
type migrateMaker func(db *sql.DB, migrationsFS fs.ReadDirFS) (Migrator, error)

// defaultMakeMigrator is the production implementation that builds a real
// *migrate.Migrate instance backed by iofs + postgres driver.
func defaultMakeMigrator(db *sql.DB, migrationsFS fs.ReadDirFS) (Migrator, error) {
	src, err := iofs.New(migrationsFS, ".")
	if err != nil {
		return nil, fmt.Errorf("iofs source: %w", err)
	}

	driver, err := postgres.WithInstance(db, &postgres.Config{})
	if err != nil {
		return nil, fmt.Errorf("postgres driver: %w", err)
	}

	m, err := migrate.NewWithInstance("iofs", src, "postgres", driver)
	if err != nil {
		return nil, fmt.Errorf("migrate instance: %w", err)
	}
	return m, nil
}

// RunMigrations applies all pending migrations.
// migrationsFS must be a directory FS whose root contains the numbered *.sql
// files (e.g. 0001_initial_schema.up.sql).
func RunMigrations(db *sql.DB, migrationsFS fs.ReadDirFS) error {
	return runMigrations(db, migrationsFS, defaultMakeMigrator)
}

// runMigrations is the testable inner implementation.
func runMigrations(db *sql.DB, migrationsFS fs.ReadDirFS, maker migrateMaker) error {
	m, err := maker(db, migrationsFS)
	if err != nil {
		return err
	}

	if err := m.Up(); err != nil && !errors.Is(err, migrate.ErrNoChange) {
		return fmt.Errorf("migrate up: %w", err)
	}
	return nil
}
