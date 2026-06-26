# Compliance and Data Governance

Legal, ethical, and data-handling expectations for **Fake News Detection**.

## Software license

| Item | Policy |
|------|--------|
| Application code | [MIT License](../LICENSE) |
| Dependencies | Respective licenses in `requirements.txt` / `pyproject.toml` |

## Dataset compliance

| Source | Notes |
|--------|-------|
| Primary dataset | GonzaloA/fake_news and optional AG News subsets - verify licenses before production |
| Redistribution | Do not commit full datasets unless license allows |
| Attribution | Preserve citations in README and derived works |

## Ethics and responsible use

- Models are **baselines for learning** - not production-certified by default.
- Audit for **bias and fairness** before real-world deployment.
- Use **human oversight** where automated decisions affect people.
- Do not upload **PII** into public issues or PRs.

## Regulatory awareness (informational)

| Domain | Guidance |
|--------|----------|
| Healthcare | Not a medical device without your own validation |
| Law enforcement / risk | Consult legal counsel before operational use |
| Media / trust and safety | Disclose automated scoring; respect publisher terms |
| Biometrics | Face analysis may implicate privacy laws in some regions |

*Educational guidance only - not legal advice.*

## CI/CD quality gates

Changes on `main` and pull requests run GitHub Actions: tests (where applicable),
`pip-audit`, Bandit SAST, and CodeQL. See [OPEN_SOURCE.md](OPEN_SOURCE.md).

## Contributor confirmation

By contributing you confirm your work is submitted under the MIT License and complies with
dataset policies in the README.
