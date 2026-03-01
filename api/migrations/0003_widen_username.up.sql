-- 0003_widen_username.up.sql
-- Widen users.username from VARCHAR(50) to VARCHAR(100) to avoid silent
-- truncation of email-prefix usernames longer than 50 chars (RFC 5321 allows
-- up to 64 chars in the local part).
--
-- NOTE: No UNIQUE constraint is added here. Auto-provisioned usernames are
-- derived from email prefixes which can collide across different providers
-- (e.g. alice@gmail.com and alice@company.com both get "alice"). Username
-- uniqueness should be enforced at a higher level when users explicitly set
-- their own usernames.

ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(100);
