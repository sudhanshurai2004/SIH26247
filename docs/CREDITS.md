# Third-party credits and licences

**Generated/reviewed for the local MVP implementation on 2026-10-12.** The committed lock files are
the source of truth for versions. This document records every package resolved
by `requirements-dev.lock` and `dashboard/package-lock.json`; it intentionally
includes development and transitive packages. No AGPL dependency and no
Ultralytics YOLO dependency is used.

The project source is licensed under the repository [`LICENSE`](../LICENSE)
(MIT), adopted for the training-only source package. This list does not alter
third-party licences. Licence identifiers below are package metadata; for
distribution, retain the original notices shipped by each package.

## Release audit note (2026-10-15)

- `requirements*.lock` and `dashboard/package-lock.json` were reviewed against
  this inventory; no dependency is labelled AGPL in the committed lock files.
- Ultralytics/YOLO is not declared, imported, or packaged. No model or external
  dataset is bundled.
- Repository-authored visuals are simple Godot/UI primitives; no third-party
  3D model, texture, sound, doctrine, or operational data is shipped.
- `npm --prefix dashboard audit --audit-level=high` and `pip check` outcomes
  are recorded with their executed output in `docs/READINESS.md`. An audit
  reports dependency metadata, not a guarantee of future vulnerability status.

## Runtime tooling

| Tool | Version | Licence |
| --- | ---: | --- |
| Godot Engine | 4.5.1-stable (pinned official CI smoke binary; optional local runtime) | MIT |

The CI workflow downloads the official Godot 4.5.1-stable Linux x86_64 release
asset and verifies SHA-256
`02ec53d1cc7dbb9cc6355393c61b9ab43d1244751a124f10248a4802830788cd`
before the headless smoke. This pin identifies the test binary; it is not a
claim of target-laptop rendering or FPS verification.

## Python packages

| Package | Version | Licence |
| --- | ---: | --- |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| click | 8.5.0 | BSD-3-Clause |
| fastapi | 0.115.12 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| jsonschema | 4.23.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| numpy | 2.2.5 | BSD-3-Clause; binary wheels include separately noticed bundled libraries |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.6.0 | MIT |
| pydantic | 2.14.1 | MIT |
| pydantic_core | 2.50.1 | MIT |
| pytest | 8.3.5 | MIT |
| PyYAML | 6.0.2 | MIT |
| SQLAlchemy | 2.1.4 | MIT |
| referencing | 0.37.0 | MIT |
| rpds-py | 2026.9.1 | MIT |
| ruff | 0.11.7 | MIT |
| starlette | 0.46.2 | BSD-3-Clause |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| uvicorn | 0.34.2 | BSD-3-Clause |

`pip` and `setuptools` are virtual-environment bootstrap tools, not declared
project dependencies, and are therefore not included in either requirements
lock.

## Dashboard npm packages

