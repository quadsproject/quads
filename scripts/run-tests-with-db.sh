#!/bin/bash
#
# QUADS Test Runner with Database Container
#
# This script manages the PostgreSQL container lifecycle for running tests.
# It can be invoked as: ./scripts/run-tests-with-db.sh [OPTIONS]
#
# Options:
#   --keep-db     Keep the database container running after tests
#   --cleanup     Stop and remove any existing test database containers
#   --no-coverage Skip coverage reporting
#   --venv PATH   Path to virtualenv (default: .venv)
#   -h, --help    Show this help message

set -e

# Configuration
CONTAINER_NAME="quads-test-db"
DB_PASSWORD="postgres"
DB_PORT="5432"
DB_NAME="quads"
DB_URI="postgresql://postgres:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"
VENV_PATH=".venv"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
KEEP_DB=false
CLEANUP_ONLY=false
NO_COVERAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-db)
            KEEP_DB=true
            shift
            ;;
        --cleanup)
            CLEANUP_ONLY=true
            shift
            ;;
        --no-coverage)
            NO_COVERAGE=true
            shift
            ;;
        --venv)
            VENV_PATH="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --keep-db     Keep the database container running after tests"
            echo "  --cleanup     Stop and remove any existing test database containers"
            echo "  --no-coverage Skip coverage reporting"
            echo "  --venv PATH   Path to virtualenv (default: .venv)"
            echo "  -h, --help    Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if container exists
container_exists() {
    podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"
}

# Function to check if container is running
container_running() {
    podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"
}

# Function to stop and remove container
cleanup_container() {
    if container_exists; then
        print_info "Stopping and removing existing container: ${CONTAINER_NAME}"
        podman stop "${CONTAINER_NAME}" 2>/dev/null || true
        podman rm "${CONTAINER_NAME}" 2>/dev/null || true
    fi
}

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    print_info "Waiting for PostgreSQL to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if podman exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null 2>&1; then
            print_info "PostgreSQL is ready!"
            return 0
        fi

        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    print_error "PostgreSQL failed to become ready after ${max_attempts} seconds"
    return 1
}

# Function to setup virtualenv (does not activate - caller must source)
setup_virtualenv() {
    if [ ! -d "${VENV_PATH}" ]; then
        print_info "Creating virtualenv at ${VENV_PATH}..."
        python3 -m venv "${VENV_PATH}"

        print_info "Installing dependencies in virtualenv..."
        "${VENV_PATH}/bin/pip" install -q --upgrade pip

        print_info "Installing QUADS dependencies..."
        "${VENV_PATH}/bin/pip" install -q -r requirements.txt

        print_info "Installing test dependencies..."
        "${VENV_PATH}/bin/pip" install -q -r tests/requirements.txt

        print_info "Installing QUADS in development mode..."
        "${VENV_PATH}/bin/pip" install -q -e .
    else
        print_info "Using existing virtualenv at ${VENV_PATH}"
    fi

    # Verify installation
    if ! "${VENV_PATH}/bin/python" -c "import quads" 2>/dev/null; then
        print_warn "QUADS not found in virtualenv, reinstalling..."
        "${VENV_PATH}/bin/pip" install -q -r requirements.txt
        "${VENV_PATH}/bin/pip" install -q -r tests/requirements.txt
        "${VENV_PATH}/bin/pip" install -q -e .
    fi
}

# Server PID for cleanup (set when daemonized)
SERVER_PID=""

# Cleanup on script exit (unless --keep-db is set)
cleanup_on_exit() {
    local exit_code=$?

    if [ -n "${SERVER_PID}" ]; then
        print_info "Stopping QUADS server (PID ${SERVER_PID})..."
        kill "${SERVER_PID}" 2>/dev/null || true
        wait "${SERVER_PID}" 2>/dev/null || true
    fi

    if [ "$KEEP_DB" = false ]; then
        print_info "Cleaning up database container..."
        cleanup_container
    else
        print_info "Keeping database container running (use --cleanup to remove)"
        print_info "Container name: ${CONTAINER_NAME}"
        print_info "Connection URI: ${DB_URI}"
    fi

    exit $exit_code
}

# Main execution
main() {
    # Handle cleanup-only mode
    if [ "$CLEANUP_ONLY" = true ]; then
        cleanup_container
        print_info "Cleanup complete"
        exit 0
    fi

    # Check for podman
    if ! command -v podman &> /dev/null; then
        print_error "podman not found. Please install podman first."
        exit 1
    fi

    # Check for python3
    if ! command -v python3 &> /dev/null; then
        print_error "python3 not found. Please install python3 first."
        exit 1
    fi

    # Setup virtualenv
    setup_virtualenv

    # Set paths to use virtualenv binaries
    PYTHON="${VENV_PATH}/bin/python"
    PIP="${VENV_PATH}/bin/pip"
    FLASK="${VENV_PATH}/bin/flask"
    PYTEST="${VENV_PATH}/bin/pytest"

    print_info "Using Python: ${PYTHON}"
    print_info "Python version: $(${PYTHON} --version)"

    # Setup cleanup trap
    trap cleanup_on_exit EXIT INT TERM

    # Clean up any existing container
    cleanup_container

    # Start PostgreSQL container
    print_info "Starting PostgreSQL container: ${CONTAINER_NAME}"
    podman run -d \
        --name "${CONTAINER_NAME}" \
        -e POSTGRES_PASSWORD="${DB_PASSWORD}" \
        -p "${DB_PORT}:5432" \
        postgres:latest

    # Wait for PostgreSQL to be ready
    if ! wait_for_postgres; then
        print_error "Failed to start PostgreSQL"
        exit 1
    fi

    # Set QUADS configuration directory to use test config
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
    export QUADS_CONF_DIR="${REPO_ROOT}/conf"

    print_info "Using QUADS config from: ${QUADS_CONF_DIR}"

    # Initialize the database
    print_info "Initializing QUADS database..."
    if ! SQLALCHEMY_DATABASE_URI="${DB_URI}" QUADS_CONF_DIR="${QUADS_CONF_DIR}" "${FLASK}" --app quads.server.app init-db; then
        print_error "Database initialization failed"
        exit 1
    fi

    print_info "Database initialized successfully"

    # Start the server in the background (logs to /tmp/quads-test-server.log)
    print_info "Starting QUADS server..."
    SQLALCHEMY_DATABASE_URI="${DB_URI}" QUADS_CONF_DIR="${QUADS_CONF_DIR}" "${FLASK}" --app quads.server.app run > /tmp/quads-test-server.log 2>&1 &
    SERVER_PID=$!
    sleep 2
    if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
        print_error "Server startup failed"
        cat /tmp/quads-test-server.log
        exit 1
    fi

    # Build test command
    if [ "$NO_COVERAGE" = true ]; then
        TEST_CMD="${PYTEST} -vv -p no:warnings tests/"
    else
        TEST_CMD="${PYTEST} -vv -p no:warnings --cov=quads.cli --cov=quads.server --cov=quads.tools --cov-report=xml --cov-report=term --junitxml=junit.xml tests/"
    fi

    # Run tests
    print_info "Running test suite..."
    echo ""

    if SQLALCHEMY_DATABASE_URI="${DB_URI}" QUADS_CONF_DIR="${QUADS_CONF_DIR}" ${TEST_CMD}; then
        echo ""
        print_info "✓ All tests passed successfully!"
        exit 0
    else
        echo ""
        print_error "✗ Some tests failed"
        exit 1
    fi
}

# Run main function
main
