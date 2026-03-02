package main

import (
	"context"
	"embed"
	"io/fs"
	"log"
	"net/http"
	"os"

	gcstorage "cloud.google.com/go/storage"
	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/database"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/migration"
	"github.com/ai-teammate/mytube/api/internal/repository"
	"github.com/ai-teammate/mytube/api/internal/storage"
)

//go:embed migrations/*.sql
var rawMigrationsFS embed.FS

func main() {
	ctx := context.Background()

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

	verifier, err := auth.NewFirebaseVerifier(ctx)
	if err != nil {
		log.Fatalf("firebase verifier: %v", err)
	}

	gcsClient, err := gcstorage.NewClient(ctx)
	if err != nil {
		log.Fatalf("gcs client: %v", err)
	}

	if os.Getenv("RAW_UPLOADS_BUCKET") == "" {
		log.Fatalf("RAW_UPLOADS_BUCKET environment variable is required")
	}

	userRepo := repository.NewUserRepository(db)
	videoRepo := repository.NewVideoRepository(db)
	ratingRepo := repository.NewRatingRepository(db)
	commentRepo := repository.NewCommentRepository(db)
	searchRepo := repository.NewSearchRepository(db)
	gcsSigner := storage.NewGCSSigner(gcsClient)
	authMiddleware := middleware.RequireAuth(verifier)

	cdnBaseURL := os.Getenv("CDN_BASE_URL")

	// /api/videos (exact) handles both:
	//   GET  ?category_id=<id>  — public category browse
	//   POST                    — auth-protected video creation
	createHandler := authMiddleware(handler.NewVideosHandler(videoRepo, userRepo, gcsSigner))
	browseHandler := handler.NewBrowseVideosHandler(searchRepo)
	videosHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodPost:
			createHandler.ServeHTTP(w, r)
		case http.MethodGet:
			browseHandler.ServeHTTP(w, r)
		default:
			w.Header().Set("Allow", "GET, POST")
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusMethodNotAllowed)
			_, _ = w.Write([]byte(`{"error":"method not allowed"}`))
		}
	})

	mux := http.NewServeMux()
	mux.HandleFunc("/health", handler.NewHealthHandler(db))
	mux.Handle("/api/me", authMiddleware(handler.NewMeHandler(userRepo)))
	mux.Handle("/api/users/", handler.NewUsersHandler(userRepo))
	// Rating and comment sub-resources are registered with wildcard patterns
	// (Go 1.22+ ServeMux), so they take precedence over the /api/videos/ subtree.
	// Public GET endpoints are wrapped with per-IP rate limiting to guard against
	// DB overload and video-ID enumeration abuse.
	mux.Handle("/api/videos/{id}/rating", middleware.RateLimitPublic(handler.NewRatingHandler(ratingRepo, userRepo, videoRepo)))
	mux.Handle("/api/videos/{id}/comments", middleware.RateLimitPublic(handler.NewVideoCommentsHandler(commentRepo, userRepo, videoRepo)))
	// Delete comment: authenticated
	mux.Handle("/api/comments/", authMiddleware(handler.NewDeleteCommentHandler(commentRepo, userRepo)))
	// /api/videos/recent and /api/videos/popular must be registered before
	// the generic /api/videos/ prefix handler so they are matched first.
	mux.Handle("/api/videos/recent", handler.NewRecentVideosHandler(searchRepo))
	mux.Handle("/api/videos/popular", handler.NewPopularVideosHandler(searchRepo))
	mux.Handle("/api/videos/", handler.NewVideoHandler(videoRepo, cdnBaseURL))
	mux.Handle("/api/videos", videosHandler)
	mux.Handle("/api/search", handler.NewSearchHandler(searchRepo))
	mux.Handle("/api/categories", handler.NewCategoriesHandler(searchRepo))
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
