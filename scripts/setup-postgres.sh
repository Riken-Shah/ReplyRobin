#!/usr/bin/env bash
# Install Postgres + pgvector natively on a Linux VM (no Docker).
# Idempotent: safe to re-run. Requires root (sudo).
#
# Env vars (all optional):
#   PG_VERSION   default: 17
#   PG_DB        default: replyrobin
#   PG_USER      default: replyrobin
#   PG_PASS      default: auto-generated (printed at end)
#
# Usage:
#   sudo ./scripts/setup-postgres.sh
#   sudo PG_PASS=mysecret PG_DB=mydb ./scripts/setup-postgres.sh

set -euo pipefail

PG_VERSION="${PG_VERSION:-17}"
PG_DB="${PG_DB:-replyrobin}"
PG_USER="${PG_USER:-replyrobin}"
PG_PASS="${PG_PASS:-}"

# Resolve project root from script location so .env writes go to the right place.
SCRIPT_PATH="$(readlink -f "$0" 2>/dev/null || python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$0")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"

info() { printf '==> %s\n' "$*"; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

# True when systemd is the active init (i.e. we can use systemctl).
have_systemd() { [ -d /run/systemd/system ]; }

[ "$(id -u)" = "0" ] || die "must run as root (use sudo if available, otherwise switch user)"
[ -f /etc/os-release ] || die "cannot detect distro (no /etc/os-release)"
# shellcheck disable=SC1091
. /etc/os-release

# Drop privileges to the postgres user. Works with or without sudo (containers,
# minimal images), falling back through sudo → runuser → su.
as_postgres() {
    if command -v sudo >/dev/null 2>&1; then
        sudo -u postgres "$@"
    elif command -v runuser >/dev/null 2>&1; then
        runuser -u postgres -- "$@"
    else
        # Last-resort: use su. Quote args safely for the -c string.
        local cmd=""
        for arg in "$@"; do
            cmd+=" $(printf '%q' "$arg")"
        done
        su -s /bin/sh postgres -c "$cmd"
    fi
}

# Generate a URL/SQL-safe password if none provided.
if [ -z "$PG_PASS" ]; then
    if command -v openssl >/dev/null 2>&1; then
        PG_PASS="$(openssl rand -hex 16)"
    else
        PG_PASS="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | dd bs=1 count=32 2>/dev/null)"
    fi
    info "generated random password for ${PG_USER}"
fi

install_debian() {
    info "detected Debian/Ubuntu — installing via apt + PGDG"
    apt-get update -qq
    apt-get install -y -qq curl ca-certificates gnupg lsb-release openssl
    install -d /usr/share/postgresql-common/pgdg
    if [ ! -f /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc ]; then
        curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
            -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
    fi
    cat > /etc/apt/sources.list.d/pgdg.list <<EOF
deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main
EOF
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        "postgresql-${PG_VERSION}" "postgresql-${PG_VERSION}-pgvector"
    start_debian
}

start_debian() {
    if have_systemd; then
        systemctl enable --now postgresql
    else
        info "no systemd detected — starting cluster directly via pg_ctlcluster"
        if ! pg_isready -h /var/run/postgresql >/dev/null 2>&1; then
            pg_ctlcluster "${PG_VERSION}" main start
        fi
        info "note: without systemd, restart on boot is not configured — your container/host must start it"
    fi
}

install_rhel() {
    info "detected RHEL family — installing via dnf + PGDG"
    local rhel_ver="${VERSION_ID%%.*}"
    if ! rpm -q pgdg-redhat-repo >/dev/null 2>&1; then
        dnf install -y -q "https://download.postgresql.org/pub/repos/yum/reporpms/EL-${rhel_ver}-x86_64/pgdg-redhat-repo-latest.noarch.rpm"
    fi
    # The built-in 'postgresql' module on RHEL 8/9 conflicts with PGDG packages.
    dnf -qy module disable postgresql >/dev/null 2>&1 || true
    dnf install -y -q openssl "postgresql${PG_VERSION}-server" "postgresql${PG_VERSION}-contrib" "pgvector_${PG_VERSION}"
    local data_dir="/var/lib/pgsql/${PG_VERSION}/data"
    if [ ! -f "${data_dir}/PG_VERSION" ]; then
        "/usr/pgsql-${PG_VERSION}/bin/postgresql-${PG_VERSION}-setup" initdb
    fi
    start_rhel "$data_dir"
}

start_rhel() {
    local data_dir="$1"
    if have_systemd; then
        systemctl enable --now "postgresql-${PG_VERSION}"
    else
        info "no systemd detected — starting cluster directly via pg_ctl"
        if ! as_postgres pg_isready -h /var/run/postgresql >/dev/null 2>&1; then
            as_postgres "/usr/pgsql-${PG_VERSION}/bin/pg_ctl" \
                -D "$data_dir" -l "${data_dir}/server.log" start
        fi
        info "note: without systemd, restart on boot is not configured — your container/host must start it"
    fi
}

write_env_file() {
    local conn="$1"
    local seed_from=""

    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "${PROJECT_ROOT}/.env.example" ]; then
            seed_from="${PROJECT_ROOT}/.env.example"
            cp "$seed_from" "$ENV_FILE"
        else
            : > "$ENV_FILE"
        fi
    fi

    # Replace any existing POSTGRES_CONNECTION= line; append if absent.
    local tmp
    tmp="$(mktemp)"
    if grep -q '^POSTGRES_CONNECTION=' "$ENV_FILE"; then
        sed "s|^POSTGRES_CONNECTION=.*|POSTGRES_CONNECTION=${conn}|" "$ENV_FILE" > "$tmp"
    else
        cp "$ENV_FILE" "$tmp"
        printf '\nPOSTGRES_CONNECTION=%s\n' "$conn" >> "$tmp"
    fi
    mv "$tmp" "$ENV_FILE"
    chmod 600 "$ENV_FILE"

    # Running under sudo? Hand .env ownership back to the invoking user.
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        chown "${SUDO_USER}:" "$ENV_FILE"
    fi

    if [ -n "$seed_from" ]; then
        info "created ${ENV_FILE} from .env.example"
    else
        info "updated POSTGRES_CONNECTION in ${ENV_FILE}"
    fi
}

