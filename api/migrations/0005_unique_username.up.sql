-- 0005_unique_username.up.sql
-- Add UNIQUE constraint to users.username.
--
-- Before applying the constraint, resolve any duplicate usernames by appending
-- a numeric suffix (e.g. "john" → "john_2", "john_3") to all but the earliest
-- row (by created_at ASC).  This matches the decision in MYTUBE-88 Option A.

DO $$
DECLARE
    r RECORD;
    suffix INT;
    candidate TEXT;
BEGIN
    -- For each username that appears more than once, keep the earliest row
    -- unchanged and rename the subsequent rows john_2, john_3, …
    FOR r IN
        SELECT id, username
        FROM (
            SELECT id,
                   username,
                   ROW_NUMBER() OVER (PARTITION BY username ORDER BY created_at ASC, id ASC) AS rn
            FROM users
        ) ranked
        WHERE rn > 1
        ORDER BY username, rn
    LOOP
        suffix := 2;
        LOOP
            -- Safety guard: if more than 10000 suffixed variants already exist
            -- for this username, raise an exception instead of looping forever.
            IF suffix > 10000 THEN
                RAISE EXCEPTION 'Too many duplicate usernames for "%": cannot deduplicate safely', r.username;
            END IF;
            candidate := r.username || '_' || suffix;
            EXIT WHEN NOT EXISTS (SELECT 1 FROM users WHERE username = candidate);
            suffix := suffix + 1;
        END LOOP;
        UPDATE users SET username = candidate WHERE id = r.id;
    END LOOP;
END;
$$;

ALTER TABLE users ADD CONSTRAINT users_username_unique UNIQUE (username);

-- Add an index on username to support fast profile lookups.
CREATE INDEX idx_users_username ON users(username);
