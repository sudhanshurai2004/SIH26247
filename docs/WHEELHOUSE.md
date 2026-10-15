# Local Python wheelhouse and offline-install verification

A wheelhouse is a **per-platform, per-Python-ABI** collection of the exact
wheels needed to install the locked Python dependencies without contacting an
index. It is deliberately ignored by Git: third-party binary artifacts should
be reviewed/provenanced for the receiving laptop rather than silently committed.

## Build and verify

Run these commands while an approved package source is available:

```bash
make wheelhouse
make offline-wheelhouse-test
```

The first invokes `scripts/build_wheelhouse.py` using
`requirements-dev.lock`. The second creates a fresh temporary virtual
environment and runs pip with `--no-index --find-links wheelhouse`,
`PIP_NO_INDEX=1`, and `PIP_FIND_LINKS` set to that directory. It then runs
`pip check` and imports the core runtime packages. The test has no fallback to
PyPI or another index.

## Executed Linux evidence

On 2026-10-15, CPython 3.11 on this Linux x86_64 validation environment built
28 wheels and passed the clean offline install/import test. The unabridged
actual outputs are committed at:

- [`evidence/wheelhouse-build-2026-10-15.txt`](evidence/wheelhouse-build-2026-10-15.txt)
- [`evidence/offline-wheelhouse-2026-10-15.txt`](evidence/offline-wheelhouse-2026-10-15.txt)

**Dependencies that could not be built/resolved in that executed Linux run:**
**none**. All locked dependencies were resolved as wheels; no source build was
needed in that environment.

## Dependencies that need a target-compatible wheelhouse

The following locked packages produced CPython-3.11 Linux x86_64 wheels in the
executed run and therefore cannot be reused as Windows/macOS/other-ABI
artifacts: `PyYAML`, `SQLAlchemy`, `numpy`, `pydantic_core`, `rpds-py`, and
`ruff`. Build or obtain the appropriate wheels for each intended target before
an air-gapped installation.

This Linux evidence does **not** verify a Windows, macOS, target-laptop, or
fully packaged-folder air-gapped installation. The package launcher does not
download dependencies; provision a reviewed target-specific virtual environment
or wheelhouse before copying the package.
