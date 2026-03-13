# joledev-vpn

[![Deploy Docs](https://github.com/joledev/joledev-vpn/actions/workflows/deploy-docs.yml/badge.svg)](https://github.com/joledev/joledev-vpn/actions/workflows/deploy-docs.yml)
[![Validate Manifests](https://github.com/joledev/joledev-vpn/actions/workflows/validate-manifests.yml/badge.svg)](https://github.com/joledev/joledev-vpn/actions/workflows/validate-manifests.yml)
[![Secret Scan](https://github.com/joledev/joledev-vpn/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/joledev/joledev-vpn/actions/workflows/secret-scan.yml)
![WireGuard](https://img.shields.io/badge/WireGuard-88171A?logo=wireguard&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

VPN personal self-hosted con WireGuard, desplegado en K3s.

## Por que

No confio en VPNs comerciales. Quiero saber exactamente por donde pasa mi trafico, quien tiene acceso a mis datos, y tener la capacidad de revocar un dispositivo en segundos si lo pierdo. Este VPN corre en mi propio VPS, usa WireGuard (modulo del kernel, no userspace), y el unico que tiene las llaves soy yo.

## Arquitectura

```
Internet
    |
    |--- :443 HTTPS ---> Traefik (K3s)
    |                       |
    |                       |--- admin.vpn.joledev.com --> Authelia 2FA --> wg-easy (panel)
    |                       |--- docs.vpn.joledev.com  --> Authelia 2FA --> nginx (manual)
    |
    |--- :51820 UDP (directo, sin proxy)
            |
          WireGuard wg0
          10.8.0.0/24
            |
            |--- 10.8.0.2  phone-1
            |--- 10.8.0.3  phone-2
            |--- 10.8.0.4  desktop-1
            |--- 10.8.0.5  laptop-1
```

## Stack

- **WireGuard** - kernel module, protocolo VPN moderno (ChaCha20-Poly1305)
- **wg-easy** - panel web para administrar peers, QR codes, estadisticas
- **K3s** - Kubernetes ligero, orquesta todo
- **Traefik** - ingress controller, TLS automatico
- **Authelia** - SSO con 2FA obligatorio para el panel admin y docs
- **cert-manager** - certificados Let's Encrypt automaticos
- **GitHub Actions** - CI/CD para docs + escaneo de secretos

## Requisitos

- VPS con Debian 12+ y kernel 6.1+ (WireGuard built-in)
- K3s instalado con Traefik
- cert-manager con ClusterIssuer `letsencrypt-prod`
- Authelia configurado como middleware de Traefik
- Docker (para generar password hash)
- DNS: `admin.vpn.joledev.com` y `docs.vpn.joledev.com` apuntando al VPS

## Instalacion

```bash
# 1. Clonar
git clone https://github.com/joledev/joledev-vpn.git
cd joledev-vpn

# 2. Verificar prerequisitos
bash scripts/install.sh

# 3. Crear namespace
kubectl apply -f k8s/namespace.yaml

# 4. Crear secret con password del panel
docker run --rm ghcr.io/wg-easy/wg-easy wgpw 'TU_PASSWORD_SEGURA'
kubectl create secret generic wg-easy-secret \
  --from-literal=password-hash='$2b$12$HASH_AQUI' \
  -n joledev-vpn

# 5. Aplicar manifests
kubectl apply -f k8s/wg-easy/
kubectl apply -f k8s/docs/

# 6. Reglas de firewall
sudo bash security/firewall-rules.sh

# 7. Verificar
kubectl get pods -n joledev-vpn
kubectl get certificate -n joledev-vpn
```

## Seguridad

**Protege contra:**
- Espionaje en redes WiFi publicas
- ISP inspeccionando tu trafico (DPI)
- Censura basica por DNS/IP

**NO protege contra:**
- Anonimato total (el VPS tiene IP fija)
- Malware en tu dispositivo
- Sitios que te trackean con cookies/fingerprinting

## Estructura

```
joledev-vpn/
|-- k8s/                    # Manifests de Kubernetes
|   |-- namespace.yaml
|   |-- wg-easy/            # WireGuard + panel admin
|   |-- docs/               # Sitio de documentacion
|-- docs/                   # Manual web (HTML/CSS/JS)
|-- scripts/                # Utilidades (install, backup, peers)
|-- security/               # Reglas de firewall
|-- .github/workflows/      # CI/CD
|-- Dockerfile.docs         # Imagen del manual
|-- .env.example            # Template de variables
```

## Contributing

The `main` branch is protected. All changes require a pull request with owner review before merging. See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for details.

Critical paths (`k8s/`, `.github/`, `security/`, `scripts/`) are enforced via [CODEOWNERS](.github/CODEOWNERS).

## Manual completo

[docs.vpn.joledev.com](https://docs.vpn.joledev.com)

## License

MIT
