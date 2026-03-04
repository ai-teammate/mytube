package repository

import "errors"

// ErrNotFound is returned by repository methods when the requested resource
// does not exist.
var ErrNotFound = errors.New("not found")

// ErrForbidden is returned by repository methods when the requesting user is
// authenticated but does not own the resource they are trying to modify.
var ErrForbidden = errors.New("forbidden")
