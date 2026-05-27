package handler

import (
	"log"
	"net/http"

	"github.com/ai-teammate/mytube/api/internal/middleware"
)

// avatarDeleteHandler implements DELETE /api/me/avatar.
type avatarDeleteHandler struct {
	users AvatarUserProvider
}

// NewAvatarDeleteHandler returns an http.Handler for DELETE /api/me/avatar.
func NewAvatarDeleteHandler(users AvatarUserProvider) http.Handler {
	return &avatarDeleteHandler{users: users}
}

func (h *avatarDeleteHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	user, err := h.users.ClearAvatarURL(r.Context(), claims.UID)
	if err != nil {
		log.Printf("DELETE /api/me/avatar: clear avatar_url for user %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if user == nil {
		writeJSONError(w, "user not found", http.StatusNotFound)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
