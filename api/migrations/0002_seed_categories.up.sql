-- 0002_seed_categories.up.sql
-- Seed initial category rows

INSERT INTO categories (name) VALUES
    ('Education'),
    ('Entertainment'),
    ('Gaming'),
    ('Music'),
    ('Other')
ON CONFLICT (name) DO NOTHING;
