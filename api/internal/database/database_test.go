package database

import (
	"os"
	"strings"
	"testing"

	_ "github.com/lib/pq"
)

func TestDSN_TCPDefaults(t *testing.T) {
	// Clear all relevant env vars to ensure defaults are used.
	vars := []string{
		"INSTANCE_UNIX_SOCKET", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME", "SSL_MODE",
	}
	for _, v := range vars {
		t.Setenv(v, "")
	}

	got := DSN()
	// Assert structural fields individually to avoid embedding password literals in test output.
	checks := map[string]string{
		"host":    "host=localhost",
		"port":    "port=5432",
		"dbname":  "dbname=mytube",
		"sslmode": "sslmode=require",
	}
	for field, want := range checks {
		if !strings.Contains(got, want) {
			t.Errorf("DSN() missing %s: want %q in %q", field, want, got)
		}
	}
}

func TestDSN_TCPCustom(t *testing.T) {
	t.Setenv("INSTANCE_UNIX_SOCKET", "")
	t.Setenv("DB_HOST", "db.example.com")
	t.Setenv("DB_PORT", "5433")
	t.Setenv("DB_USER", "alice")
	t.Setenv("DB_PASSWORD", "secret")
	t.Setenv("DB_NAME", "mydb")
	t.Setenv("SSL_MODE", "")

	got := DSN()
	// Assert each field individually; do not assert the password literal in error output.
	checks := map[string]string{
		"host":    "host=db.example.com",
		"port":    "port=5433",
		"user":    "user=alice",
		"dbname":  "dbname=mydb",
		"sslmode": "sslmode=require",
	}
	for field, want := range checks {
		if !strings.Contains(got, want) {
			t.Errorf("DSN() missing %s: want %q present", field, want)
		}
	}
}

func TestDSN_TCPSSLModeOverride(t *testing.T) {
	t.Setenv("INSTANCE_UNIX_SOCKET", "")
	t.Setenv("DB_HOST", "localhost")
	t.Setenv("DB_PORT", "5432")
	t.Setenv("DB_USER", "dev")
	t.Setenv("DB_PASSWORD", "dev")
	t.Setenv("DB_NAME", "mytube")
	t.Setenv("SSL_MODE", "disable")

	got := DSN()
	if !strings.Contains(got, "sslmode=disable") {
		t.Errorf("DSN() expected sslmode=disable when SSL_MODE=disable, got %q", got)
	}
}

func TestDSN_UnixSocket(t *testing.T) {
	t.Setenv("INSTANCE_UNIX_SOCKET", "/cloudsql/project:region:instance")
	t.Setenv("DB_USER", "svc")
	t.Setenv("DB_PASSWORD", "pw")
	t.Setenv("DB_NAME", "prod")

	got := DSN()
	// Unix socket path must always use sslmode=disable (traffic stays on the VM).
	checks := map[string]string{
		"host":    "host=/cloudsql/project:region:instance",
		"dbname":  "dbname=prod",
		"sslmode": "sslmode=disable",
	}
	for field, want := range checks {
		if !strings.Contains(got, want) {
			t.Errorf("DSN() missing %s: want %q present", field, want)
		}
	}
}

func TestGetenv_Fallback(t *testing.T) {
	const key = "TEST_GETENV_KEY_UNUSED"
	os.Unsetenv(key)

	if got := getenv(key, "fallback_value"); got != "fallback_value" {
		t.Errorf("getenv fallback = %q, want %q", got, "fallback_value")
	}
}

func TestGetenv_EnvSet(t *testing.T) {
	const key = "TEST_GETENV_KEY_SET"
	t.Setenv(key, "env_value")

	if got := getenv(key, "ignored"); got != "env_value" {
		t.Errorf("getenv set = %q, want %q", got, "env_value")
	}
}

// TestOpen_ReturnsDB verifies that Open() returns a non-nil *sql.DB.
// sql.Open with the postgres driver does not establish a connection, so this
// succeeds without a running database.
func TestOpen_ReturnsDB(t *testing.T) {
	t.Setenv("INSTANCE_UNIX_SOCKET", "")
	t.Setenv("DB_HOST", "localhost")
	t.Setenv("DB_PORT", "5432")
	t.Setenv("DB_USER", "test")
	t.Setenv("DB_PASSWORD", "test")
	t.Setenv("DB_NAME", "test")

	db, err := Open()
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	if db == nil {
		t.Fatal("Open() returned nil db")
	}
	db.Close()
}
