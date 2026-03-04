// Package database provides PostgreSQL connection helpers.
package database

import (
	"database/sql"
	"fmt"
	"os"

	_ "github.com/lib/pq"
)

// Open opens a *sql.DB using connection parameters from environment variables.
// Callers are responsible for closing the returned DB.
func Open() (*sql.DB, error) {
	return sql.Open("postgres", DSN())
}

// DSN builds a PostgreSQL DSN from environment variables.
// Priority order:
//  1. DB_DSN — if set, returned as-is (allows callers such as test harnesses to
//     supply a complete pre-built DSN).
//  2. INSTANCE_UNIX_SOCKET — Cloud SQL via Unix socket (sslmode always disabled).
//  3. Individual TCP vars: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, SSL_MODE.
func DSN() string {
	if dsn := os.Getenv("DB_DSN"); dsn != "" {
		return dsn
	}
	if socket := os.Getenv("INSTANCE_UNIX_SOCKET"); socket != "" {
		return fmt.Sprintf(
			"host=%s user=%s password=%s dbname=%s sslmode=disable",
			socket, os.Getenv("DB_USER"), os.Getenv("DB_PASSWORD"), os.Getenv("DB_NAME"),
		)
	}
	sslMode := getenv("SSL_MODE", "require")
	return fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		getenv("DB_HOST", "localhost"),
		getenv("DB_PORT", "5432"),
		os.Getenv("DB_USER"),
		os.Getenv("DB_PASSWORD"),
		getenv("DB_NAME", "mytube"),
		sslMode,
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
