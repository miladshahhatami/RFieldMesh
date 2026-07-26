# Contributing to RFieldMesh

Contributions should preserve scientific traceability, deterministic behavior,
and Abaqus source safety.

## Development setup

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev,desktop,packaging]"
```

Before proposing a change, run:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m build
```

Numerical changes require tests for deterministic seeds, target statistics,
covariance behavior, and limiting cases. Abaqus-writing changes require
source-preservation, independent-reparse, and golden or integration tests.
Platform-specific claims require evidence from the corresponding native
runtime.

Do not commit proprietary Abaqus models, unpublished research data, credentials,
personal paths, or transient build environments. Use the redistributable
fixtures or construct a minimal synthetic reproducer.

Bug reports should identify the RFieldMesh version, operating system, Python or
packaged-application route, selected algorithm and mapping, mesh type and size,
and a minimal non-confidential input when possible.
