// Package repository provides data-access objects for the mytube domain.
package repository

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// SearchVideo represents a video row returned by search and discovery queries.
type SearchVideo struct {
	ID               string
	Title            string
	ThumbnailURL     *string
	ViewCount        int64
	UploaderUsername string
	CreatedAt        time.Time
}

// Category represents a row in the categories table.
type Category struct {
	ID   int
	Name string
}

// SearchParams holds the parameters for the search endpoint.
type SearchParams struct {
	Query      string
	CategoryID *int
	Limit      int
	Offset     int
}

// SearchRepository handles persistence for search and discovery queries.
type SearchRepository struct {
	db VideoQuerier
}

// NewSearchRepository constructs a SearchRepository backed by db.
func NewSearchRepository(db VideoQuerier) *SearchRepository {
	return &SearchRepository{db: db}
}

// queryBuilder accumulates SQL WHERE conditions paired with their bind
// parameter values. It automatically assigns sequential $N placeholders,
// eliminating the manual argIdx counter and the risk of interpolating
// user-controlled values directly into the SQL string.
//
// IMPORTANT: Only static string literals must be passed as the cond argument.
// Never interpolate user-supplied values into cond — always pass them as vals.
type queryBuilder struct {
	conditions []string
	args       []any
}

// add appends a condition and its associated bind values. The condition string
// must use ? as a single placeholder token; add replaces each ? with the
// appropriate $N index automatically.
func (b *queryBuilder) add(cond string, vals ...any) {
	// Replace ? tokens with $N sequentially.
	result := make([]byte, 0, len(cond)+len(vals)*3)
	argN := len(b.args) + 1
	for i := 0; i < len(cond); i++ {
		if cond[i] == '?' {
			result = append(result, []byte(fmt.Sprintf("$%d", argN))...)
			argN++
		} else {
			result = append(result, cond[i])
		}
	}
	b.conditions = append(b.conditions, string(result))
	b.args = append(b.args, vals...)
}

// whereClause joins all accumulated conditions with AND.
func (b *queryBuilder) whereClause() string {
	return strings.Join(b.conditions, " AND ")
}

// Search returns videos with status=ready that match the given query and optional
// category filter. When both query and category_id are provided the results are
// filtered by AND semantics (video must match keyword AND belong to the category).
// Matches against title (full-text) and video_tags.tag (exact).
// When a keyword query is present, results are ordered by ts_rank DESC for relevance.
func (r *SearchRepository) Search(ctx context.Context, p SearchParams) ([]SearchVideo, error) {
	if p.Limit <= 0 {
		p.Limit = 20
	}
	if p.Offset < 0 {
		p.Offset = 0
	}

	var qb queryBuilder

	qb.add("v.status = 'ready'")

	if p.Query != "" {
		// Match against title (full-text) OR video_tags.tag (exact).
		// The subquery for tag matching uses EXISTS for efficiency.
		// IMPORTANT: p.Query is passed as bind values only — never interpolated.
		qb.add(
			"(to_tsvector('english', v.title) @@ plainto_tsquery('english', ?) OR EXISTS (SELECT 1 FROM video_tags vt WHERE vt.video_id = v.id AND vt.tag = ?))",
			p.Query, p.Query,
		)
	}

	if p.CategoryID != nil {
		qb.add("v.category_id = ?", *p.CategoryID)
	}

	// When a full-text query is present, rank by relevance (ts_rank) so the
	// most relevant results appear first. Fall back to recency for ties and
	// for pure browse queries (no keyword).
	var orderClause string
	if p.Query != "" {
		// Pass p.Query again as a bind value for the rank expression.
		rankIdx := len(qb.args) + 1
		orderClause = fmt.Sprintf(
			"ts_rank(to_tsvector('english', v.title), plainto_tsquery('english', $%d)) DESC, v.created_at DESC",
			rankIdx,
		)
		qb.args = append(qb.args, p.Query)
	} else {
		orderClause = "v.created_at DESC"
	}

	limitIdx := len(qb.args) + 1
	offsetIdx := limitIdx + 1
	query := fmt.Sprintf(`
SELECT v.id,
       v.title,
       v.thumbnail_url,
       v.view_count,
       u.username,
       v.created_at
FROM   videos v
JOIN   users  u ON u.id = v.uploader_id
WHERE  %s
ORDER BY %s
LIMIT  $%d OFFSET $%d`, qb.whereClause(), orderClause, limitIdx, offsetIdx)

	qb.args = append(qb.args, p.Limit, p.Offset)

	rows, err := r.db.QueryContext(ctx, query, qb.args...)
	if err != nil {
		return nil, fmt.Errorf("search videos: %w", err)
	}
	defer rows.Close()

	return scanSearchVideos(rows)
}

