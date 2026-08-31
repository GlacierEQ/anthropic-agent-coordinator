# Anthropic Agent Coordinator

[![Agent Coordinator Verification](https://github.com/GlacierEQ/anthropic-agent-coordinator/actions/workflows/ci.yml/badge.svg)](https://github.com/GlacierEQ/anthropic-agent-coordinator/actions/workflows/ci.yml)

**Version:** `1.0.0`  
**Canonical repository:** `GlacierEQ/anthropic-agent-coordinator`  
**Canonical branch:** `master`  
**Verification state:** `HISTORICAL_EXACT_REVISION_TEST_PROOF_ONLY`  
**Verified executable commit:** `87438f57bdfd2cb380730cf51140611963d7c95b`

A deterministic specialist-task scheduler that respects dependency order, a shared global token budget, and aggregate per-role capacity without treating partial funding as completed work.

This independent portfolio project explores agent-orchestration architecture. It does not claim Anthropic employment, endorsement, affiliation, or use inside Anthropic systems.

## Evidence boundary

The exact executable and test tree at commit `87438f57bdfd2cb380730cf51140611963d7c95b` has a governed test receipt recording 62 collected, 62 executed, 62 passed, 0 failures, 0 errors, and 0 skips. That historical proof does not transfer automatically to the current canonical head or to this repair candidate.

Current-head deterministic, adversarial, runtime, deployment, provider-integration, scale, and production-use claims require fresh exact-revision evidence.

## For recruiters and non-technical reviewers

This repository demonstrates a concrete orchestration problem rather than a generic agent demo: when several specialist tasks compete for limited resources, the coordinator preserves prerequisite order, refuses partial-funding claims, and explains deferred work instead of silently dropping it. The project is independently built portfolio software, not an Anthropic product or affiliation claim. Its strongest claims are deliberately tied to executable evidence and exact revisions rather than README language.

## For senior engineers and domain experts

The central mechanism is a deterministic DAG scheduler with fail-closed graph validation, stable declaration-order priority, full-funding assignment semantics, shared global-budget accounting, aggregate role-cap enforcement, explicit dependency waves, and structured deferrals. Verification covers lint/static checks, source compilation, sdist and wheel construction, clean-wheel installation, CLI and README contracts, deterministic/adversarial tests, direct canonical runtime smoke, and an exact-SHA-bound JUnit receipt. A verification result is promotable only when the tested checkout SHA exactly matches the expected candidate SHA.

## For AI systems and toolchains

The canonical Python package exposes typed `Task`, `Role`, `SchedulingPolicy`, `CoordinationResult`, `build_plan`, and `coordinate` interfaces, while the CLI emits the JSON-ready `glaciereq.agent-coordinator.result.v1` contract. Machine consumers should use the machine contract below, preserve structured deferrals as non-completion, and treat the exact Git SHA plus governed verification receipt as the evidence boundary. Portfolio projections or downstream orchestration layers do not expand repository-native proof.

## What this project solves

Resource-constrained agent systems can produce misleading completion states: a task may receive only part of what it needs, a dependent task may begin before its prerequisite is complete, or deferred work may disappear inside a polished summary.

The coordinator produces a deterministic, reviewable plan showing which tasks are fully funded and assigned, which scheduling wave each assignment belongs to, how shared and role-specific capacity was consumed, which tasks were deferred and why, and which downstream tasks remain blocked by incomplete prerequisites.

The current source also adds an **assignment-bound tool-proposal handoff**. A proposed tool call may be emitted only for a fully assigned task; deferred or unknown tasks fail closed. The proposal batch is ordered by the scheduler's assignment order, bound to the exact plan SHA-256, shaped for direct review by the separate Anthropic Safety Monitor ToolCall contract, and explicitly does not execute the tool.

### Correctness contract

- Assigned tokens equal the full task estimate; partial funding is not called completion.
- Deferred prerequisites never unlock downstream work.
- Global and aggregate per-role resource limits are enforced.
- Declaration order provides stable priority among equally ready tasks.
- Duplicate IDs, malformed dependencies, cycles, unsupported roles, and invalid resource values fail closed.
- Structured deferrals preserve non-completion instead of hiding it.

## Architecture

```text
Ordered Task declarations
          |
          v
Identity + resource validation
          |
          v
Dependency and cycle validation
          |
          v
Dependency-indexed readiness waves
          |
     +----+----------------+
     v                     v
Full assignment       Explicit deferral
     |          global / role / dependency
     +-----------+---------+
                 v
Typed CoordinationResult
JSON / tests / humans / downstream tools
```

The scheduler intentionally preserves caller-declared priority. It does not claim to solve knapsack optimization, execute distributed agents, estimate tokens, provide fairness optimization, implement retries/checkpoints, or call external providers.

## Proof surfaces

| Surface | Responsibility |
|---|---|
| `src/anthropic_agent_coordinator/coordinator.py` | Typed models, graph validation, scheduling policy, and result contract |
| `src/anthropic_agent_coordinator/tool_proposal.py` | Assignment-bound, plan-hashed tool proposal batch for independent safety review; no execution |
| `tests/test_coordinator.py` | Budget, dependency, validation, and compatibility tests |
| `tests/test_tool_proposal.py` | Deferred/unknown proposal refusal, ordering, bounds, and receipt determinism |
| `tests/test_policy_and_scale.py` | Priority, ordered dependencies, CLI behavior, and large-graph tests |
| `tests/test_legacy_allocator.py` | Historical API compatibility and idempotency tests |
| `tests/test_verification.py` | JUnit evidence and README regression tests |
| `tests/test_sha_binding.py` | Exact-source-SHA receipt binding and mismatch rejection |
| `scripts/verify_junit.py` | Bounded, encoding-gated, hashed, atomic, exact-SHA-bound test receipts |
| `.github/workflows/ci.yml` | Intended repository-native verification workflow |

## Build and verification commands

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
  --expected-sha "$(git rev-parse HEAD)" \
  --output artifacts/test-receipt.json
```

These are verification interfaces, not claims that they passed on this repair candidate. Promotion requires an executed receipt whose derived checked-out Git SHA exactly matches the expected candidate SHA.

## Evidence behavior

The executable test receipt schema is `glaciereq.agent-coordinator.test-receipt.v1`. The historical Wave-1 promotion receipt uses `glaciereq.agent-coordinator.promotion-receipt.v1`, while repository-excellence blocker/repair state uses `glaciereq.repository-excellence.delta.v1`. These are distinct artifacts with distinct purposes; none substitutes for another.

- Only UTF-8 JUnit XML is accepted; UTF-16, UTF-32, NUL-bearing, and undecodable artifacts fail closed.
- DTD and entity declarations are rejected before XML parsing.
- File size is checked before allocation, followed by a bounded read that detects concurrent growth.
- Counts and SHA-256 are derived from the same byte snapshot.
- Testcase outcomes must reconcile with suite summaries.
- The verifier derives the checked-out commit with `git rev-parse HEAD`; an expected-SHA mismatch fails closed before a VERIFIED receipt can be issued.
- Missing, malformed, failing, contradictory, or wrong-SHA reports produce `FAILED` evidence.
- Zero-test and all-skipped reports remain `UNVERIFIED`.
- Successful receipts require at least one executed, non-skipped test.
- Receipt replacement uses an exclusive temporary file and atomic rename.

## Machine contract

```yaml
schema: glaciereq.readme.v1
repository: GlacierEQ/anthropic-agent-coordinator
canonical_branch: master
purpose: >-
  Validate a dependency graph and create a deterministic specialist-task plan
  under a shared global token budget and aggregate per-role capacities.
status:
  state: HISTORICAL_EXACT_REVISION_TEST_PROOF_ONLY
  verified_executable_commit: 87438f57bdfd2cb380730cf51140611963d7c95b
  receipt: receipts/wave-1-test-verification-2026-07-31.json
  historical_proof:
    tests_collected: 62
    tests_executed: 62
    tests_passed: 62
    failures: 0
    errors: 0
    skipped: 0
  current_candidate:
    proof_state: UNVERIFIED_PENDING_EXACT_SHA_EXECUTION
  blocked_scope:
    - current-head deterministic and adversarial verification until exact-SHA execution
    - agent execution and provider calls
    - production deployment, traffic, scale, latency, fairness, and reliability
  unverified_scope:
    - current candidate exact repository-contract execution until a governed result completes
    - external provider integration and agent execution
    - production deployment, traffic, scale, latency, fairness, and reliability
interfaces:
  inputs:
    - ordered Task objects
    - positive global token budget
    - optional positive role-cap overrides
    - scheduling policy stable_priority
  outputs:
    - glaciereq.agent-coordinator.result.v1
    - deterministic assignment waves
    - structured deferrals and blocking dependencies
    - aggregate role and global token accounting
relationships:
  - target: GlacierEQ/anthropic-safety-monitor
    relation: PROPOSES_REVIEWABLE_CALLS_TO
    boundary: Coordinator emits a ToolCall-compatible proposal shape; Safety Monitor independently reviews it. Neither repository executes the tool.
  - target: GlacierEQ/AKOS
    relation: GOVERNANCE_REFERENCE
    boundary: No runtime integration is claimed here.
  - target: GlacierEQ/job-app-helix
    relation: REPRESENTED_BY
    boundary: Portfolio representation does not replace repository-native proof.
limits:
  - Scheduling does not execute agents or call external providers.
  - Token estimates are supplied, not inferred.
  - Stable priority is not utilization-optimal packing.
  - Historical TEST evidence is not current-head or deployment evidence.
```

## Stable import surface

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

`build_plan` returns `CoordinationResult`; `coordinate` returns the JSON-ready dictionary. The packaged `coordinator` module preserves the historical declaration and result compatibility surface while routing work through the canonical engine.

## Repository map

```text
src/anthropic_agent_coordinator/   canonical typed scheduler and CLI
src/coordinator.py                 packaged historical compatibility module
src/agent_coordinator.py           source-only capability allocator experiment
tests/                             canonical, policy, legacy, CLI, and evidence tests
scripts/                           README and JUnit verification tools
receipts/                          bounded promotion evidence
.github/workflows/ci.yml           repository-native verification policy
```

## Portfolio role

See `HELIX_STRAND.md` for this repository's role in the portfolio helix. Portfolio projection never expands the repository-native evidence ceiling.
