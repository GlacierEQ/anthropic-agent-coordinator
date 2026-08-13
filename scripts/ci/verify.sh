#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="${GITHUB_WORKSPACE:-$PWD}"
readonly ARTIFACT_DIR="$ROOT/.verification-artifacts"
readonly DIST_DIR="$ARTIFACT_DIR/dist"
readonly VERIFY_VENV="$ROOT/.coordinator-verify-venv"
readonly WHEEL_VENV="$ROOT/.coordinator-wheel-venv"

cleanup() {
  rm -rf "$VERIFY_VENV" "$WHEEL_VENV"
}
trap cleanup EXIT

cd "$ROOT"
readonly SOURCE_SHA="$(git rev-parse HEAD)"
export SOURCE_SHA
install -d -m 700 "$ARTIFACT_DIR" "$DIST_DIR"
rm -rf "$DIST_DIR"/*

python3 -m venv "$VERIFY_VENV"
readonly PYTHON="$VERIFY_VENV/bin/python"
readonly RUFF="$VERIFY_VENV/bin/ruff"
readonly COORDINATE="$VERIFY_VENV/bin/agent-coordinate"
readonly VERIFY_README="$VERIFY_VENV/bin/agent-coordinator-verify-readme"

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -e ".[dev]"
"$PYTHON" -m pip check

"$RUFF" check src tests scripts
"$PYTHON" -m compileall -q src tests scripts
"$PYTHON" -m build --outdir "$DIST_DIR"

mapfile -t wheels < <(find "$DIST_DIR" -maxdepth 1 -type f -name '*.whl' -print | sort)
mapfile -t sdists < <(find "$DIST_DIR" -maxdepth 1 -type f -name '*.tar.gz' -print | sort)
[[ ${#wheels[@]} -eq 1 ]] || {
  printf 'expected exactly one wheel, found %s\n' "${#wheels[@]}" >&2
  exit 65
}
[[ ${#sdists[@]} -eq 1 ]] || {
  printf 'expected exactly one source distribution, found %s\n' "${#sdists[@]}" >&2
  exit 65
}

python3 -m venv "$WHEEL_VENV"
"$WHEEL_VENV/bin/python" -m pip install --upgrade pip
"$WHEEL_VENV/bin/python" -m pip install "${wheels[0]}"
"$WHEEL_VENV/bin/python" -m pip check
"$WHEEL_VENV/bin/python" - <<'PY'
import coordinator
import anthropic_agent_coordinator as package

if coordinator.SchedulingPolicy.STABLE_PRIORITY.value != "stable_priority":
    raise SystemExit("compatibility module omitted the scheduling policy")
if package.DEFAULT_ROLE_CAPS[package.Role.EXPLORE] != 4_000:
    raise SystemExit("installed package exposed the wrong default role capacity")
if coordinator.ANSWER != 42:
    raise SystemExit("installed compatibility module changed the historical sentinel")
PY
"$WHEEL_VENV/bin/agent-coordinator-verify-readme"

"$PYTHON" scripts/verify_readme_contract.py
"$COORDINATE" > "$ARTIFACT_DIR/demo.json"
"$PYTHON" - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path(".verification-artifacts/demo.json").read_text(encoding="utf-8"))
if payload.get("schema") != "glaciereq.agent-coordinator.result.v1":
    raise SystemExit("demo emitted the wrong result schema")
if payload.get("scheduling_policy") != "stable_priority":
    raise SystemExit("demo emitted the wrong scheduling policy")
if payload.get("complete") is not True:
    raise SystemExit("nominal demo did not complete")
if payload.get("used_tokens") != 12_000:
    raise SystemExit("nominal demo token accounting changed")
PY

set +e
"$PYTHON" -m pytest --junitxml="$ARTIFACT_DIR/pytest.xml"
pytest_status=$?
set -e
"$PYTHON" scripts/verify_junit.py \
  --junit "$ARTIFACT_DIR/pytest.xml" \
  --pytest-exit-code "$pytest_status" \
  --expected-sha "$SOURCE_SHA" \
  --output "$ARTIFACT_DIR/test-receipt.json"

"$PYTHON" - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path

artifact_dir = Path(".verification-artifacts")
dist_dir = artifact_dir / "dist"
files = sorted(path for path in dist_dir.iterdir() if path.is_file())
manifest = {
    "schema": "glaciereq.agent-coordinator.public-runner-receipt.v1",
    "repository": os.getenv("GITHUB_REPOSITORY", "GlacierEQ/anthropic-agent-coordinator"),
    "commit": os.environ["SOURCE_SHA"],
    "github_event_sha": os.getenv("GITHUB_SHA", "LOCAL"),
    "run_id": os.getenv("GITHUB_RUN_ID", "LOCAL"),
    "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "1"),
    "python": platform.python_version(),
    "distributions": [
        {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in files
    ],
}
(artifact_dir / "public-runner-receipt.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
