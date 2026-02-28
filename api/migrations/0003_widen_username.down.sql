-- 0003_widen_username.down.sql
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_unique;

ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(50);
