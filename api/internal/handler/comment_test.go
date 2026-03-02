package handler_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── stub CommentStore ────────────────────────────────────────────────────────

type stubCommentStore struct {
	comment    *repository.Comment
	createErr  error
	comments   []repository.Comment
	listErr    error
	deleted    bool
	deleteErr  error
}

func (s *stubCommentStore) Create(_ context.Context, _ repository.CreateCommentParams) (*repository.Comment, error) {
	return s.comment, s.createErr
}

func (s *stubCommentStore) ListByVideoID(_ context.Context, _ string) ([]repository.Comment, error) {
	return s.comments, s.listErr
}

func (s *stubCommentStore) Delete(_ context.Context, _, _ string) (bool, error) {
	return s.deleted, s.deleteErr
}

// ─── stub CommentUserProvider ─────────────────────────────────────────────────

type stubCommentUserProvider struct {
	user    *repository.User
	userErr error
}

func (s *stubCommentUserProvider) GetByFirebaseUID(_ context.Context, _ string) (*repository.User, error) {
	return s.user, s.userErr
}

// ─── helpers ──────────────────────────────────────────────────────────────────

const commentTestVideoID = "00000000-0000-0000-0000-000000000002"
const commentTestCommentID = "00000000-0000-0000-0000-000000000003"

func makeComment(id, body, authorUsername string) *repository.Comment {
	return &repository.Comment{
		ID:             id,
		Body:           body,
		AuthorID:       "user-1",
		AuthorUsername: authorUsername,
		CreatedAt:      time.Now().Truncate(time.Second),
	}
}

func authCommentRequest(r *http.Request) *http.Request {
	claims := &auth.TokenClaims{UID: "firebase-uid-1"}
	return withClaims(r, claims)
}

// ─── GET /api/videos/:id/comments tests ──────────────────────────────────────

func TestVideoCommentsHandler_GET_ReturnsEmptyList(t *testing.T) {
	store := &stubCommentStore{comments: []repository.Comment{}}
	users := &stubCommentUserProvider{}
	h := handler.NewVideoCommentsHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+commentTestVideoID+"/comments", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body []handler.CommentResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(body) != 0 {
		t.Errorf("expected empty array, got %d items", len(body))
	}
}

func TestVideoCommentsHandler_GET_ReturnsComments(t *testing.T) {
	avatarURL := "https://example.com/avatar.png"
	now := time.Now().Truncate(time.Second)
	store := &stubCommentStore{
		comments: []repository.Comment{
			{
				ID:              "c1",
				Body:            "First comment",
				AuthorID:        "user-1",
				AuthorUsername:  "alice",
				AuthorAvatarURL: &avatarURL,
				CreatedAt:       now,
			},
		},
	}
	users := &stubCommentUserProvider{}
	h := handler.NewVideoCommentsHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+commentTestVideoID+"/comments", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body []handler.CommentResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(body) != 1 {
		t.Fatalf("expected 1 comment, got %d", len(body))
	}
	if body[0].ID != "c1" {
		t.Errorf("ID: got %q, want c1", body[0].ID)
	}
	if body[0].Body != "First comment" {
		t.Errorf("Body: got %q", body[0].Body)
	}
	if body[0].Author.Username != "alice" {
		t.Errorf("Author.Username: got %q", body[0].Author.Username)
	}
	if body[0].Author.AvatarURL == nil || *body[0].Author.AvatarURL != avatarURL {
		t.Errorf("Author.AvatarURL: expected %q", avatarURL)
	}
}

