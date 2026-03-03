package repository_test

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"testing"

	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── ratingQuerier stub ───────────────────────────────────────────────────────

type ratingQuerier struct {
	t           *testing.T
	avgRating   float64
	count       int64
	myRating    *int
	queryRowErr bool
	execErr     error
	execCalled  bool
}

func (q *ratingQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	q.execCalled = true
	if q.execErr != nil {
		return nil, q.execErr
	}
	return okResult{}, nil
}

func (q *ratingQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.queryRowErr {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
	}

	myRatingVal := driver.Value(nil)
	if q.myRating != nil {
		myRatingVal = int64(*q.myRating)
	}

	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"avg", "count", "my_rating"},
			rows:    [][]driver.Value{{q.avgRating, q.count, myRatingVal}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryRowContext(context.Background(), "SELECT 1")
}

// ─── UpsertRating tests ───────────────────────────────────────────────────────

func TestUpsertRating_ExecError_ReturnsError(t *testing.T) {
	dbErr := errors.New("upsert failed")
	q := &ratingQuerier{t: t, execErr: dbErr}
	repo := repository.NewRatingRepository(q)

	result, err := repo.UpsertRating(context.Background(), "video-1", "user-1", 4)

	if result != nil {
		t.Errorf("expected nil result on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestUpsertRating_Success_ReturnsSummary(t *testing.T) {
	myRating := 4
	q := &ratingQuerier{
		t:         t,
		avgRating: 4.2,
		count:     10,
		myRating:  &myRating,
	}
	repo := repository.NewRatingRepository(q)

	result, err := repo.UpsertRating(context.Background(), "video-1", "user-1", 4)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result == nil {
		t.Fatal("expected non-nil result")
	}
	if result.AverageRating != 4.2 {
		t.Errorf("AverageRating: got %v, want 4.2", result.AverageRating)
	}
	if result.RatingCount != 10 {
		t.Errorf("RatingCount: got %d, want 10", result.RatingCount)
	}
	if result.MyRating == nil || *result.MyRating != 4 {
		t.Errorf("MyRating: got %v, want 4", result.MyRating)
	}
}

func TestUpsertRating_CallsExec(t *testing.T) {
	myRating := 3
	q := &ratingQuerier{t: t, avgRating: 3.0, count: 1, myRating: &myRating}
	repo := repository.NewRatingRepository(q)

	_, err := repo.UpsertRating(context.Background(), "video-1", "user-1", 3)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !q.execCalled {
		t.Errorf("expected ExecContext to be called")
	}
}

// ─── GetSummary tests ─────────────────────────────────────────────────────────

func TestGetSummary_WithoutUserID_MyRatingIsNil(t *testing.T) {
	q := &ratingQuerier{t: t, avgRating: 3.5, count: 4, myRating: nil}
	repo := repository.NewRatingRepository(q)

	result, err := repo.GetSummary(context.Background(), "video-1", nil)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result == nil {
		t.Fatal("expected non-nil result")
	}
	if result.MyRating != nil {
		t.Errorf("MyRating: expected nil, got %d", *result.MyRating)
	}
	if result.AverageRating != 3.5 {
		t.Errorf("AverageRating: got %v, want 3.5", result.AverageRating)
	}
	if result.RatingCount != 4 {
		t.Errorf("RatingCount: got %d, want 4", result.RatingCount)
	}
}

func TestGetSummary_WithUserID_MyRatingSet(t *testing.T) {
	myRating := 5
	uid := "user-1"
	q := &ratingQuerier{t: t, avgRating: 5.0, count: 1, myRating: &myRating}
	repo := repository.NewRatingRepository(q)

	result, err := repo.GetSummary(context.Background(), "video-1", &uid)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.MyRating == nil || *result.MyRating != 5 {
		t.Errorf("MyRating: got %v, want 5", result.MyRating)
	}
}

func TestGetSummary_NoRows_ReturnsEmptySummary(t *testing.T) {
	// When the query returns no rows (ErrNoRows), GetSummary returns an empty
	// summary rather than an error, so the rating widget still renders.
	q := &ratingQuerier{t: t, queryRowErr: true}
	repo := repository.NewRatingRepository(q)

	result, err := repo.GetSummary(context.Background(), "video-1", nil)

	if err != nil {
		t.Errorf("expected nil error for no-rows, got: %v", err)
	}
	if result == nil {
		t.Errorf("expected non-nil empty summary on no rows")
	}
}

func TestGetSummary_ZeroRatings(t *testing.T) {
	q := &ratingQuerier{t: t, avgRating: 0, count: 0, myRating: nil}
	repo := repository.NewRatingRepository(q)

	result, err := repo.GetSummary(context.Background(), "video-1", nil)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.RatingCount != 0 {
		t.Errorf("RatingCount: got %d, want 0", result.RatingCount)
	}
	if result.AverageRating != 0 {
		t.Errorf("AverageRating: got %v, want 0", result.AverageRating)
	}
}
