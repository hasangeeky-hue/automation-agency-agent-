#!/usr/bin/env bash
# ============================================================================
# Postgres backup for the Content Engine.
#
# Everything the engine knows lives in ONE docker volume (engine_db): 39
# credentials, every lead, every recorded deal, the playbook and the whole job
# history. `docker compose down -v`, a disk failure, or a mistyped volume prune
# ends all of it at once. This is the only thing standing between you and that.
#
# Writes a compressed dump to /opt/content-engine-backups on the HOST — outside
# the docker volume, so removing the volume cannot remove the backups.
#
#   ./deploy/backup.sh              take a backup now
#   ./deploy/backup.sh --verify     take one and prove it restores
#
# A backup nobody has restored is a hope, not a backup. --verify actually loads
# the dump into a scratch database and counts the rows back.
#
# OFF-BOX is the part this script CANNOT do for you: a backup sitting on the
# same VPS as the database dies with the VPS. See the note it prints at the end.
# ============================================================================
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-/opt/content-engine/deploy/docker-compose.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/content-engine-backups}"
KEEP="${KEEP:-14}"
DB_USER="${DB_USER:-engine}"
DB_NAME="${DB_NAME:-engine}"
STAMP="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="${BACKUP_DIR}/engine-${STAMP}.sql.gz"

dc() { docker compose -f "$COMPOSE_FILE" "$@"; }

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"    # dumps contain every credential in plaintext

echo "==> dumping ${DB_NAME} ..."
# --clean --if-exists so the dump can be restored over an existing database.
if ! dc exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists \
        | gzip -9 > "$OUT.part"; then
    rm -f "$OUT.part"
    echo "!! pg_dump FAILED — no backup was written." >&2
    exit 1
fi
mv "$OUT.part" "$OUT"

# A dump that is technically a file but contains nothing is the worst outcome:
# it looks like a backup in a directory listing and restores an empty engine.
SIZE=$(stat -c%s "$OUT")
if [ "$SIZE" -lt 2000 ]; then
    echo "!! the dump is only ${SIZE} bytes — that is not a real backup." >&2
    echo "   keeping it as ${OUT}.SUSPECT for inspection." >&2
    mv "$OUT" "${OUT}.SUSPECT"
    exit 1
fi
if ! zcat "$OUT" | grep -q "CREATE TABLE.*settings"; then
    echo "!! the dump has no settings table — your credentials are NOT in it." >&2
    mv "$OUT" "${OUT}.SUSPECT"
    exit 1
fi

echo "==> wrote $OUT  ($(numfmt --to=iec "$SIZE" 2>/dev/null || echo "$SIZE bytes"))"

if [ "${1:-}" = "--verify" ]; then
    echo "==> verifying by RESTORING into a scratch database ..."
    SCRATCH="verify_${STAMP//-/_}"
    dc exec -T db psql -U "$DB_USER" -d postgres -c "CREATE DATABASE ${SCRATCH};" >/dev/null
    if zcat "$OUT" | dc exec -T db psql -U "$DB_USER" -d "$SCRATCH" -q >/dev/null 2>&1; then
        ROWS=$(dc exec -T db psql -U "$DB_USER" -d "$SCRATCH" -tAc \
               "SELECT count(*) FROM settings;" 2>/dev/null | tr -d '[:space:]')
        JOBS=$(dc exec -T db psql -U "$DB_USER" -d "$SCRATCH" -tAc \
               "SELECT count(*) FROM jobs;" 2>/dev/null | tr -d '[:space:]')
        echo "    restored OK — ${ROWS:-0} settings rows, ${JOBS:-0} jobs"
        [ "${ROWS:-0}" -gt 0 ] || echo "    !! zero settings restored — check this."
    else
        echo "    !! THE DUMP DID NOT RESTORE. Treat this backup as invalid." >&2
    fi
    dc exec -T db psql -U "$DB_USER" -d postgres \
        -c "DROP DATABASE IF EXISTS ${SCRATCH};" >/dev/null
fi

# Retention: keep the newest $KEEP, delete older. Never touches .SUSPECT files.
ls -1t "${BACKUP_DIR}"/engine-*.sql.gz 2>/dev/null | tail -n "+$((KEEP + 1))" \
    | xargs -r rm -f
COUNT=$(ls -1 "${BACKUP_DIR}"/engine-*.sql.gz 2>/dev/null | wc -l)
echo "==> ${COUNT} backup(s) kept in ${BACKUP_DIR} (keeping newest ${KEEP})"

cat <<'NOTE'

  ---------------------------------------------------------------------
  THIS BACKUP IS STILL ON THE SAME MACHINE AS THE DATABASE.
  That covers a bad deploy or a dropped volume. It does NOT cover losing
  the VPS. Copy it somewhere else — from YOUR laptop, not from the VPS:

      scp root@72.62.90.174:/opt/content-engine-backups/engine-*.sql.gz .

  To restore:
      zcat engine-TIMESTAMP.sql.gz | docker compose -f deploy/docker-compose.yml \
          exec -T db psql -U engine -d engine
  ---------------------------------------------------------------------
NOTE
