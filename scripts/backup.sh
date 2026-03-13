#!/bin/bash
# Backup del PVC de wg-easy (contiene llaves del servidor y todos los peers)
# Guardar en lugar SEGURO — no en el repo
set -euo pipefail

BACKUP_DIR="$HOME/vpn-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/wg-easy-backup-$TIMESTAMP.tar.gz"
NAMESPACE="joledev-vpn"

mkdir -p "$BACKUP_DIR"

POD=$(kubectl get pod -n "$NAMESPACE" -l app=wg-easy -o jsonpath='{.items[0].metadata.name}')

if [[ -z "$POD" ]]; then
  echo "Error: wg-easy pod not found"
  exit 1
fi

kubectl cp "$NAMESPACE/$POD:/etc/wireguard" "/tmp/wg-backup-$TIMESTAMP"
tar -czf "$BACKUP_FILE" -C "/tmp" "wg-backup-$TIMESTAMP"
rm -rf "/tmp/wg-backup-$TIMESTAMP"

echo "Backup saved to: $BACKUP_FILE"
echo "WARNING: This file contains private keys. Store it securely (encrypted, outside the repo)."
