package database

import (
	"os"
	"testing"

	_ "github.com/lib/pq"
)

func TestDSN_TCPDefaults(t *testing.T) {
	// Clear all relevant env vars to ensure defaults are used.
	vars := []string{
		"INSTANCE_UNIX_SOCKET", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME",
	}
	for _, v := range vars {
		t.Setenv(v, "")
	}

	got := DSN()
	want := "host=localhost port=5432 user= password= dbname=mytube sslmode=disable"
	if got != want {
		t.Errorf("DSN() = %q, want %q", got, want)
	}
}

func TestDSN_TCPCustom(t *testing.T) {
	t.Setenv("INSTANCE_UNIX_SOCKET", "")
	t.Setenv("DB_HOST", "db.example.com")
	t.Setenv("DB_PORT", "5433")
	t.Setenv("DB_USER", "alice")
	t.Setenv("DB_PASSWORD", "secret")
	t.Setenv("DB_NAME", "mydb")

	got := DSN()
	want := "host=db.example.com port=5433 user=alice password=secret dbname=mydb sslmode=disable"
	if got != want {
		t.Errorf("DSN() = %q, want %q", got, want)
	}
}

func TestDSN_UnixSocket(t *testing.T) {
	t.Setenv("INSTANCE_UNIX_SOCKET", "/cloudsql/project:region:instance")
	t.Setenv("DB_USER", "svc")
	t.Setenv("DB_PASSWORD", "pw")
	t.Setenv("DB_NAME", "prod")

	got := DSN()
	want := "host=/cloudsql/project:region:instance user=svc password=pw dbname=prod sslmode=disable"
	if got != want {
		t.Errorf("DSN() = %q, want %q", got, want)
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
