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

// ─── Stub PlaylistStore ───────────────────────────────────────────────────────

type stubPlaylistStore struct {
	createdPlaylist       *repository.PlaylistSummary
	createErr             error
	playlistDetail        *repository.PlaylistDetail
	getByIDErr            error
	ownerList             []repository.PlaylistSummary
	listByOwnerErr        error
	usernameList          []repository.PlaylistSummary
	listByUsernameErr     error
	updatedPlaylist       *repository.PlaylistSummary
	updateTitleErr        error
	deleted               bool
	deleteErr             error
	videoAdded            bool
	addVideoErr           error
	videoRemoved          bool
	removeVideoErr        error
}

func (s *stubPlaylistStore) Create(_ context.Context, _, _ string) (*repository.PlaylistSummary, error) {
	return s.createdPlaylist, s.createErr
}

func (s *stubPlaylistStore) GetByID(_ context.Context, _ string) (*repository.PlaylistDetail, error) {
	return s.playlistDetail, s.getByIDErr
}

func (s *stubPlaylistStore) ListByOwnerID(_ context.Context, _ string) ([]repository.PlaylistSummary, error) {
	return s.ownerList, s.listByOwnerErr
}

func (s *stubPlaylistStore) ListByOwnerUsername(_ context.Context, _ string) ([]repository.PlaylistSummary, error) {
	return s.usernameList, s.listByUsernameErr
}

func (s *stubPlaylistStore) UpdateTitle(_ context.Context, _, _, _ string) (*repository.PlaylistSummary, error) {
	return s.updatedPlaylist, s.updateTitleErr
}

func (s *stubPlaylistStore) Delete(_ context.Context, _, _ string) (bool, error) {
	return s.deleted, s.deleteErr
}

func (s *stubPlaylistStore) AddVideo(_ context.Context, _, _, _ string) (bool, error) {
	return s.videoAdded, s.addVideoErr
}

func (s *stubPlaylistStore) RemoveVideo(_ context.Context, _, _, _ string) (bool, error) {
	return s.videoRemoved, s.removeVideoErr
}

// ─── Stub PlaylistUserProvider ────────────────────────────────────────────────

type stubPlaylistUserProvider struct {
	user    *repository.User
	userErr error
}

func (s *stubPlaylistUserProvider) GetByFirebaseUID(_ context.Context, _ string) (*repository.User, error) {
	return s.user, s.userErr
}

// ─── Test helpers ─────────────────────────────────────────────────────────────

const (
	testPlaylistID  = "00000000-0000-0000-0000-000000000010"
	testPlaylistVID = "00000000-0000-0000-0000-000000000011"
)

func makePlaylistSummary(id, title, ownerUsername string) *repository.PlaylistSummary {
	return &repository.PlaylistSummary{
		ID:            id,
		Title:         title,
		OwnerUsername: ownerUsername,
		CreatedAt:     time.Now().Truncate(time.Second),
	}
}

func makePlaylistDetail(id, title, ownerUsername string, videos []repository.PlaylistVideoItem) *repository.PlaylistDetail {
	if videos == nil {
		videos = []repository.PlaylistVideoItem{}
	}
	return &repository.PlaylistDetail{
		ID:            id,
		Title:         title,
		OwnerUsername: ownerUsername,
		Videos:        videos,
	}
}

func authPlaylistRequest(r *http.Request) *http.Request {
	claims := &auth.TokenClaims{UID: "firebase-uid-1"}
	return withClaims(r, claims)
}

func defaultPlaylistUser() *repository.User {
	return &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
}

// ─── POST /api/playlists ──────────────────────────────────────────────────────

