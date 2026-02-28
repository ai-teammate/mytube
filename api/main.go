package main

import (
	"embed"
	"io/fs"
	"log"
	"net/http"
	"os"

	"github.com/ai-teammate/mytube/api/internal/database"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/migration"
)

//go:embed migrations/*.sql
var rawMigrationsFS embed.FS

func main() {
	db, err := database.Open()
	if err != nil {
		log.Fatalf("db open: %v", err)
	}

	// Sub-FS so that the root of migrationsFS contains *.sql directly.
	migrationsFS, err := fs.Sub(rawMigrationsFS, "migrations")
	if err != nil {
		log.Fatalf("migrations sub-fs: %v", err)
	}

	if err := migration.RunMigrations(db, migrationsFS.(fs.ReadDirFS)); err != nil {
		log.Fatalf("migrate: %v", err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", handler.NewHealthHandler(db))
	// Catch-all: return 404 for any path not matched above.
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		http.NotFound(w, r)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}
