-- 0003_widen_username.up.sql
-- Widen users.username from VARCHAR(50) to VARCHAR(100) to avoid silent
-- truncation of email-prefix usernames longer than 50 chars (RFC 5321 allows
-- up to 64 chars in the local part).  Add a UNIQUE constraint so duplicate
-- default usernames are rejected at the database level.

ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(100);

ALTER TABLE users ADD CONSTRAINT users_username_unique UNIQUE (username);