func TestCreatePlaylistHandler_POST_Success_Returns201(t *testing.T) {
	playlist := makePlaylistSummary(testPlaylistID, "My Playlist", "alice")
	store := &stubPlaylistStore{createdPlaylist: playlist}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewCreatePlaylistHandler(store, users)

	body := bytes.NewBufferString(`{"title":"My Playlist"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists", body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Errorf("expected 201, got %d", rec.Code)
	}

	var resp handler.PlaylistSummaryResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.Title != "My Playlist" {
		t.Errorf("Title: got %q, want My Playlist", resp.Title)
	}
	if resp.OwnerUsername != "alice" {
		t.Errorf("OwnerUsername: got %q, want alice", resp.OwnerUsername)
	}
}

func TestCreatePlaylistHandler_POST_NoAuth_Returns401(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewCreatePlaylistHandler(store, users)

	body := bytes.NewBufferString(`{"title":"My Playlist"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/playlists", body)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestCreatePlaylistHandler_POST_EmptyTitle_Returns422(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewCreatePlaylistHandler(store, users)

	body := bytes.NewBufferString(`{"title":"   "}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists", body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422, got %d", rec.Code)
	}
}

func TestCreatePlaylistHandler_POST_TitleTooLong_Returns422(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewCreatePlaylistHandler(store, users)

	longTitle := strings.Repeat("a", 256)
	body := bytes.NewBufferString(`{"title":"` + longTitle + `"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists", body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422, got %d", rec.Code)
	}
}

func TestCreatePlaylistHandler_POST_InvalidJSON_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewCreatePlaylistHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists", strings.NewReader("not-json")))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestCreatePlaylistHandler_POST_StoreError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{createErr: errors.New("db error")}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewCreatePlaylistHandler(store, users)

	body := bytes.NewBufferString(`{"title":"My Playlist"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists", body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestCreatePlaylistHandler_POST_UserNotFound_Returns404(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: nil}
	h := handler.NewCreatePlaylistHandler(store, users)

	body := bytes.NewBufferString(`{"title":"My Playlist"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists", body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestCreatePlaylistHandler_POST_UserProviderError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{userErr: errors.New("db error")}
	h := handler.NewCreatePlaylistHandler(store, users)

	body := bytes.NewBufferString(`{"title":"My Playlist"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists", body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestCreatePlaylistHandler_WrongMethod_Returns405(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewCreatePlaylistHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/playlists", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

// ─── GET /api/me/playlists ────────────────────────────────────────────────────

func TestMePlaylistsHandler_GET_ReturnsEmptyList(t *testing.T) {
	store := &stubPlaylistStore{ownerList: []repository.PlaylistSummary{}}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewMePlaylistsHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodGet, "/api/me/playlists", nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	var body []handler.PlaylistSummaryResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(body) != 0 {
		t.Errorf("expected empty list, got %d", len(body))
	}
}

func TestMePlaylistsHandler_GET_ReturnsPlaylists(t *testing.T) {
	playlists := []repository.PlaylistSummary{
		*makePlaylistSummary("pl-1", "First", "alice"),
		*makePlaylistSummary("pl-2", "Second", "alice"),
	}
	store := &stubPlaylistStore{ownerList: playlists}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewMePlaylistsHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodGet, "/api/me/playlists", nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	var body []handler.PlaylistSummaryResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(body) != 2 {
		t.Errorf("expected 2 playlists, got %d", len(body))
	}
	if body[0].Title != "First" {
		t.Errorf("Title[0]: got %q", body[0].Title)
	}
}

func TestMePlaylistsHandler_GET_NoAuth_Returns401(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewMePlaylistsHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/me/playlists", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestMePlaylistsHandler_GET_StoreError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{listByOwnerErr: errors.New("db error")}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewMePlaylistsHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodGet, "/api/me/playlists", nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestMePlaylistsHandler_WrongMethod_Returns405(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewMePlaylistsHandler(store, users)

	req := httptest.NewRequest(http.MethodPost, "/api/me/playlists", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

// ─── GET /api/users/:username/playlists ───────────────────────────────────────

func TestUserPlaylistsHandler_GET_ReturnsPlaylists(t *testing.T) {
	playlists := []repository.PlaylistSummary{
		*makePlaylistSummary("pl-1", "Alice's List", "alice"),
	}
	store := &stubPlaylistStore{usernameList: playlists}
	h := handler.NewUserPlaylistsHandler(store)

	req := httptest.NewRequest(http.MethodGet, "/api/users/alice/playlists", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	var body []handler.PlaylistSummaryResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(body) != 1 {
		t.Errorf("expected 1 playlist, got %d", len(body))
	}
}

func TestUserPlaylistsHandler_GET_StoreError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{listByUsernameErr: errors.New("db error")}
	h := handler.NewUserPlaylistsHandler(store)

	req := httptest.NewRequest(http.MethodGet, "/api/users/alice/playlists", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestUserPlaylistsHandler_WrongMethod_Returns405(t *testing.T) {
	store := &stubPlaylistStore{}
	h := handler.NewUserPlaylistsHandler(store)

	req := httptest.NewRequest(http.MethodPost, "/api/users/alice/playlists", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

// ─── GET /api/playlists/:id ───────────────────────────────────────────────────

func TestPlaylistByIDHandler_GET_ReturnsPlaylist(t *testing.T) {
	thumbURL := "https://cdn.example.com/thumb.jpg"
	detail := makePlaylistDetail(testPlaylistID, "Test Playlist", "alice",
		[]repository.PlaylistVideoItem{
			{ID: testPlaylistVID, Title: "Video 1", ThumbnailURL: &thumbURL, Position: 1},
		})
	store := &stubPlaylistStore{playlistDetail: detail}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/playlists/"+testPlaylistID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var resp handler.PlaylistDetailResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.Title != "Test Playlist" {
		t.Errorf("Title: got %q", resp.Title)
	}
	if resp.OwnerUsername != "alice" {
		t.Errorf("OwnerUsername: got %q", resp.OwnerUsername)
	}
	if len(resp.Videos) != 1 {
		t.Errorf("Videos: expected 1, got %d", len(resp.Videos))
	}
	if resp.Videos[0].ID != testPlaylistVID {
		t.Errorf("Videos[0].ID: got %q", resp.Videos[0].ID)
	}
}

func TestPlaylistByIDHandler_GET_NotFound_Returns404(t *testing.T) {
	store := &stubPlaylistStore{playlistDetail: nil}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/playlists/"+testPlaylistID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_GET_InvalidID_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/playlists/not-a-uuid", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_GET_StoreError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{getByIDErr: errors.New("db error")}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/playlists/"+testPlaylistID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_GET_ContentType_IsJSON(t *testing.T) {
	detail := makePlaylistDetail(testPlaylistID, "Test", "alice", nil)
	store := &stubPlaylistStore{playlistDetail: detail}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/playlists/"+testPlaylistID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type: got %q, want application/json", ct)
	}
}

func TestPlaylistByIDHandler_GET_EmptyVideos_ReturnsEmptyArray(t *testing.T) {
	detail := makePlaylistDetail(testPlaylistID, "Empty", "alice", []repository.PlaylistVideoItem{})
	store := &stubPlaylistStore{playlistDetail: detail}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/playlists/"+testPlaylistID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	var resp handler.PlaylistDetailResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.Videos == nil || len(resp.Videos) != 0 {
		t.Errorf("expected empty videos array, got %v", resp.Videos)
	}
}

// ─── PUT /api/playlists/:id ───────────────────────────────────────────────────

func TestPlaylistByIDHandler_PUT_Success_Returns200(t *testing.T) {
	updated := makePlaylistSummary(testPlaylistID, "Renamed", "alice")
	store := &stubPlaylistStore{updatedPlaylist: updated}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	body := bytes.NewBufferString(`{"title":"Renamed"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPut, "/api/playlists/"+testPlaylistID, body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var resp handler.PlaylistSummaryResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.Title != "Renamed" {
		t.Errorf("Title: got %q", resp.Title)
	}
}

func TestPlaylistByIDHandler_PUT_NoAuth_Returns401(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	body := bytes.NewBufferString(`{"title":"New"}`)
	req := httptest.NewRequest(http.MethodPut, "/api/playlists/"+testPlaylistID, body)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_PUT_EmptyTitle_Returns422(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	body := bytes.NewBufferString(`{"title":""}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPut, "/api/playlists/"+testPlaylistID, body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_PUT_TitleTooLong_Returns422(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	longTitle := strings.Repeat("a", 256)
	body := bytes.NewBufferString(`{"title":"` + longTitle + `"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPut, "/api/playlists/"+testPlaylistID, body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_PUT_NotFound_Returns404(t *testing.T) {
	store := &stubPlaylistStore{updatedPlaylist: nil}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	body := bytes.NewBufferString(`{"title":"New Title"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPut, "/api/playlists/"+testPlaylistID, body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_PUT_Forbidden_Returns403(t *testing.T) {
	store := &stubPlaylistStore{updateTitleErr: repository.ErrForbidden}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	body := bytes.NewBufferString(`{"title":"New Title"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPut, "/api/playlists/"+testPlaylistID, body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Errorf("expected 403, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_PUT_StoreError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{updateTitleErr: errors.New("db error")}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	body := bytes.NewBufferString(`{"title":"New Title"}`)
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPut, "/api/playlists/"+testPlaylistID, body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_PUT_InvalidJSON_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodPut, "/api/playlists/"+testPlaylistID, strings.NewReader("invalid")))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

// ─── DELETE /api/playlists/:id ────────────────────────────────────────────────

func TestPlaylistByIDHandler_DELETE_Success_Returns204(t *testing.T) {
	store := &stubPlaylistStore{deleted: true}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete, "/api/playlists/"+testPlaylistID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Errorf("expected 204, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_DELETE_NoAuth_Returns401(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/playlists/"+testPlaylistID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_DELETE_Forbidden_Returns403(t *testing.T) {
	store := &stubPlaylistStore{deleteErr: repository.ErrForbidden}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete, "/api/playlists/"+testPlaylistID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Errorf("expected 403, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_DELETE_NotFound_Returns404(t *testing.T) {
	store := &stubPlaylistStore{deleted: false}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete, "/api/playlists/"+testPlaylistID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_DELETE_StoreError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{deleteErr: errors.New("db error")}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete, "/api/playlists/"+testPlaylistID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_DELETE_InvalidID_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete, "/api/playlists/not-a-uuid", nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestPlaylistByIDHandler_UnsupportedMethod_Returns405(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewPlaylistByIDHandler(store, users)

	req := httptest.NewRequest(http.MethodPost, "/api/playlists/"+testPlaylistID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

// ─── POST /api/playlists/:id/videos ──────────────────────────────────────────

func TestAddVideoToPlaylistHandler_POST_Success_Returns204(t *testing.T) {
	store := &stubPlaylistStore{videoAdded: true}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	body, _ := json.Marshal(map[string]string{"video_id": testPlaylistVID})
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists/"+testPlaylistID+"/videos", bytes.NewReader(body)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Errorf("expected 204, got %d", rec.Code)
	}
}

func TestAddVideoToPlaylistHandler_POST_NoAuth_Returns401(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	body, _ := json.Marshal(map[string]string{"video_id": testPlaylistVID})
	req := httptest.NewRequest(http.MethodPost, "/api/playlists/"+testPlaylistID+"/videos", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestAddVideoToPlaylistHandler_POST_InvalidVideoID_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	body, _ := json.Marshal(map[string]string{"video_id": "not-a-uuid"})
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists/"+testPlaylistID+"/videos", bytes.NewReader(body)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestAddVideoToPlaylistHandler_POST_Forbidden_Returns403(t *testing.T) {
	store := &stubPlaylistStore{addVideoErr: repository.ErrForbidden}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	body, _ := json.Marshal(map[string]string{"video_id": testPlaylistVID})
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists/"+testPlaylistID+"/videos", bytes.NewReader(body)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Errorf("expected 403, got %d", rec.Code)
	}
}

func TestAddVideoToPlaylistHandler_POST_PlaylistNotFound_Returns404(t *testing.T) {
	store := &stubPlaylistStore{videoAdded: false}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	body, _ := json.Marshal(map[string]string{"video_id": testPlaylistVID})
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists/"+testPlaylistID+"/videos", bytes.NewReader(body)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestAddVideoToPlaylistHandler_POST_StoreError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{addVideoErr: errors.New("db error")}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	body, _ := json.Marshal(map[string]string{"video_id": testPlaylistVID})
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists/"+testPlaylistID+"/videos", bytes.NewReader(body)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestAddVideoToPlaylistHandler_POST_InvalidPlaylistID_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	body, _ := json.Marshal(map[string]string{"video_id": testPlaylistVID})
	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists/not-a-uuid/videos", bytes.NewReader(body)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestAddVideoToPlaylistHandler_WrongMethod_Returns405(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/playlists/"+testPlaylistID+"/videos", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestAddVideoToPlaylistHandler_POST_InvalidJSON_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewAddVideoToPlaylistHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodPost, "/api/playlists/"+testPlaylistID+"/videos", strings.NewReader("not-json")))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

// ─── DELETE /api/playlists/:id/videos/:video_id ───────────────────────────────

func TestRemoveVideoFromPlaylistHandler_DELETE_Success_Returns204(t *testing.T) {
	store := &stubPlaylistStore{videoRemoved: true}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewRemoveVideoFromPlaylistHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete,
		"/api/playlists/"+testPlaylistID+"/videos/"+testPlaylistVID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Errorf("expected 204, got %d", rec.Code)
	}
}

func TestRemoveVideoFromPlaylistHandler_DELETE_NoAuth_Returns401(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewRemoveVideoFromPlaylistHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete,
		"/api/playlists/"+testPlaylistID+"/videos/"+testPlaylistVID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestRemoveVideoFromPlaylistHandler_DELETE_Forbidden_Returns403(t *testing.T) {
	store := &stubPlaylistStore{removeVideoErr: repository.ErrForbidden}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewRemoveVideoFromPlaylistHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete,
		"/api/playlists/"+testPlaylistID+"/videos/"+testPlaylistVID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Errorf("expected 403, got %d", rec.Code)
	}
}

func TestRemoveVideoFromPlaylistHandler_DELETE_NotFound_Returns404(t *testing.T) {
	store := &stubPlaylistStore{videoRemoved: false}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewRemoveVideoFromPlaylistHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete,
		"/api/playlists/"+testPlaylistID+"/videos/"+testPlaylistVID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestRemoveVideoFromPlaylistHandler_DELETE_StoreError_Returns500(t *testing.T) {
	store := &stubPlaylistStore{removeVideoErr: errors.New("db error")}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewRemoveVideoFromPlaylistHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete,
		"/api/playlists/"+testPlaylistID+"/videos/"+testPlaylistVID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestRemoveVideoFromPlaylistHandler_DELETE_InvalidPlaylistID_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewRemoveVideoFromPlaylistHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete,
		"/api/playlists/not-a-uuid/videos/"+testPlaylistVID, nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestRemoveVideoFromPlaylistHandler_DELETE_InvalidVideoID_Returns400(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{user: defaultPlaylistUser()}
	h := handler.NewRemoveVideoFromPlaylistHandler(store, users)

	req := authPlaylistRequest(httptest.NewRequest(http.MethodDelete,
		"/api/playlists/"+testPlaylistID+"/videos/not-a-uuid", nil))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestRemoveVideoFromPlaylistHandler_WrongMethod_Returns405(t *testing.T) {
	store := &stubPlaylistStore{}
	users := &stubPlaylistUserProvider{}
	h := handler.NewRemoveVideoFromPlaylistHandler(store, users)

	req := httptest.NewRequest(http.MethodGet,
		"/api/playlists/"+testPlaylistID+"/videos/"+testPlaylistVID, nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}
