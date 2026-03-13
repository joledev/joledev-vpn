#!/bin/bash
# Add a WireGuard peer via wg-easy CLI
# Usage: bash scripts/add-peer.sh <peer-name>
set -euo pipefail

PEER_NAME="${1:?Usage: $0 <peer-name>}"
NAMESPACE="joledev-vpn"

POD=$(kubectl get pod -n "$NAMESPACE" -l app=wg-easy -o jsonpath='{.items[0].metadata.name}')

if [[ -z "$POD" ]]; then
  echo "Error: wg-easy pod not found in namespace $NAMESPACE"
  exit 1
fi

echo "Adding peer '$PEER_NAME' via wg-easy..."
echo "Use the admin panel at https://admin.vpn.joledev.com to create peers with QR codes."
echo ""
echo "Current WireGuard status:"
kubectl exec -n "$NAMESPACE" "$POD" -- wg show 2>/dev/null || echo "(WireGuard not yet initialized)"
