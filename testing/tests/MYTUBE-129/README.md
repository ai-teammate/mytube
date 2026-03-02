# MYTUBE-129 — DB integration tests with custom environment variables

Verifies that the test suite correctly uses `DB_HOST` and `DB_PORT` environment
variable overrides to connect to a non-default PostgreSQL host or port, preventing
hardcoded environment failures.

## Dependencies

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | `testpass` | PostgreSQL password |
| `DB_NAME` | `mytube_test` | PostgreSQL database name |
| `SSL_MODE` | `disable` | SSL mode |

To test with a non-standard port set the variables before running:

```bash
export DB_HOST=localhost
export DB_PORT=5433
export DB_USER=testuser
export DB_PASSWORD=testpass
export DB_NAME=mytube_test
export SSL_MODE=disable
```

## Running the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-129/test_mytube_129.py -v
```

## Expected output when tests pass

```
testing/tests/MYTUBE-129/test_mytube_129.py::TestDBConfigReadsEnvVars::test_custom_host_reflected_in_config PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDBConfigReadsEnvVars::test_custom_port_reflected_in_config PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDBConfigReadsEnvVars::test_default_host_when_env_unset PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDBConfigReadsEnvVars::test_default_port_when_env_unset PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDBConfigReadsEnvVars::test_port_is_integer PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDSNContainsCustomValues::test_dsn_contains_custom_host PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDSNContainsCustomValues::test_dsn_contains_custom_port PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDSNContainsCustomValues::test_dsn_contains_both_custom_host_and_port PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDSNContainsCustomValues::test_dsn_default_host_and_port PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestDSNContainsCustomValues::test_dsn_logged_value_matches_env PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestPsycopg2HonoursDBConfig::test_connection_fails_to_unreachable_custom_port PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestPsycopg2HonoursDBConfig::test_connection_fails_to_unreachable_custom_host PASSED
testing/tests/MYTUBE-129/test_mytube_129.py::TestPsycopg2HonoursDBConfig::test_connection_succeeds_with_valid_db_config PASSED
```

All 13 tests pass confirming that:
- `DBConfig` reads `DB_HOST` and `DB_PORT` from the environment
- The DSN produced contains the overridden values
- `psycopg2` uses those values when connecting (fails fast on unreachable targets,
  succeeds when pointed at the real test database)
