#!/bin/bash
# joledev-vpn — Verificacion y setup inicial del nodo
# Uso: bash scripts/install.sh
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK] $1${NC}"; }
warn() { echo -e "${YELLOW}[!]  $1${NC}"; }
fail() { echo -e "${RED}[X]  $1${NC}"; exit 1; }

echo "joledev-vpn — Setup inicial"
echo "================================"

# WireGuard
if find /lib/modules/"$(uname -r)" -name 'wireguard.ko' 2>/dev/null | grep -q wireguard; then
  ok "WireGuard kernel module found"
else
  fail "WireGuard module not found for kernel $(uname -r)"
fi

# IP forwarding
IP_FWD=$(cat /proc/sys/net/ipv4/ip_forward)
if [[ "$IP_FWD" == "1" ]]; then
  ok "IP forwarding active"
else
  warn "IP forwarding disabled — needs: echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf && sudo sysctl -p"
fi

# Puerto 51820
if ss -ulpn | grep -q ":51820"; then
  warn "Port 51820 UDP already in use — check if WireGuard is already running"
else
  ok "Port 51820 UDP available"
fi

# kubectl
if kubectl get nodes &>/dev/null; then
  ok "K3s accessible"
else
  fail "kubectl not working"
fi

# Docker
if docker ps &>/dev/null; then
  ok "Docker OK"
else
  fail "Docker not accessible"
fi

echo ""
echo "All prerequisites OK"
echo ""
echo "Next steps:"
echo "  1. Create the Secret with the panel password:"
echo "     docker run --rm ghcr.io/wg-easy/wg-easy wgpw 'YOUR_PASSWORD'"
echo "     kubectl create secret generic wg-easy-secret \\"
echo "       --from-literal=password-hash='\$2b\$12\$HASH' \\"
echo "       -n joledev-vpn"
echo ""
echo "  2. Apply K3s manifests:"
echo "     kubectl apply -f k8s/"
echo ""
echo "  3. Verify pods:"
echo "     kubectl get pods -n joledev-vpn -w"
