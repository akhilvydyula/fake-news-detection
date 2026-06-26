# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `main` branch | Active development and security fixes |
| Latest release tag | Best-effort |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

1. Contact the maintainer via [GitHub](https://github.com/akhilvydyula) with subject:
   `[SECURITY] Fake News Detection`
2. Include: description, steps to reproduce, impact, and suggested fix if available.
3. Allow **72 hours** for an initial response.

## Security controls in this repository

| Control | Implementation |
|---------|----------------|
| Dependency audit | `pip-audit` in GitHub Actions CI |
| SAST | Bandit static analysis on Python source |
| Code scanning | GitHub CodeQL |
| Secret hygiene | No credentials in git; use env vars / Render / Streamlit secrets |
| Supply chain | Dependabot for pip and GitHub Actions |

## Scope

This is a **research / education / demo** ML project. Review [docs/COMPLIANCE.md](docs/COMPLIANCE.md)
for dataset and ethics constraints before production use.

## Safe harbor

We appreciate responsible disclosure and will not pursue legal action against researchers
who follow this policy in good faith.
