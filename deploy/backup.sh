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

# A dump holds every credential in PLAINTEXT. Inside a git working tree it is one
# `git add -A` away from being pushed to a public remote, so refuse outright
# rather than rely on .gitignore being right.
if git -C "$BACKUP_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "!! ${BACKUP_DIR} is inside a git repository." >&2
    echo "   A dump contains every API key in plaintext; one 'git add -A' would" >&2
    echo "   push them to the remote. Choose a directory outside the repo:" >&2
    echo "     BACKUP_DIR=/opt/content-engine-backups $0 ${*:-}" >&2
    exit 1
fi

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
# NOTE: deliberately `grep -c`, not `grep -q`. With `set -o pipefail`, `grep -q`
# exits the moment it matches, zcat takes SIGPIPE (141), and the PIPELINE reports
# failure — so a perfectly good dump gets condemned as missing its settings
# table. grep -c reads the whole stream, so the exit code means what it says.
TABLES=$(zcat "$OUT" | grep -c "^CREATE TABLE" || true)
SETTINGS=$(zcat "$OUT" | grep -c "CREATE TABLE.*settings" || true)
if [ "${SETTINGS:-0}" -lt 1 ]; then
    echo "!! the dump has no settings table — your credentials are NOT in it." >&2
    echo "   (it does contain ${TABLES:-0} other tables)" >&2
    mv "$OUT" "${OUT}.SUSPECT"
    exit 1
fi
ROWCOPY=$(zcat "$OUT" | grep -c "^COPY public.settings" || true)
echo "    contains ${TABLES} tables, settings included$([ "${ROWCOPY:-0}" -gt 0 ] \
    && echo " with its rows" || echo " (SCHEMA ONLY — no rows!)")"

echo "==> wrote $OUT  ($(numfmt --to=iec "$SIZE" 2>/dev/null || echo "$SIZE bytes"))"

if [ "${1:-}" = "--verify" ]; then
    echo "==> verifying by RESTORING into a scratch database ..."
    # Lowercase: unquoted identifiers are folded to lowercase by Postgres, so a
    # name with a capital in it is not the name you think you created.
    SCRATCH="verify_$(echo "$STAMP" | tr 'A-Z-' 'a-z_')"
    TMP="$(mktemp)"
    LOG="$(mktemp)"
    trap 'rm -f "$TMP" "$LOG"' EXIT

    # Decompress to a FILE and redirect, rather than piping into the container.
    # A pipe here means psql can close stdin early and hand zcat a SIGPIPE,
    # which `set -o pipefail` then reports as a failed restore — the same false
    # alarm that condemned this dump's settings table an hour ago.
    zcat "$OUT" > "$TMP"

    if ! dc exec -T db psql -U "$DB_USER" -d postgres \
            -c "DROP DATABASE IF EXISTS ${SCRATCH};" \
            -c "CREATE DATABASE ${SCRATCH};" > "$LOG" 2>&1; then
        echo "    !! could not create the scratch database:" >&2
        sed 's/^/       /' "$LOG" >&2
        exit 1
    fi

    RESTORE_RC=0
    dc exec -T db psql -U "$DB_USER" -d "$SCRATCH" -v ON_ERROR_STOP=0 \
        < "$TMP" > "$LOG" 2>&1 || RESTORE_RC=$?

    # psql exits 0 even when individual statements fail, so its exit code alone
    # proves nothing. The only honest test of a backup is whether the ROWS came
    # back — so count them, and show any errors either way.
    ERRS=$(grep -c "^ERROR:" "$LOG" || true)
    ROWS=$(dc exec -T db psql -U "$DB_USER" -d "$SCRATCH" -tAc \
           "SELECT count(*) FROM settings;" 2>/dev/null | tr -d '[:space:]')
    JOBS=$(dc exec -T db psql -U "$DB_USER" -d "$SCRATCH" -tAc \
           "SELECT count(*) FROM jobs;" 2>/dev/null | tr -d '[:space:]')

    if [ "${ROWS:-0}" -gt 0 ]; then
        echo "    RESTORED — ${ROWS} settings rows, ${JOBS:-0} jobs came back."
        if [ "${ERRS:-0}" -gt 0 ]; then
            # Ownership/role GRANTs routinely fail on a restore into a scratch
            # database and do not affect your data. Show them; do not fail.
            echo "    (${ERRS} non-fatal statement error(s) — first 3:)"
            grep "^ERROR:" "$LOG" | head -3 | sed 's/^/       /'
        fi
    else
        echo "    !! THE DUMP DID NOT RESTORE — settings came back empty." >&2
        echo "       psql exit ${RESTORE_RC}, ${ERRS:-0} error(s). First 10:" >&2
        grep -E "^(ERROR|FATAL|psql)" "$LOG" | head -10 | sed 's/^/       /' >&2
        [ "${ERRS:-0}" -eq 0 ] && { echo "       (no SQL errors — last output:)" >&2
                                    tail -5 "$LOG" | sed 's/^/       /' >&2; }
    fi

    dc exec -T db psql -U "$DB_USER" -d postgres \
        -c "DROP DATABASE IF EXISTS ${SCRATCH};" >/dev/null 2>&1 || true
    rm -f "$TMP" "$LOG"
    trap - EXIT
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
