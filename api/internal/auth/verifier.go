// Package auth provides Firebase ID-token verification.
package auth

import (
	"context"
	"fmt"
	"os"

	firebase "firebase.google.com/go/v4"
	firebaseAuth "firebase.google.com/go/v4/auth"
)

// TokenClaims holds the verified claims extracted from a Firebase ID token.
type TokenClaims struct {
	// UID is the Firebase user UID.
	UID string
	// Email is the user's email address as recorded in Firebase Auth.
	Email string
	// Picture is the user's profile photo URL from the Firebase/Google ID
	// token "picture" claim.  Empty string when not present.
	Picture string
}

// TokenVerifier is the interface that wraps Firebase token verification.
// The interface makes the auth middleware unit-testable by allowing tests to
// inject a stub that does not call Firebase.
type TokenVerifier interface {
	VerifyIDToken(ctx context.Context, idToken string) (*TokenClaims, error)
}

// FirebaseVerifier is the production TokenVerifier backed by the Firebase
// Admin SDK.  It reads FIREBASE_PROJECT_ID from the environment.
type FirebaseVerifier struct {
	client *firebaseAuth.Client
}

// NewFirebaseVerifier creates a FirebaseVerifier.  When running on Cloud Run
// the SDK uses Application Default Credentials automatically; no service-account
// file is needed.
func NewFirebaseVerifier(ctx context.Context) (*FirebaseVerifier, error) {
	projectID := os.Getenv("FIREBASE_PROJECT_ID")
	if projectID == "" {
		return nil, fmt.Errorf("FIREBASE_PROJECT_ID env var is not set")
	}

	app, err := firebase.NewApp(ctx, &firebase.Config{ProjectID: projectID})
	if err != nil {
		return nil, fmt.Errorf("firebase app: %w", err)
	}

	client, err := app.Auth(ctx)
	if err != nil {
		return nil, fmt.Errorf("firebase auth client: %w", err)
	}

	return &FirebaseVerifier{client: client}, nil
}

// VerifyIDToken validates the token against Firebase and returns the verified
// claims.  Returns an error if the token is expired, malformed, or issued for a
// different project.
func (v *FirebaseVerifier) VerifyIDToken(ctx context.Context, idToken string) (*TokenClaims, error) {
	t, err := v.client.VerifyIDToken(ctx, idToken)
	if err != nil {
		return nil, fmt.Errorf("verify firebase id token: %w", err)
	}

	email, _ := t.Claims["email"].(string)
	// The "picture" claim is a user-controlled URL from the Firebase/Google ID
	// token.  Firebase verifies the token signature so the URL cannot be forged
	// by a third party, but a user may point their Google profile picture at any
	// external host.  The URL is stored as avatar_url and rendered client-side
	// via <Image src={avatarUrl}>.  For the current static-export frontend this
	// is low risk (no server-side proxying).  If server-side image optimisation
	// is ever enabled, this should be validated against an allowed-domain list
	// (e.g. lh3.googleusercontent.com) to prevent SSRF.
	picture, _ := t.Claims["picture"].(string)

	return &TokenClaims{
		UID:     t.UID,
		Email:   email,
		Picture: picture,
	}, nil
}
