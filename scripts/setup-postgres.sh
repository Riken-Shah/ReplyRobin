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

info() { printf '==> %s\n' "$*"; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "run with sudo (need apt/dnf + systemctl)"
[ -f /etc/os-release ] || die "cannot detect distro (no /etc/os-release)"
# shellcheck disable=SC1091
. /etc/os-release

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
    apt-get install -y -qq "postgresql-${PG_VERSION}" "postgresql-${PG_VERSION}-pgvector"
    systemctl enable --now postgresql
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
    systemctl enable --now "postgresql-${PG_VERSION}"
}

case "${ID_LIKE:-$ID}" in
    *debian*|debian|ubuntu)                    install_debian ;;
    *rhel*|*fedora*|centos|rocky|almalinux|amzn) install_rhel ;;
    *) die "unsupported distro: ${ID}. Handles Debian/Ubuntu and RHEL family." ;;
esac

info "creating role '${PG_USER}' and database '${PG_DB}' (idempotent)"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
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

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1; then
    sudo -u postgres createdb -O "${PG_USER}" "${PG_DB}"
fi

sudo -u postgres psql -d "${PG_DB}" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector;"

info "verifying connection + pgvector as ${PG_USER}"
PGPASSWORD="${PG_PASS}" psql -h localhost -U "${PG_USER}" -d "${PG_DB}" \
    -tAc "SELECT extname FROM pg_extension WHERE extname='vector';" \
    | grep -q vector \
    || die "verification failed — pgvector not loaded"

cat <<EOF

Postgres ${PG_VERSION} + pgvector ready.

Add this line to your .env (and run \`make migrate\`):

  POSTGRES_CONNECTION=postgresql://${PG_USER}:${PG_PASS}@localhost:5432/${PG_DB}

systemd is managing the daemon — it will restart on boot and on crash:
  systemctl status postgresql
  journalctl -u postgresql -f

EOF
