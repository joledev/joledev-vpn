#!/bin/bash
# Backup all PVC data from K3s cluster
# Designed to run directly on the VPS
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
  local resource_type="${5:-deployment}"  # deployment or statefulset

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

# --- Backup each PVC ---

backup_pvc "wg-easy-data" "joledev-vpn" "app=wg-easy" "/etc/wireguard"

backup_pvc "scheduler-data" "joledev" "app=scheduler" "/data"

backup_pvc "pocketbase-data" "puntamorro" "app=pocketbase" "/pb_data"

# For postgres, use pg_dump instead of raw file copy for consistency
echo "--- recetario-db-data (puntamorro) ---"
DB_POD=$(kubectl get pod -n puntamorro -l app=recetario-db -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -n "$DB_POD" ]]; then
  echo "  Pod: $DB_POD"
  mkdir -p "$BACKUP_DIR/recetario-db-data"
  if kubectl exec -n puntamorro "$DB_POD" -- pg_dump -U recetario_user -d recetario > "$BACKUP_DIR/recetario-db-data/dump.sql" 2>/dev/null; then
    SIZE=$(du -sh "$BACKUP_DIR/recetario-db-data" | cut -f1)
    echo "  OK — pg_dump ($SIZE)"
    BACKED_UP+=("recetario-db-data ($SIZE)")
  else
    echo "  FAIL: pg_dump failed, falling back to file copy"
    rm -f "$BACKUP_DIR/recetario-db-data/dump.sql"
    if kubectl cp "puntamorro/$DB_POD:/var/lib/postgresql/data" "$BACKUP_DIR/recetario-db-data" 2>/dev/null; then
      SIZE=$(du -sh "$BACKUP_DIR/recetario-db-data" | cut -f1)
      echo "  OK — file copy ($SIZE)"
      BACKED_UP+=("recetario-db-data ($SIZE)")
    else
      echo "  FAIL"
      FAILED+=("recetario-db-data")
      rm -rf "$BACKUP_DIR/recetario-db-data"
    fi
  fi
else
  echo "  SKIP: no pod found"
  FAILED+=("recetario-db-data")
fi
echo ""

backup_pvc "recetario-uploads" "puntamorro" "app=recetario-backend" "/app/uploads"

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
  # Also remove any leftover uncompressed directories
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
