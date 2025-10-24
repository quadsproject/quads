# QUADS Development Scripts

This directory contains development and testing utilities for QUADS.

## Test Runner with Database

### run-tests-with-db.sh

A comprehensive test runner that manages the PostgreSQL container lifecycle for running the QUADS test suite.

**Features:**
- Automatically starts a PostgreSQL container using podman
- Initializes the QUADS database schema
- Runs the full test suite with coverage reporting
- Handles cleanup automatically
- Provides colored output for better readability

**Usage:**

```bash
# Run tests with automatic database setup and cleanup
./scripts/run-tests-with-db.sh

# Run tests and keep the database container running
./scripts/run-tests-with-db.sh --keep-db

# Run tests without coverage reporting (faster)
./scripts/run-tests-with-db.sh --no-coverage

# Clean up any existing test database containers
./scripts/run-tests-with-db.sh --cleanup

# Show help
./scripts/run-tests-with-db.sh --help
```

**Examples:**

```bash
# Quick test run during development
./scripts/run-tests-with-db.sh --no-coverage

# Full test run with coverage for CI/CD
./scripts/run-tests-with-db.sh

# Keep database running for debugging
./scripts/run-tests-with-db.sh --keep-db
# ... run manual queries or debugging
./scripts/run-tests-with-db.sh --cleanup
```

**Container Details:**
- Container name: `quads-test-db`
- Port: `5432`
- User: `postgres`
- Password: `postgres`
- Database: `quads`
- Connection URI: `postgresql://postgres:postgres@localhost:5432/quads`

**Requirements:**
- `podman` installed and running
- Python environment with QUADS dependencies installed
- Flask CLI available

**Troubleshooting:**

If the script fails to start:
1. Check if podman is installed: `podman --version`
2. Check if port 5432 is already in use: `ss -tlnp | grep 5432`
3. Clean up any existing containers: `./scripts/run-tests-with-db.sh --cleanup`

If tests fail:
1. Check the database logs: `podman logs quads-test-db`
2. Verify database initialization: `SQLALCHEMY_DATABASE_URI=postgresql://postgres:postgres@localhost:5432/quads flask --app quads.server.app shell`
3. Run tests with verbose output: `./scripts/run-tests-with-db.sh --no-coverage`
