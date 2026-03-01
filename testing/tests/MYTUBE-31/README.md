# MYTUBE-31: Verify initial category seeding

Automated test for: **Verify initial category seeding — default categories populated in database**

Verifies that after running both `0001_initial_schema.up.sql` and `0002_seed_categories.up.sql`, the `categories` table contains exactly 5 rows: Education, Entertainment, Gaming, Music, and Other.

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ (accessible and running)
- A test database that the configured user can connect to (it will be wiped clean)

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable     | Default       | Description                        |
|--------------|---------------|------------------------------------|
| `DB_HOST`    | `localhost`   | PostgreSQL host                    |
| `DB_PORT`    | `5432`        | PostgreSQL port                    |
| `DB_USER`    | `testuser`    | Database user                      |
| `DB_PASSWORD`| `testpass`    | Database password                  |
| `DB_NAME`    | `mytube_test` | Target database (will be cleaned)  |
| `SSL_MODE`   | `disable`     | SSL mode                           |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-31/test_mytube_31.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-31/test_mytube_31.py::TestCategorySeeding::test_exactly_five_categories PASSED
testing/tests/MYTUBE-31/test_mytube_31.py::TestCategorySeeding::test_category_names_match_expected PASSED
testing/tests/MYTUBE-31/test_mytube_31.py::TestCategorySeeding::test_each_expected_category_exists[Education] PASSED
testing/tests/MYTUBE-31/test_mytube_31.py::TestCategorySeeding::test_each_expected_category_exists[Entertainment] PASSED
testing/tests/MYTUBE-31/test_mytube_31.py::TestCategorySeeding::test_each_expected_category_exists[Gaming] PASSED
testing/tests/MYTUBE-31/test_mytube_31.py::TestCategorySeeding::test_each_expected_category_exists[Music] PASSED
testing/tests/MYTUBE-31/test_mytube_31.py::TestCategorySeeding::test_each_expected_category_exists[Other] PASSED
testing/tests/MYTUBE-31/test_mytube_31.py::TestCategorySeeding::test_seed_is_idempotent PASSED

8 passed in X.XXs
```