| Package | Version | Licence |
| --- | ---: | --- |
| @babel/code-frame | 7.29.7 | MIT |
| @babel/compat-data | 7.29.7 | MIT |
| @babel/core | 7.29.7 | MIT |
| @babel/generator | 7.29.8 | MIT |
| @babel/helper-compilation-targets | 7.29.7 | MIT |
| @babel/helper-globals | 7.29.7 | MIT |
| @babel/helper-module-imports | 7.29.7 | MIT |
| @babel/helper-module-transforms | 7.29.7 | MIT |
| @babel/helper-plugin-utils | 7.29.7 | MIT |
| @babel/helper-string-parser | 7.29.7 | MIT |
| @babel/helper-validator-identifier | 7.29.7 | MIT |
| @babel/helper-validator-option | 7.29.7 | MIT |
| @babel/helpers | 7.29.10 | MIT |
| @babel/parser | 7.29.9 | MIT |
| @babel/plugin-transform-react-jsx-self | 7.29.7 | MIT |
| @babel/plugin-transform-react-jsx-source | 7.29.7 | MIT |
| @babel/template | 7.29.7 | MIT |
| @babel/traverse | 7.29.10 | MIT |
| @babel/types | 7.29.8 | MIT |
| @esbuild/aix-ppc64 | 0.25.12 | MIT |
| @esbuild/android-arm | 0.25.12 | MIT |
| @esbuild/android-arm64 | 0.25.12 | MIT |
| @esbuild/android-x64 | 0.25.12 | MIT |
| @esbuild/darwin-arm64 | 0.25.12 | MIT |
| @esbuild/darwin-x64 | 0.25.12 | MIT |
| @esbuild/freebsd-arm64 | 0.25.12 | MIT |
| @esbuild/freebsd-x64 | 0.25.12 | MIT |
| @esbuild/linux-arm | 0.25.12 | MIT |
| @esbuild/linux-arm64 | 0.25.12 | MIT |
| @esbuild/linux-ia32 | 0.25.12 | MIT |
| @esbuild/linux-loong64 | 0.25.12 | MIT |
| @esbuild/linux-mips64el | 0.25.12 | MIT |
| @esbuild/linux-ppc64 | 0.25.12 | MIT |
| @esbuild/linux-riscv64 | 0.25.12 | MIT |
| @esbuild/linux-s390x | 0.25.12 | MIT |
| @esbuild/linux-x64 | 0.25.12 | MIT |
| @esbuild/netbsd-arm64 | 0.25.12 | MIT |
| @esbuild/netbsd-x64 | 0.25.12 | MIT |
| @esbuild/openbsd-arm64 | 0.25.12 | MIT |
| @esbuild/openbsd-x64 | 0.25.12 | MIT |
| @esbuild/openharmony-arm64 | 0.25.12 | MIT |
| @esbuild/sunos-x64 | 0.25.12 | MIT |
| @esbuild/win32-arm64 | 0.25.12 | MIT |
| @esbuild/win32-ia32 | 0.25.12 | MIT |
| @esbuild/win32-x64 | 0.25.12 | MIT |
| @jridgewell/gen-mapping | 0.3.13 | MIT |
| @jridgewell/remapping | 2.3.5 | MIT |
| @jridgewell/resolve-uri | 3.1.2 | MIT |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT |
| @jridgewell/trace-mapping | 0.3.31 | MIT |
| @napi-rs/lzma-linux-x64-gnu | 1.5.1 | MIT |
| @rollup/rollup-android-arm-eabi | 4.64.5 | MIT |
| @rollup/rollup-android-arm64 | 4.64.5 | MIT |
| @rollup/rollup-darwin-arm64 | 4.64.5 | MIT |
| @rollup/rollup-darwin-x64 | 4.64.5 | MIT |
| @rollup/rollup-freebsd-arm64 | 4.64.5 | MIT |
| @rollup/rollup-freebsd-x64 | 4.64.5 | MIT |
| @rollup/rollup-linux-arm-gnueabihf | 4.64.5 | MIT |
| @rollup/rollup-linux-arm-musleabihf | 4.64.5 | MIT |
| @rollup/rollup-linux-arm64-gnu | 4.64.5 | MIT |
| @rollup/rollup-linux-arm64-musl | 4.64.5 | MIT |
| @rollup/rollup-linux-loong64-gnu | 4.64.5 | MIT |
| @rollup/rollup-linux-loong64-musl | 4.64.5 | MIT |
| @rollup/rollup-linux-ppc64-gnu | 4.64.5 | MIT |
| @rollup/rollup-linux-ppc64-musl | 4.64.5 | MIT |
| @rollup/rollup-linux-riscv64-gnu | 4.64.5 | MIT |
| @rollup/rollup-linux-riscv64-musl | 4.64.5 | MIT |
| @rollup/rollup-linux-s390x-gnu | 4.64.5 | MIT |
| @rollup/rollup-linux-x64-gnu | 4.64.5 | MIT |
| @rollup/rollup-linux-x64-musl | 4.64.5 | MIT |
| @rollup/rollup-openbsd-x64 | 4.64.5 | MIT |
| @rollup/rollup-openharmony-arm64 | 4.64.5 | MIT |
| @rollup/rollup-win32-arm64-msvc | 4.64.5 | MIT |
| @rollup/rollup-win32-ia32-msvc | 4.64.5 | MIT |
| @rollup/rollup-win32-x64-gnu | 4.64.5 | MIT |
| @rollup/rollup-win32-x64-msvc | 4.64.5 | MIT |
| @types/babel__core | 7.20.5 | MIT |
| @types/babel__generator | 7.27.0 | MIT |
| @types/babel__template | 7.4.4 | MIT |
| @types/babel__traverse | 7.28.0 | MIT |
| @types/estree | 1.0.9 | MIT |
| @types/node | 22.15.3 | MIT |
| @types/prop-types | 15.7.15 | MIT |
| @types/react | 18.3.22 | MIT |
| @types/react-dom | 18.3.5 | MIT |
| @vitejs/plugin-react | 4.4.1 | MIT |
| baseline-browser-mapping | 2.11.28 | Apache-2.0 |
| browserslist | 4.29.3 | MIT |
| caniuse-lite | 1.0.30001815 | CC-BY-4.0 |
| convert-source-map | 2.0.0 | MIT |
| csstype | 3.2.3 | MIT |
| debug | 4.4.3 | MIT |
| electron-to-chromium | 1.5.452 | ISC |
| esbuild | 0.25.12 | MIT |
| escalade | 3.2.0 | MIT |
| fdir | 6.5.0 | MIT |
| fsevents | 2.3.3 | MIT |
| gensync | 1.0.0-beta.2 | MIT |
| js-tokens | 4.0.0 | MIT |
| jsesc | 3.1.0 | MIT |
| json5 | 2.2.3 | MIT |
| loose-envify | 1.4.0 | MIT |
| lru-cache | 5.1.1 | ISC |
| ms | 2.1.3 | MIT |
| nanoid | 3.3.20 | MIT |
| node-releases | 2.0.58 | MIT |
| picocolors | 1.1.1 | ISC |
| picomatch | 4.0.7 | MIT |
| postcss | 8.5.29 | MIT |
| react | 18.3.1 | MIT |
| react-dom | 18.3.1 | MIT |
| react-refresh | 0.17.0 | MIT |
| rollup | 4.64.5 | MIT |
| scheduler | 0.23.2 | MIT |
| semver | 6.3.1 | ISC |
| source-map-js | 1.2.2 | BSD-3-Clause |
| tinyglobby | 0.2.17 | MIT |
| typescript | 5.8.3 | Apache-2.0 |
| undici-types | 6.21.0 | MIT |
| update-browserslist-db | 1.3.4 | MIT |
| vite | 6.4.4 | MIT |
| yallist | 3.1.1 | ISC |

The npm table includes optional platform packages retained in
`dashboard/package-lock.json`, even when npm does not install them on the
current platform. It is generated from each lock entry's recorded `license`
field; regenerate it whenever the npm lock changes.