case "${ID_LIKE:-$ID}" in
    *debian*|debian|ubuntu)                    install_debian ;;
    *rhel*|*fedora*|centos|rocky|almalinux|amzn) install_rhel ;;
    *) die "unsupported distro: ${ID}. Handles Debian/Ubuntu and RHEL family." ;;
esac

info "creating role '${PG_USER}' and database '${PG_DB}' (idempotent)"
as_postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${PG_USER}') THEN
        CREATE ROLE ${PG_USER} LOGIN PASSWORD '${PG_PASS}';
    ELSE
        ALTER ROLE ${PG_USER} WITH PASSWORD '${PG_PASS}';
    END IF;
END
\$\$;
SQL

if ! as_postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1; then
    as_postgres createdb -O "${PG_USER}" "${PG_DB}"
fi

as_postgres psql -d "${PG_DB}" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector;"

info "verifying connection + pgvector as ${PG_USER}"
PGPASSWORD="${PG_PASS}" psql -h localhost -U "${PG_USER}" -d "${PG_DB}" \
    -tAc "SELECT extname FROM pg_extension WHERE extname='vector';" \
    | grep -q vector \
    || die "verification failed — pgvector not loaded"

CONNECTION_STRING="postgresql://${PG_USER}:${PG_PASS}@localhost:5432/${PG_DB}"
write_env_file "$CONNECTION_STRING"

cat <<EOF

Postgres ${PG_VERSION} + pgvector ready.
POSTGRES_CONNECTION written to ${ENV_FILE}

Next: run \`make migrate\` to apply Alembic migrations.

EOF

if have_systemd; then
    cat <<EOF
systemd is managing the daemon — restart on boot and on crash:
  systemctl status postgresql
  journalctl -u postgresql -f

EOF
else
    cat <<EOF
No systemd on this host (container / WSL). Manage the cluster manually:
  pg_ctlcluster ${PG_VERSION} main status
  pg_ctlcluster ${PG_VERSION} main {start|stop|restart}
(prefix with sudo if you're not root)

EOF
fi
