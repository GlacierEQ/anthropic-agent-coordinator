# Anthropic Agent Coordinator

[![Agent Coordinator Verification](https://github.com/GlacierEQ/anthropic-agent-coordinator/actions/workflows/ci.yml/badge.svg)](https://github.com/GlacierEQ/anthropic-agent-coordinator/actions/workflows/ci.yml)

**Version:** `1.0.0`  
**Canonical repository:** `GlacierEQ/anthropic-agent-coordinator`  
**Canonical branch:** `master`  
**Verification state:** `PARTIALLY_VERIFIED` while the repository-native promotion branch is under review  
**Target evidence:** `TEST`

A deterministic specialist-task scheduler that respects dependency order, a shared global token budget, and aggregate per-role capacity—without treating partial funding as completed work.

This independent portfolio project explores agent-orchestration architecture. It does not claim Anthropic employment, endorsement, affiliation, or use inside Anthropic systems.

<!-- README-MESH:BEGIN -->

## For recruiters and non-technical reviewers

### What this project solves

Multi-agent systems often look impressive until resources become constrained. A task may be declared “done” after receiving only part of what it needs, dependent work may begin before its prerequisite is truly complete, and a polished summary may hide which work was actually deferred.

This coordinator makes those decisions explicit and reviewable.

It accepts specialist tasks with dependencies and estimated token requirements, then produces a deterministic execution plan that shows:

- which tasks are fully funded and assigned;
- which wave each assignment belongs to;
- how much global budget has been consumed;
- how much aggregate capacity each specialist role has used;
- which tasks were deferred and why;
- which downstream tasks remain blocked by incomplete prerequisites.

### Why it is valuable

The project demonstrates practical orchestration judgment rather than a collection of prompts:

- **No fabricated completion.** A task is assigned only when its entire estimate fits.
- **Dependency integrity.** Deferred prerequisites never unlock downstream work.
- **Bounded specialists.** Role ceilings apply across all tasks assigned to that role, not independently to each task.
- **Deterministic output.** The same ordered graph and policy produce the same plan.
- **Visible tradeoffs.** Budget pressure becomes structured deferral evidence instead of hidden truncation.
- **Fail-fast inputs.** Duplicate IDs, missing dependencies, cycles, invalid estimates, and invalid budgets are rejected before scheduling.

### Proof in 60 seconds

| Open or run | What it demonstrates |
|---|---|
| [`src/anthropic_agent_coordinator/coordinator.py`](src/anthropic_agent_coordinator/coordinator.py) | Typed task model, graph validation, scheduling semantics, and machine result contract. |
| [`tests/test_coordinator.py`](tests/test_coordinator.py) | Adversarial tests for budgets, roles, dependencies, cycles, and deterministic results. |
| [`tests/test_verification.py`](tests/test_verification.py) | Failure-safe JUnit receipts and portable README enforcement. |
| [`scripts/verify_junit.py`](scripts/verify_junit.py) | Hashed, atomic conversion of standard test output into evidence. |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Package, CLI, documentation, and test verification on three Python versions. |
| [`HELIX_STRAND.md`](HELIX_STRAND.md) | This repository's responsibility in the larger portfolio system. |

### Run the nominal scenario

```bash
python -m pip install -e ".[dev]"
agent-coordinate
```

The command emits JSON rather than narrative prose so people, tests, and connected systems can inspect the same result.

## For senior engineers and domain experts

### Scheduling contract

A task is represented by four fields:

```python
Task(
    id="implement",
    role=Role.IMPLEMENT,
    tokens_est=6_000,
    deps=("design",),
)
```

The coordinator evaluates two resource boundaries:

1. a global token budget shared by every role;
2. an aggregate capacity for each specialist role.

A task becomes assignable only when:

- every declared dependency is known;
- the dependency graph is acyclic;
- every prerequisite has actually been assigned and completed in an earlier wave;
- the task's **full** estimate fits the remaining global budget;
- the task's **full** estimate fits the remaining aggregate role capacity.

There is intentionally no partial-completion state. Partial execution may be valid in another system, but it would require a separate checkpoint and continuation contract rather than silently reusing `complete`.

### Architecture

```text
Ordered task declarations
          │
          ▼
Identity + resource validation
          │
          ▼
Dependency existence + cycle validation
          │
          ▼
Stable readiness waves
          │
    ┌─────┴─────────────┐
    ▼                   ▼
Full assignment      Explicit deferral
    │             global • role • dependency
    └──────────┬────────┘
               ▼
Typed CoordinationResult
human review • JSON • tests • downstream tools
```

### Correctness properties

| Property | Enforcement |
|---|---|
| Unique task identity | Duplicate task IDs fail before scheduling. |
| Referential integrity | Unknown dependency IDs fail before scheduling. |
| Acyclic graph | Depth-first cycle detection returns a readable cycle trace. |
| Positive resources | Boolean, fractional, string, zero, and negative resource values are rejected. |
| Full-funding completion | Assigned tokens always equal the task estimate. |
| Aggregate role limits | Usage is accumulated across every assignment for the same role. |
| Global conservation | Total assigned tokens cannot exceed the declared global budget. |
| Dependency safety | Only fully assigned prerequisites enter the completed set. |
| Stable planning | Input order breaks readiness ties deterministically. |
| Explicit non-completion | Deferred tasks carry a structured reason and remaining-resource context. |

### Deferral semantics

`DeferralReason` is a closed machine-readable enum:

- `global_budget` — the full estimate exceeds remaining shared budget;
- `role_capacity` — the full estimate exceeds remaining capacity for the task's role;
- `dependency_not_completed` — one or more prerequisites were not assigned.

A deferred record includes the task, role, estimate, remaining global budget, remaining role capacity, and blocking dependency IDs where applicable.

### Result contract

```json
{
  "schema": "glaciereq.agent-coordinator.result.v1",
  "complete": false,
  "global_budget": 5000,
  "used_tokens": 0,
  "remaining_tokens": 5000,
  "role_caps": {},
  "role_usage": {},
  "assignments": [],
  "deferred": [
    {
      "task": "oversized",
      "reason": "global_budget",
      "tokens_est": 6000,
      "blocking_dependencies": []
    }
  ]
}
```

The actual result contains all roles and complete resource context. The abbreviated example highlights the stable schema rather than duplicating every field.

### Complexity and tradeoffs

- Identity, unknown-dependency, and cycle validation are linear in graph size aside from deterministic reporting and ordering costs.
- Scheduling favors transparent stable waves over an opaque optimizer. The current ordered readiness scan is appropriate for small and medium orchestration graphs and prioritizes explainability.
- This is not a general-purpose constraint solver, preemptive scheduler, or distributed execution engine.
- Token estimates are caller-provided planning inputs; the coordinator validates and allocates them but does not predict them.
- Fairness is deterministic input order. Weighted fairness, deadlines, retries, checkpointed partial work, and dynamic reprioritization require explicit future policy rather than accidental behavior.

### Package and command surface

```bash
# Install
python -m pip install -e ".[dev]"
python -m pip check

# Quality and importability
ruff check src tests scripts
python -m compileall -q src tests scripts

# Build both distribution formats
python -m build --outdir artifacts/dist

# Demonstration
agent-coordinate

# Public README contract
agent-coordinator-verify-readme

# Behavioral tests and standard JUnit evidence
python -m pytest --junitxml=artifacts/pytest.xml
python scripts/verify_junit.py \
  --junit artifacts/pytest.xml \
  --pytest-exit-code 0 \
  --output artifacts/test-receipt.json
```

### Evidence behavior

The receipt schema is `glaciereq.agent-coordinator.test-receipt.v1`.

The verifier records:

- repository and revision identity;
- Python version;
- pytest exit status;
- test, failure, error, and skip counts;
- SHA-256 of the JUnit artifact;
- start and completion timestamps;
- evidence level and conclusion.

A missing or malformed JUnit document produces `FAILED` evidence. A zero-test report remains `UNVERIFIED`. Any pytest, failure, or error signal produces `FAILED`. The receipt is written through an exclusive temporary file and atomically replaces any stale result.

### Language fit

| Language / format | Responsibility | Why it fits | Proof |
|---|---|---|---|
| Python 3.11+ | Typed graph validation, deterministic scheduling, CLI, and evidence tooling | Fast reviewability and strong standard-library support for this control-plane workload | Python 3.11–3.13 CI |
| JSON | Coordination output and verification receipts | Stable interchange for humans, tests, and AI/tooling consumers | Schema assertions and CLI gate |
| JUnit XML | Test-runner interoperability | Standard CI artifact independent of a custom test framework | Parsed, counted, and SHA-256 bound into the receipt |
| YAML | GitHub Actions verification policy | Native workflow declaration | Read-only repository-native CI |
| Markdown | Recruiter, engineering, and machine context | One public document with distinct audience layers | README contract gate |

No language is present merely to increase the language count. New languages belong only at a workload boundary with measurable correctness, interoperability, safety, or performance value.

## For AI systems and toolchains

### Machine contract

```yaml
schema: glaciereq.readme.v1
profile: glaciereq.readme-impact.v2-draft
repository: GlacierEQ/anthropic-agent-coordinator
canonical_branch: master
purpose: >-
  Validate a dependency graph and create a deterministic specialist-task plan
  under a shared global token budget and aggregate per-role capacities.
status:
  state: PARTIALLY_VERIFIED
  target_evidence: TEST
  promotion_rule: >-
    Promote only after the repository-native Python 3.11, 3.12, and 3.13
    matrix passes packaging, lint, compilation, CLI, README, and positive-count tests.
  verified_scope:
    - README Mesh identity and responsibility are established
    - typed scheduler, tests, and receipt tooling are reviewable in source
  blocked_scope:
    - agent execution, provider calls, and irreversible external actions
    - partial-task continuation without a checkpoint contract
  unverified_scope:
    - canonical-branch package and test result until this promotion change is merged
    - production scale, fairness, latency, and reliability outside repository CI
interfaces:
  inputs:
    - ordered Task objects
    - positive global token budget
    - optional positive role-cap overrides
  outputs:
    - glaciereq.agent-coordinator.result.v1
    - full assignments grouped by deterministic wave
    - structured deferrals and blocking dependencies
    - aggregate role and global token accounting
  commands:
    install: python -m pip install -e ".[dev]"
    demo: agent-coordinate
    lint: ruff check src tests scripts
    build: python -m build --outdir artifacts/dist
    test: python -m pytest --junitxml=artifacts/pytest.xml
    verify_readme: agent-coordinator-verify-readme
evidence:
  workflow: .github/workflows/ci.yml
  test_receipt_schema: glaciereq.agent-coordinator.test-receipt.v1
  result_schema: glaciereq.agent-coordinator.result.v1
  receipt_builder: scripts/verify_junit.py
  tests:
    - tests/test_coordinator.py
    - tests/test_verification.py
relationships:
  - target: GlacierEQ/anthropic-safety-monitor
    relation: VERIFIED_BY
    combined_value: >-
      Coordination policy and independent safety evaluation remain separate,
      composable responsibilities.
  - target: GlacierEQ/AKOS
    relation: GOVERNED_BY
    combined_value: >-
      AKOS supplies authority, evidence, persistence, and completion semantics
      around deterministic task motion.
  - target: GlacierEQ/job-app-helix
    relation: REPRESENTED_BY
    combined_value: >-
      Job-App Helix publishes the repository's human and machine role inside
      the evidence-bound portfolio mesh.
limits:
  - Scheduling does not execute agents or call external providers.
  - Token estimates are supplied, not inferred.
  - Deterministic input order is not a claim of optimal fairness.
  - Repository-local CI is not production deployment evidence.
```

### Stable import surface

```python
from anthropic_agent_coordinator import (
    CoordinationError,
    DeferralReason,
    Role,
    Task,
    build_plan,
    coordinate,
)
```

`build_plan` returns the typed `CoordinationResult`. `coordinate` remains as a compatibility wrapper returning the JSON-ready dictionary.

### Mesh resources

- [Canonical README Mesh](https://github.com/GlacierEQ/job-app-helix/blob/main/manifests/readme_mesh.json)
- [README Mesh Protobuf schema](https://github.com/GlacierEQ/job-app-helix/blob/main/proto/readme_mesh.proto)
- [AKOS governance layer](https://github.com/GlacierEQ/AKOS)
- [Independent safety monitor](https://github.com/GlacierEQ/anthropic-safety-monitor)

<!-- README-MESH:END -->

## Repository map

```text
src/anthropic_agent_coordinator/   typed scheduler and installed CLI
src/coordinator.py                 backward-compatible import and script entry point
tests/                             scheduler and evidence regression tests
scripts/                           README and JUnit receipt verification
.github/workflows/ci.yml           repository-native verification matrix
```

## Fleet operations

Integrity baselines and health sidecars, when present, are transparent multi-repository operations. See [`SECURITY_AND_FLEET_OPS.md`](SECURITY_AND_FLEET_OPS.md).

## Portfolio role

See [`HELIX_STRAND.md`](HELIX_STRAND.md) for this repository's role in the portfolio helix.
