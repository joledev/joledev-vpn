#!/bin/bash
# Revoke a WireGuard peer
# Usage: bash scripts/revoke-peer.sh
set -euo pipefail

NAMESPACE="joledev-vpn"

POD=$(kubectl get pod -n "$NAMESPACE" -l app=wg-easy -o jsonpath='{.items[0].metadata.name}')

if [[ -z "$POD" ]]; then
  echo "Error: wg-easy pod not found in namespace $NAMESPACE"
  exit 1
fi

echo "Current peers:"
kubectl exec -n "$NAMESPACE" "$POD" -- wg show 2>/dev/null || echo "(No peers configured)"
echo ""
echo "To revoke a peer, use the admin panel at https://admin.vpn.joledev.com"
echo "or delete the peer config from /etc/wireguard/ inside the pod."
