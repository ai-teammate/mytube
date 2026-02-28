// Package database provides PostgreSQL connection helpers.
package database

import (
	"database/sql"
	"fmt"
	"os"

	_ "github.com/lib/pq"
)

// DB is the interface covering the database/sql.DB methods used by this package.
// Using an interface makes it trivial to swap in a mock during unit tests.
type DB interface {
	Ping() error
}

// Open opens a *sql.DB using connection parameters from environment variables.
// Callers are responsible for closing the returned DB.
func Open() (*sql.DB, error) {
	return sql.Open("postgres", DSN())
}

// DSN builds a PostgreSQL DSN from environment variables.
// When INSTANCE_UNIX_SOCKET is set (Cloud SQL via Unix socket) that path is
// used as the host; otherwise a TCP connection is made.
func DSN() string {
	if socket := os.Getenv("INSTANCE_UNIX_SOCKET"); socket != "" {
		return fmt.Sprintf(
			"host=%s user=%s password=%s dbname=%s sslmode=disable",
			socket, os.Getenv("DB_USER"), os.Getenv("DB_PASSWORD"), os.Getenv("DB_NAME"),
		)
	}
	return fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		getenv("DB_HOST", "localhost"),
		getenv("DB_PORT", "5432"),
		os.Getenv("DB_USER"),
		os.Getenv("DB_PASSWORD"),
		getenv("DB_NAME", "mytube"),
	)
}

// getenv returns the value of the environment variable named by key, or
// fallback when the variable is unset or empty.
func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
