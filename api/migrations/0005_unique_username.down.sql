-- 0005_unique_username.down.sql
DROP INDEX IF EXISTS idx_users_username;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_unique;
