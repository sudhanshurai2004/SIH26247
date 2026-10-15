# Versioned contracts

The frozen Stage-1 v1 wire contracts are:

- `scenario.schema.json` — deterministic playback data and precomputed target trajectories.
- `event.schema.json` — idempotent trainee actions at logical session offsets.
- `doctrine.schema.json` — editable, abstract training scoring/decision-tree data.

Their source digests are recorded in `v1_contracts.sha256`; verify them with:

```bash
sha256sum --check contracts/v1_contracts.sha256
```

`contracts/samples/*valid*` must validate and `*invalid*` must fail. YAML
doctrine files are parsed with `yaml.safe_load` before validation.

## Contract v2 (additive)

V2 is a separate native contract family selected only by
`contract_version: "2.0"`:

- `scenario_v2.schema.json` adds synthetic per-target `training_class`,
  assessment truth, outer/inner response zone, and inner-zone reach fields.
- `event_v2.schema.json` preserves the abstract, idempotent event shape under an
  explicit v2 version.
- `doctrine_v2.schema.json` adds class-wise outer/inner response matrices,
  partial-class credit, critical-error penalties, a friendly score cap, and a
  `mean_per_target` session aggregate.

`core.contracts.validate_versioned_payload()` dispatches only from the explicit
payload version; a missing or unsupported version is rejected rather than
inferred. `core.migrations.v1_to_v2` and `scripts/migrate_v1_to_v2.py` provide
an additive v1-to-v2 conversion. The migration retains all v1 fields and fills
only clearly labelled generic synthetic defaults. It does not infer real
training doctrine or tactical data.

## Compatibility rule

`contract_version: "1.0"` is frozen. Do not edit its schemas or samples to add
v2 behavior. A breaking/new semantic capability must use a separately versioned
contract plus explicit migration. Structural schema validation lives here;
playback invariants and executable doctrine checks live in the corresponding
core modules.

All time fields are logical millisecond offsets. Scenario generation and scoring
must not add wall-clock timestamps to a contract payload.
