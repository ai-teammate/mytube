-- 0003_widen_username.down.sql
ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(50);