func TestVideoCommentsHandler_GET_ListError_Returns500(t *testing.T) {
	store := &stubCommentStore{listErr: errors.New("db error")}
	users := &stubCommentUserProvider{}
	h := handler.NewVideoCommentsHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+commentTestVideoID+"/comments", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_GET_InvalidVideoID_Returns400(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{}
	h := handler.NewVideoCommentsHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/not-a-uuid/comments", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_GET_EmptyVideoID_Returns400(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{}
	h := handler.NewVideoCommentsHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos//comments", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_UnsupportedMethod_Returns405(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{}
	h := handler.NewVideoCommentsHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/videos/"+commentTestVideoID+"/comments", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
	if allow := rec.Header().Get("Allow"); !strings.Contains(allow, "GET") {
		t.Errorf("Allow header: got %q, want to contain GET", allow)
	}
}

// ─── POST /api/videos/:id/comments tests ─────────────────────────────────────

func TestVideoCommentsHandler_POST_NoAuth_Returns401(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{}
	h := handler.NewVideoCommentsHandler(store, users)

	body := strings.NewReader(`{"body":"hello"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", body)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_POST_EmptyBody_Returns422(t *testing.T) {
	store := &stubCommentStore{comment: makeComment("c1", "hello", "alice")}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewVideoCommentsHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]string{"body": "   "})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", bytes.NewReader(bodyBytes))
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 for empty body, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_POST_BodyTooLong_Returns422(t *testing.T) {
	longBody := strings.Repeat("a", 2001)
	store := &stubCommentStore{}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewVideoCommentsHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]string{"body": longBody})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", bytes.NewReader(bodyBytes))
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 for body too long, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_POST_BodyAtMaxLength_Returns201(t *testing.T) {
	maxBody := strings.Repeat("a", 2000)
	store := &stubCommentStore{comment: makeComment("c1", maxBody, "alice")}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewVideoCommentsHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]string{"body": maxBody})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", bytes.NewReader(bodyBytes))
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Errorf("expected 201, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_POST_Success_Returns201WithComment(t *testing.T) {
	comment := makeComment("c-new", "Great video!", "alice")
	store := &stubCommentStore{comment: comment}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewVideoCommentsHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]string{"body": "Great video!"})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", bytes.NewReader(bodyBytes))
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Errorf("expected 201, got %d", rec.Code)
	}

	var resp handler.CommentResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.ID != "c-new" {
		t.Errorf("ID: got %q, want c-new", resp.ID)
	}
	if resp.Body != "Great video!" {
		t.Errorf("Body: got %q", resp.Body)
	}
	if resp.Author.Username != "alice" {
		t.Errorf("Author.Username: got %q", resp.Author.Username)
	}
}

func TestVideoCommentsHandler_POST_UserNotFound_Returns404(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{user: nil}
	h := handler.NewVideoCommentsHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]string{"body": "hello"})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", bytes.NewReader(bodyBytes))
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_POST_UserProviderError_Returns500(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{userErr: errors.New("db error")}
	h := handler.NewVideoCommentsHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]string{"body": "hello"})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", bytes.NewReader(bodyBytes))
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_POST_CreateError_Returns500(t *testing.T) {
	store := &stubCommentStore{createErr: errors.New("create failed")}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewVideoCommentsHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]string{"body": "hello"})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", bytes.NewReader(bodyBytes))
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_POST_InvalidJSON_Returns400(t *testing.T) {
	store := &stubCommentStore{}
	user := &repository.User{ID: "user-1"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewVideoCommentsHandler(store, users)

	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+commentTestVideoID+"/comments", strings.NewReader("not-json"))
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

// ─── DELETE /api/comments/:id tests ──────────────────────────────────────────

func TestDeleteCommentHandler_DELETE_Success_Returns204(t *testing.T) {
	store := &stubCommentStore{deleted: true}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/comments/"+commentTestCommentID, nil)
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Errorf("expected 204, got %d", rec.Code)
	}
}

func TestDeleteCommentHandler_DELETE_NotFound_Returns404(t *testing.T) {
	store := &stubCommentStore{deleted: false}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/comments/"+commentTestCommentID, nil)
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestDeleteCommentHandler_DELETE_NoAuth_Returns401(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/comments/"+commentTestCommentID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestDeleteCommentHandler_DELETE_UserNotFound_Returns404(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{user: nil}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/comments/"+commentTestCommentID, nil)
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestDeleteCommentHandler_DELETE_DeleteError_Returns500(t *testing.T) {
	store := &stubCommentStore{deleteErr: errors.New("db error")}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/comments/"+commentTestCommentID, nil)
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestDeleteCommentHandler_DELETE_UserProviderError_Returns500(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{userErr: errors.New("db error")}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/comments/"+commentTestCommentID, nil)
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestDeleteCommentHandler_DELETE_InvalidCommentID_Returns400(t *testing.T) {
	store := &stubCommentStore{}
	user := &repository.User{ID: "user-1"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/comments/not-a-uuid", nil)
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestDeleteCommentHandler_DELETE_EmptyCommentID_Returns400(t *testing.T) {
	store := &stubCommentStore{}
	user := &repository.User{ID: "user-1"}
	users := &stubCommentUserProvider{user: user}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/comments/", nil)
	req = authCommentRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestDeleteCommentHandler_WrongMethod_Returns405(t *testing.T) {
	store := &stubCommentStore{}
	users := &stubCommentUserProvider{}
	h := handler.NewDeleteCommentHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/comments/"+commentTestCommentID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestVideoCommentsHandler_GET_ContentType_IsJSON(t *testing.T) {
	store := &stubCommentStore{comments: []repository.Comment{}}
	users := &stubCommentUserProvider{}
	h := handler.NewVideoCommentsHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+commentTestVideoID+"/comments", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type: got %q, want application/json", ct)
	}
}
