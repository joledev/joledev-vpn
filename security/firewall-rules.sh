#!/bin/bash
# Firewall rules for WireGuard + wg-easy
# Run with sudo: sudo bash security/firewall-rules.sh
set -euo pipefail

# WireGuard UDP — open to the world (peers need to connect)
iptables -C INPUT -p udp --dport 51820 -j ACCEPT 2>/dev/null \
  || iptables -I INPUT -p udp --dport 51820 -j ACCEPT

# Rate limiting: max 10 new connections per minute per IP
iptables -C INPUT -p udp --dport 51820 -m state --state NEW -m recent --set --name wg_ratelimit 2>/dev/null \
  || iptables -I INPUT -p udp --dport 51820 -m state --state NEW -m recent --set --name wg_ratelimit

iptables -C INPUT -p udp --dport 51820 -m state --state NEW -m recent --update --seconds 60 --hitcount 10 --name wg_ratelimit -j DROP 2>/dev/null \
  || iptables -I INPUT -p udp --dport 51820 -m state --state NEW -m recent --update --seconds 60 --hitcount 10 --name wg_ratelimit -j DROP

# wg-easy web UI: ONLY from localhost and K3s pod network (Traefik)
iptables -C INPUT -p tcp --dport 51821 -s 127.0.0.1 -j ACCEPT 2>/dev/null \
  || iptables -I INPUT -p tcp --dport 51821 -s 127.0.0.1 -j ACCEPT

iptables -C INPUT -p tcp --dport 51821 -s 10.42.0.0/16 -j ACCEPT 2>/dev/null \
  || iptables -I INPUT -p tcp --dport 51821 -s 10.42.0.0/16 -j ACCEPT

iptables -C INPUT -p tcp --dport 51821 -j DROP 2>/dev/null \
  || iptables -A INPUT -p tcp --dport 51821 -j DROP

echo "VPN firewall rules applied"
