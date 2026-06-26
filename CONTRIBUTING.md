# Contributing to Fake News Detection

Thank you for helping improve **Fake News Detection**! This project is part of the
[Skills Marathon ML portfolio](https://github.com/akhilvydyula) and welcomes contributions
from students, practitioners, and the open-source community.

## Ways to contribute

| Action | How |
|--------|-----|
| **Star the repo** | Helps others discover the project on GitHub Explore |
| **Report bugs** | [Open a bug report](../../issues/new?template=bug_report.yml) |
| **Suggest features** | [Open a feature request](../../issues/new?template=feature_request.yml) |
| **Fix or improve code** | Fork, branch, pull request (see below) |
| **Improve docs** | README, `docs/`, comments, and examples |
| **Security issues** | See [SECURITY.md](SECURITY.md) - do not open public issues |

## Development setup

```bash
git clone https://github.com/akhilvydyula/fake-news-detection.git
cd fake-news-detection
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

See the [README](README.md) for project-specific train and serve commands.

## Pull request workflow

1. Fork the repository on GitHub.
2. Create a branch from `main`: `git checkout -b feature/short-description`.
3. Make focused changes - one logical change per PR when possible.
4. Run local checks: `python -m compileall -q` on changed paths; `pytest` if tests exist.
5. Open a pull request against `main` and fill out the PR template.
6. **CI must pass** - GitHub Actions runs tests, dependency audit, and SAST on every PR.

## Code style

- Python 3.10+ (3.11 recommended where noted in README)
- Prefer clear names and small, readable functions
- Match existing formatting; use `ruff` where configured
- Do not commit secrets, API keys, `.env` files, large datasets, or model binaries

## Community standards

All contributors must follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions

- [GitHub Discussions](https://github.com/akhilvydyula/fake-news-detection/discussions) for Q&A
- Open an issue labeled `question` for project-specific help

Maintained by [Akhil Vydyula](https://github.com/akhilvydyula).
