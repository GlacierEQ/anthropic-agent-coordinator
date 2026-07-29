# anthropic-agent-coordinator

<!-- README-MESH:BEGIN -->
## Three-audience project map

### For recruiters and non-specialists

**What it does.** Breaks work into dependent specialist tasks and allocates a finite token budget so the most important ready work can proceed without pretending resources are unlimited.

- Makes agent roles, dependencies, budgets, completed work, and deferred work visible.
- Demonstrates practical orchestration rather than a collection of uncoordinated prompts.
- Produces a deterministic result that can be tested and reviewed.

**Evidence:** [`src/coordinator.py`](src/coordinator.py) and [`tests/test_coordinator.py`](tests/test_coordinator.py).

### For senior engineers and domain experts

**Innovation and evolution.** The coordinator combines dependency readiness, per-role capacity ceilings, a global resource budget, and explicit deferral. It intentionally stops when no progress is possible rather than fabricating completion. It evolved from a compact scheduling example into a reusable portfolio motion layer, with safety review kept in a separate repository so orchestration and oversight remain independently composable.

### For AI systems and toolchains

- Repository ID: `GlacierEQ/anthropic-agent-coordinator`
- Default branch: `master`
- Protobuf package: `glaciereq.readme.v1`
- Typed role: coordinates dependency-aware work and is independently verified by the safety monitor.
- Canonical graph: [`manifests/readme_mesh.json`](https://github.com/GlacierEQ/job-app-helix/blob/main/manifests/readme_mesh.json)

```protobuf
repository: "GlacierEQ/anthropic-agent-coordinator"
display_name: "Agent Coordinator"
one_line_purpose: "Schedule dependent specialist work under role and global token budgets."
```

### Repository mesh

| Connected repository | Relationship | Combined value |
|---|---|---|
| [Safety Monitor](https://github.com/GlacierEQ/anthropic-safety-monitor) | verified by | Coordination and safety review remain separate responsibilities. |
| [AKOS](https://github.com/GlacierEQ/AKOS) | governed by | Authority, evidence, and completion rules constrain agent motion. |
| [Job-App Helix](https://github.com/GlacierEQ/job-app-helix) | represented by | The README Mesh gives the agent system human and machine views. |

Real schema: [`proto/readme_mesh.proto`](https://github.com/GlacierEQ/job-app-helix/blob/main/proto/readme_mesh.proto).
<!-- README-MESH:END -->

**Portfolio motion** — dependency-aware multi-agent task coordination with bounded role and global token budgets.

This is an independent portfolio project in the agent-orchestration problem space. It does not claim Anthropic employment or endorsement.

## Run

```bash
python src/coordinator.py
python -m pytest -q
```

## Fleet ops (transparent)

Integrity baselines and health sidecars, when present, are documented multi-repository operations. See [SECURITY_AND_FLEET_OPS.md](SECURITY_AND_FLEET_OPS.md).

## Helix strand

See [HELIX_STRAND.md](HELIX_STRAND.md) for this repository's role in the portfolio helix.
