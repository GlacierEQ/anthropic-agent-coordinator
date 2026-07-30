# Anthropic Agent Coordinator

[![Agent Coordinator Verification](https://github.com/GlacierEQ/anthropic-agent-coordinator/actions/workflows/ci.yml/badge.svg)](https://github.com/GlacierEQ/anthropic-agent-coordinator/actions/workflows/ci.yml)

**Version:** `1.0.0`  
**Canonical repository:** `GlacierEQ/anthropic-agent-coordinator`  
**Canonical branch:** `master`  
**Verification state:** `PARTIALLY_VERIFIED` while the promotion PR is under review  
**Target evidence:** `TEST`

A deterministic specialist-task scheduler that respects dependency order, a shared global token budget, and aggregate per-role capacity without treating partial funding as completed work.

This independent portfolio project explores agent-orchestration architecture. It does not claim Anthropic employment, endorsement, affiliation, or use inside Anthropic systems.

<!-- README-MESH:BEGIN -->

## For recruiters and non-technical reviewers

### What this project solves

Resource-constrained agent systems can produce misleading completion states: a task may receive only part of what it needs, a dependent task may begin before its prerequisite is complete, or deferred work may disappear inside a polished summary.

This coordinator converts those decisions into a deterministic, reviewable plan. It shows:

- which tasks are fully funded and assigned;
- which deterministic wave each assignment belongs to;
- how shared and role-specific capacity was consumed;
- which tasks were deferred and why;
- which downstream tasks remain blocked by incomplete prerequisites.

### Why it matters

- **No fabricated completion.** Assigned tokens equal the full task estimate.
- **Dependency integrity.** Deferred prerequisites never unlock downstream work.
- **Aggregate role limits.** Capacity applies across all work assigned to a role.
- **Explicit priority.** `stable_priority` preserves declaration order among equally ready tasks.
- **Deterministic evidence.** The same ordered graph and resource policy produce the same result.
- **Fail-fast inputs.** Duplicate IDs, malformed dependencies, cycles, unsupported roles, and invalid resource values are rejected.

### Proof in 60 seconds

| Open or run | What it demonstrates |
|---|---|
| [`src/anthropic_agent_coordinator/coordinator.py`](src/anthropic_agent_coordinator/coordinator.py) | Typed models, graph validation, scheduling policy, and result contract. |
| [`tests/test_coordinator.py`](tests/test_coordinator.py) | Adversarial budget, dependency, validation, and canonical compatibility tests. |
| [`tests/test_policy_and_scale.py`](tests/test_policy_and_scale.py) | Explicit priority, ordered dependencies, CLI behavior, and large-graph execution. |
| [`tests/test_legacy_allocator.py`](tests/test_legacy_allocator.py) | Historical module exports, constructor shape, capability matching, and idempotency. |
| [`tests/test_verification.py`](tests/test_verification.py) | JUnit evidence and portable README regression tests. |
| [`scripts/verify_junit.py`](scripts/verify_junit.py) | Bounded, encoding-gated, hashed, atomic test receipts. |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Package, wheel, CLI, documentation, and test verification on Python 3.11–3.13. |

```bash
python -m pip install -e ".[dev]"
agent-coordinate
```

The command emits JSON so people, tests, and connected systems inspect the same result.

## For senior engineers and domain experts

### Scheduling contract

```python
Task(
    id="implement",
    role=Role.IMPLEMENT,
    tokens_est=6_000,
    deps=("design",),
)
```

A task is assigned only when:

1. every dependency exists;
2. the graph is acyclic;
3. every prerequisite was fully assigned in an earlier wave;
4. the complete estimate fits the remaining global budget;
5. the complete estimate fits the remaining aggregate capacity for its role.

Partial execution is deliberately outside this contract. Supporting it would require checkpoint, continuation, retry, and evidence semantics rather than silently reusing `complete`.

### Architecture

```text
Ordered Task declarations
          │
          ▼
Identity + resource validation
          │
          ▼
Iterative dependency and cycle validation
          │
          ▼
Dependency-indexed readiness waves
          │
     ┌────┴───────────────┐
     ▼                    ▼
Full assignment       Explicit deferral
     │          global • role • dependency
     └───────────┬────────┘
                 ▼
Typed CoordinationResult
JSON • tests • humans • downstream tools
```

### Correctness properties

| Property | Enforcement |
|---|---|
| Unique identity | Duplicate task IDs fail before scheduling. |
| Referential integrity | Unknown dependencies fail before scheduling. |
| Acyclic graph | Iterative traversal returns a readable cycle trace without recursion-depth limits. |
| Ordered dependency contract | Sets, generators, bare strings, bytes, and non-string entries are rejected. |
| Positive resources | Boolean, fractional, string, zero, and negative values are rejected. |
| Immutable defaults | Public default role capacities cannot be mutated at runtime. |
| Full-funding completion | Assignment tokens always equal the declared estimate. |
| Aggregate role limits | Usage accumulates across every assignment for the role. |
| Global conservation | Total assigned tokens cannot exceed the global budget. |
| Dependency safety | Only fully assigned tasks enter the completed set. |
| Stable priority | Declaration order resolves ties among tasks ready in the same wave. |
| Explicit non-completion | Deferred records carry a reason and remaining-resource context. |

### Complexity and policy tradeoffs

Identity, dependency indexing, readiness propagation, and iterative cycle validation are linear in task and dependency count, apart from stable ordering and deterministic reporting costs. The scheduler intentionally preserves caller-declared priority; it does not claim to solve knapsack optimization or maximize aggregate utilization by reordering work.

It is not a distributed executor, general constraint solver, token estimator, fairness optimizer, retry engine, or checkpoint manager.

### Deferral reasons

- `global_budget` — the full estimate exceeds remaining shared budget;
- `role_capacity` — the full estimate exceeds remaining capacity for the role;
- `dependency_not_completed` — one or more prerequisites were not assigned.

### Build and verification

```bash
python -m pip install -e ".[dev]"
python -m pip check
ruff check src tests scripts
python -m compileall -q src tests scripts
python -m build --outdir artifacts/dist
agent-coordinator-verify-readme
agent-coordinate
python -m pytest --junitxml=artifacts/pytest.xml
python scripts/verify_junit.py \
  --junit artifacts/pytest.xml \
  --pytest-exit-code 0 \
  --output artifacts/test-receipt.json
```

The wheel gate installs the built artifact into an isolated environment, imports both `anthropic_agent_coordinator` and the compatibility module `coordinator`, and runs the installed README verifier.

### Evidence behavior

The receipt schema is `glaciereq.agent-coordinator.test-receipt.v1`.

- Only UTF-8 JUnit XML is accepted; UTF-16, UTF-32, NUL-bearing, and undecodable artifacts fail closed.
- DTD and entity declarations are rejected before XML parsing.
- File size is checked before allocation, followed by a bounded read that also detects concurrent growth.
- Counts and SHA-256 are derived from the same byte snapshot.
- Testcase outcomes must reconcile with suite summaries.
- Missing, malformed, failing, or contradictory reports produce `FAILED` evidence.
- Zero-test and all-skipped reports remain `UNVERIFIED`.
- Successful receipts require at least one executed, non-skipped test.
- Receipt replacement uses an exclusive temporary file and atomic rename.

### Language fit

| Language / format | Responsibility | Proof |
|---|---|---|
| Python 3.11+ | Typed scheduling, validation, CLI, compatibility, and evidence tooling | Python 3.11–3.13 matrix |
| JSON | Coordination output and receipts | Schema assertions and CLI gate |
| JUnit XML | Interoperable UTF-8 test evidence | Reconciled and SHA-256-bound receipt |
| YAML | Read-only GitHub Actions policy | Repository-native CI |
| Markdown | Recruiter, engineer, and toolchain contract | Structural README gate |

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
    Promote only after Python 3.11, 3.12, and 3.13 pass package installation,
    lint, compilation, isolated wheel verification, README verification, CLI,
    positive executed-test evidence, and artifact upload.
  verified_scope:
    - README Mesh identity and repository responsibility
    - reviewable typed scheduler, tests, package, and receipt tooling
  blocked_scope:
    - agent execution, provider calls, and irreversible external actions
    - partial-task continuation without a checkpoint contract
  unverified_scope:
    - canonical-branch package and test result until promotion is merged
    - production scale, fairness, latency, and reliability outside repository CI
interfaces:
  inputs:
    - ordered Task objects
    - positive global token budget
    - optional positive role-cap overrides
    - scheduling policy stable_priority
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
    - tests/test_policy_and_scale.py
    - tests/test_legacy_allocator.py
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
      AKOS supplies authority, evidence, persistence, and completion semantics.
  - target: GlacierEQ/job-app-helix
    relation: REPRESENTED_BY
    combined_value: >-
      Job-App Helix publishes this repository inside the evidence-bound mesh.
limits:
  - Scheduling does not execute agents or call external providers.
  - Token estimates are supplied, not inferred.
  - Stable priority is not a claim of utilization-optimal packing.
  - Repository-local CI is not production deployment evidence.
```

### Stable import surface

```python
from anthropic_agent_coordinator import (
    CoordinationError,
    DeferralReason,
    Role,
    SchedulingPolicy,
    Task,
    build_plan,
    coordinate,
)
```

`build_plan` returns `CoordinationResult`; `coordinate` returns the JSON-ready dictionary. The packaged `coordinator` module preserves the historical `Task(id, kind, tokens_est, deps)` declaration, `ANSWER`, string-keyed `ROLE_CAPS`, the original four-field result shape, and the original module/script name while routing work through the canonical engine.

### Mesh resources

- [Canonical README Mesh](https://github.com/GlacierEQ/job-app-helix/blob/main/manifests/readme_mesh.json)
- [README Mesh Protobuf schema](https://github.com/GlacierEQ/job-app-helix/blob/main/proto/readme_mesh.proto)
- [AKOS governance layer](https://github.com/GlacierEQ/AKOS)
- [Independent safety monitor](https://github.com/GlacierEQ/anthropic-safety-monitor)

<!-- README-MESH:END -->

## Repository map

```text
src/anthropic_agent_coordinator/   canonical typed scheduler and CLI
src/coordinator.py                 packaged historical compatibility module
src/agent_coordinator.py           source-only capability allocator experiment
tests/                             canonical, policy, legacy, CLI, and evidence tests
scripts/                           README and JUnit verification tools
.github/workflows/ci.yml           repository-native verification matrix
```

## Fleet operations

Integrity baselines and health sidecars, when present, are transparent multi-repository operations. See [`SECURITY_AND_FLEET_OPS.md`](SECURITY_AND_FLEET_OPS.md).

## Portfolio role

See [`HELIX_STRAND.md`](HELIX_STRAND.md) for this repository's role in the portfolio helix.
