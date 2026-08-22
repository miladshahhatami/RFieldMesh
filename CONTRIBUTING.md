# Contributing to RFieldMesh

Use Python 3.12 or later and install the development extras:

```bash
python -m pip install -e ".[dev,desktop,packaging]"
```

Before proposing a change, run:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```

Scientific changes must include tests for numerical meaning, deterministic
seeds, supported and rejected Abaqus syntax, source preservation, and output
reparsing. Do not weaken fail-closed checks. Never commit private models,
credentials, personal paths, virtual environments, caches, or generated build
trees. Native Windows or Abaqus claims require corresponding machine evidence.

By contributing, you agree that your contribution is distributed under the
project's BSD-3-Clause licence.
