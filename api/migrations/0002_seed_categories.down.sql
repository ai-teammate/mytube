-- 0002_seed_categories.down.sql
-- Remove seeded categories

DELETE FROM categories WHERE name IN ('Education', 'Entertainment', 'Gaming', 'Music', 'Other');
