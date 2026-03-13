# Contributing

This is a personal infrastructure project. Contributions are welcome for documentation fixes, typos, and general improvements, but some areas require explicit review.

## Protected paths

PRs that modify any of the following require owner approval before merging:

- `k8s/` — Kubernetes manifests
- `.github/workflows/` — CI/CD pipelines
- `security/` — Firewall rules
- `scripts/` — Backup and maintenance scripts

These are enforced via CODEOWNERS.

## How to report issues

1. Open an issue at [github.com/joledev/joledev-vpn/issues](https://github.com/joledev/joledev-vpn/issues)
2. Include: what you expected, what happened, and steps to reproduce
3. For security vulnerabilities, **do not open a public issue** — email directly or use GitHub's private vulnerability reporting

## Rules

- **Never include secrets in PRs** — no passwords, tokens, private keys, API keys, or bcrypt hashes. PRs containing secrets will be closed immediately.
- Follow the existing code style and directory structure
- One logical change per PR
- Write a clear commit message explaining _why_, not just _what_

## Setup for local development

```bash
git clone https://github.com/joledev/joledev-vpn.git
cd joledev-vpn
cp .env.example .env
# Edit .env with your values — never commit this file
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