// GetRecent returns videos with status=ready ordered by created_at DESC.
func (r *SearchRepository) GetRecent(ctx context.Context, limit int) ([]SearchVideo, error) {
	if limit <= 0 {
		limit = 20
	}

	const selectSQL = `
SELECT v.id,
       v.title,
       v.thumbnail_url,
       v.view_count,
       u.username,
       v.created_at
FROM   videos v
JOIN   users  u ON u.id = v.uploader_id
WHERE  v.status = 'ready'
ORDER BY v.created_at DESC
LIMIT  $1`

	rows, err := r.db.QueryContext(ctx, selectSQL, limit)
	if err != nil {
		return nil, fmt.Errorf("get recent videos: %w", err)
	}
	defer rows.Close()

	return scanSearchVideos(rows)
}

// GetPopular returns videos with status=ready ordered by view_count DESC.
func (r *SearchRepository) GetPopular(ctx context.Context, limit int) ([]SearchVideo, error) {
	if limit <= 0 {
		limit = 20
	}

	const selectSQL = `
SELECT v.id,
       v.title,
       v.thumbnail_url,
       v.view_count,
       u.username,
       v.created_at
FROM   videos v
JOIN   users  u ON u.id = v.uploader_id
WHERE  v.status = 'ready'
ORDER BY v.view_count DESC
LIMIT  $1`

	rows, err := r.db.QueryContext(ctx, selectSQL, limit)
	if err != nil {
		return nil, fmt.Errorf("get popular videos: %w", err)
	}
	defer rows.Close()

	return scanSearchVideos(rows)
}

// GetAllCategories returns all categories ordered by name.
func (r *SearchRepository) GetAllCategories(ctx context.Context) ([]Category, error) {
	const selectSQL = `
SELECT id, name
FROM   categories
ORDER BY name`

	rows, err := r.db.QueryContext(ctx, selectSQL)
	if err != nil {
		return nil, fmt.Errorf("get all categories: %w", err)
	}
	defer rows.Close()

	var cats []Category
	for rows.Next() {
		var c Category
		if err := rows.Scan(&c.ID, &c.Name); err != nil {
			return nil, fmt.Errorf("scan category row: %w", err)
		}
		cats = append(cats, c)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate category rows: %w", err)
	}
	if cats == nil {
		cats = []Category{}
	}
	return cats, nil
}

// GetByCategory returns videos with status=ready that belong to the given
// category, ordered by created_at DESC.
func (r *SearchRepository) GetByCategory(ctx context.Context, categoryID, limit, offset int) ([]SearchVideo, error) {
	if limit <= 0 {
		limit = 20
	}
	if offset < 0 {
		offset = 0
	}

	const selectSQL = `
SELECT v.id,
       v.title,
       v.thumbnail_url,
       v.view_count,
       u.username,
       v.created_at
FROM   videos v
JOIN   users  u ON u.id = v.uploader_id
WHERE  v.status = 'ready'
  AND  v.category_id = $1
ORDER BY v.created_at DESC
LIMIT  $2 OFFSET $3`

	rows, err := r.db.QueryContext(ctx, selectSQL, categoryID, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("get videos by category: %w", err)
	}
	defer rows.Close()

	return scanSearchVideos(rows)
}

// scanSearchVideos scans a *sql.Rows result into a slice of SearchVideo.
func scanSearchVideos(rows interface {
	Next() bool
	Scan(dest ...any) error
	Err() error
}) ([]SearchVideo, error) {
	var videos []SearchVideo
	for rows.Next() {
		var v SearchVideo
		if err := rows.Scan(
			&v.ID,
			&v.Title,
			&v.ThumbnailURL,
			&v.ViewCount,
			&v.UploaderUsername,
			&v.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("scan search video row: %w", err)
		}
		videos = append(videos, v)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate search video rows: %w", err)
	}
	if videos == nil {
		videos = []SearchVideo{}
	}
	return videos, nil
}
