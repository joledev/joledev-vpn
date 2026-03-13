#!/bin/bash
# Backup all PVC data from K3s cluster
# Designed to run directly on the VPS
#
# Edit the PVC list below to match your infrastructure.
# Each call to backup_pvc takes: name, namespace, pod-label, container-path
# For PostgreSQL, a pg_dump section is included as an example.
set -euo pipefail

BACKUP_ROOT="/home/joel/backups"
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="$BACKUP_ROOT/$DATE"
ARCHIVE="$BACKUP_ROOT/pvc-backup-$DATE.tar.gz"
MAX_BACKUPS=7

echo "=== PVC Backup — $DATE ==="
echo ""

mkdir -p "$BACKUP_DIR"

# Track results
BACKED_UP=()
FAILED=()

backup_pvc() {
  local name="$1"
  local namespace="$2"
  local label="$3"
  local container_path="$4"

  echo "--- $name ($namespace) ---"

  # Find the pod
  local pod
  pod=$(kubectl get pod -n "$namespace" -l "$label" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

  if [[ -z "$pod" ]]; then
    echo "  SKIP: no pod found for label=$label in namespace=$namespace"
    FAILED+=("$name")
    return
  fi

  echo "  Pod: $pod"
  echo "  Path: $container_path"

  local dest="$BACKUP_DIR/$name"
  mkdir -p "$dest"

  if kubectl cp "$namespace/$pod:$container_path" "$dest" 2>/dev/null; then
    local size
    size=$(du -sh "$dest" | cut -f1)
    echo "  OK ($size)"
    BACKED_UP+=("$name ($size)")
  else
    echo "  FAIL: kubectl cp failed"
    FAILED+=("$name")
    rm -rf "$dest"
  fi

  echo ""
}

# Helper for PostgreSQL databases (uses pg_dump for consistency)
backup_postgres() {
  local name="$1"
  local namespace="$2"
  local label="$3"
  local db_user="$4"
  local db_name="$5"

  echo "--- $name ($namespace) ---"

  local pod
  pod=$(kubectl get pod -n "$namespace" -l "$label" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

  if [[ -z "$pod" ]]; then
    echo "  SKIP: no pod found"
    FAILED+=("$name")
    echo ""
    return
  fi

  echo "  Pod: $pod"
  mkdir -p "$BACKUP_DIR/$name"

  if kubectl exec -n "$namespace" "$pod" -- pg_dump -U "$db_user" -d "$db_name" > "$BACKUP_DIR/$name/dump.sql" 2>/dev/null; then
    local size
    size=$(du -sh "$BACKUP_DIR/$name" | cut -f1)
    echo "  OK — pg_dump ($size)"
    BACKED_UP+=("$name ($size)")
  else
    echo "  FAIL: pg_dump failed, falling back to file copy"
    rm -f "$BACKUP_DIR/$name/dump.sql"
    if kubectl cp "$namespace/$pod:/var/lib/postgresql/data" "$BACKUP_DIR/$name" 2>/dev/null; then
      local size
      size=$(du -sh "$BACKUP_DIR/$name" | cut -f1)
      echo "  OK — file copy ($size)"
      BACKED_UP+=("$name ($size)")
    else
      echo "  FAIL"
      FAILED+=("$name")
      rm -rf "$BACKUP_DIR/$name"
    fi
  fi

  echo ""
}

# ============================================================
# PVC list — edit to match your infrastructure
# Format: backup_pvc "name" "namespace" "app=label" "/mount/path"
# ============================================================

backup_pvc "wg-easy-data" "joledev-vpn" "app=wg-easy" "/etc/wireguard"

# Add your own PVCs below. Examples:
# backup_pvc "app-data"    "my-namespace" "app=my-app"    "/data"
# backup_pvc "uploads"     "my-namespace" "app=my-app"    "/app/uploads"
# backup_postgres "my-db"  "my-namespace" "app=my-db"     "db_user" "db_name"

# --- Compress ---
echo "Compressing..."
tar -czf "$ARCHIVE" -C "$BACKUP_ROOT" "$DATE"
rm -rf "$BACKUP_DIR"
TOTAL_SIZE=$(du -sh "$ARCHIVE" | cut -f1)
echo "Archive: $ARCHIVE ($TOTAL_SIZE)"
echo ""

# --- Rotate old backups (keep last $MAX_BACKUPS) ---
echo "Cleaning old backups (keeping last $MAX_BACKUPS)..."
EXISTING=$(ls -1t "$BACKUP_ROOT"/pvc-backup-*.tar.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)))
if [[ -n "$EXISTING" ]]; then
  echo "$EXISTING" | while read -r old; do
    echo "  Removing: $(basename "$old")"
    rm -f "$old"
  done
  ls -1dt "$BACKUP_ROOT"/20??-??-?? 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | while read -r old; do
    rm -rf "$old"
  done
else
  echo "  Nothing to clean."
fi
echo ""

# --- Summary ---
echo "========== SUMMARY =========="
echo "Date:    $DATE"
echo "Archive: $ARCHIVE ($TOTAL_SIZE)"
echo ""
echo "Backed up (${#BACKED_UP[@]}):"
for item in "${BACKED_UP[@]}"; do
  echo "  + $item"
done
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo ""
  echo "Failed/Skipped (${#FAILED[@]}):"
  for item in "${FAILED[@]}"; do
    echo "  - $item"
  done
fi
echo ""
echo "Backups on disk:"
ls -lh "$BACKUP_ROOT"/pvc-backup-*.tar.gz 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
echo "=============================="
