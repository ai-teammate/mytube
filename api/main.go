package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	_ "github.com/lib/pq"
)

var db *sql.DB

func main() {
	var err error
	db, err = sql.Open("postgres", dsn())
	if err != nil {
		log.Fatalf("db: %v", err)
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, "mytube api")
	})

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if err := db.Ping(); err != nil {
			w.WriteHeader(500)
			json.NewEncoder(w).Encode(map[string]string{"status": "error", "db": err.Error()})
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "db": "connected"})
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

func dsn() string {
	if socket := os.Getenv("INSTANCE_UNIX_SOCKET"); socket != "" {
		return fmt.Sprintf("host=%s user=%s password=%s dbname=%s sslmode=disable",
			socket, os.Getenv("DB_USER"), os.Getenv("DB_PASSWORD"), os.Getenv("DB_NAME"))
	}
	return fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		getenv("DB_HOST", "localhost"), getenv("DB_PORT", "5432"),
		os.Getenv("DB_USER"), os.Getenv("DB_PASSWORD"), getenv("DB_NAME", "mytube"))
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
