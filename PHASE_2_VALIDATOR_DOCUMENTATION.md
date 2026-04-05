# Phase 2: Comprehensive Validator Documentation

> **Branch:** `feat/agent-plane-capd-patch-v0`  
> **PR:** imagelab#1  
> **Status:** Draft / In-review

---

## Table of Contents

1. [Validator Architecture Overview](#1-validator-architecture-overview)
2. [Validator Module Specifications](#2-validator-module-specifications)
3. [Capability Descriptor (CAPD) Patch](#3-capability-descriptor-capd-patch)
4. [Admission Webhook Integration](#4-admission-webhook-integration)
5. [Full Schema Binding Roadmap](#5-full-schema-binding-roadmap)
6. [Testing Strategy](#6-testing-strategy)
7. [Current Limitations & Follow-Up Tasks](#7-current-limitations--follow-up-tasks)
8. [Complete File Inventory](#8-complete-file-inventory)

---

## 1. Validator Architecture Overview

The imagelab validator stack is organised in three tiers. Each tier adds a distinct layer of trust and enforcement on top of the previous one.

```
┌──────────────────────────────────────────────────────────┐
│                   Tier 3 – Admission Gate                │
│  Kubernetes MutatingAdmissionWebhook / ValidatingWebhook │
│  • Intercepts agentplane resource submissions            │
│  • Calls Tier 2 validators via HTTP side-car             │
│  • Rejects or patches the payload before persistence     │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP / gRPC
┌────────────────────────▼─────────────────────────────────┐
│                  Tier 2 – Contract Validators            │
│  Python CLI modules (`python -m validators.<name>`)      │
│  • ExecutionDecisionValidator                            │
│  • SkillManifestValidator                                │
│  • SessionReceiptValidator                               │
│  • Read JSON from disk, check type discriminator + URN   │
│  • Return structured JSON  { ok, validated, path }       │
└────────────────────────┬─────────────────────────────────┘
                         │ file-path argument
┌────────────────────────▼─────────────────────────────────┐
│                  Tier 1 – Schema Validator                │
│  `make validate` / `tools/validate.sh`                   │
│  • Checks required directory tree is present             │
│  • Detects stray artefacts (.DS_Store, Makefile.bak.*)   │
│  • Gate for CI – runs on every push and pull_request     │
└──────────────────────────────────────────────────────────┘
```

**Data flow for a single artefact submission:**

```
agentplane artefact (JSON)
        │
        ▼
Admission Webhook receives AdmissionReview request
        │
        ▼
Handler writes payload to temp file, invokes Tier 2 validator
        │
        ├─ exit 0 → { ok: true }  → AdmissionResponse: allowed
        └─ exit 1 → { error: … }  → AdmissionResponse: denied (reason forwarded)
```

---

## 2. Validator Module Specifications

All three modules share the same structural pattern (22 lines each).

### 2.1 ExecutionDecisionValidator

**File:** `validators/execution_decision.py`

| Attribute | Value |
|---|---|
| Expected `type` discriminator | `ExecutionDecision` |
| CLI entry point | `python -m validators.execution_decision <json-file>` |
| Success stdout | `{"ok": true, "validated": "ExecutionDecision", "path": "<file>"}` |
| Failure stderr | `expected type='ExecutionDecision', got '<actual>'` |
| Exit codes | `0` success, `1` type mismatch, `2` missing argument |

**Behaviour:**

1. Reads the positional `<json-file>` argument; prints usage and exits `2` when omitted.
2. Parses the file as UTF-8 JSON.
3. Checks `data["type"] == "ExecutionDecision"`.
4. On success, prints a JSON result object to **stdout** and exits `0`.
5. On failure, prints an error message to **stderr** and exits `1`.

**Type discrimination:** The validator performs a strict equality check on the top-level `"type"` key.  
The field acts as a [tagged union](https://en.wikipedia.org/wiki/Tagged_union) discriminator — a pattern consistent with sourceos-spec artefact envelopes.

**URN pattern:** Not yet validated at this tier; deferred to schema binding (see §5).

---

### 2.2 SkillManifestValidator

**File:** `validators/skill_manifest.py`

| Attribute | Value |
|---|---|
| Expected `type` discriminator | `SkillManifest` |
| CLI entry point | `python -m validators.skill_manifest <json-file>` |
| Success stdout | `{"ok": true, "validated": "SkillManifest", "path": "<file>"}` |
| Failure stderr | `expected type='SkillManifest', got '<actual>'` |
| Exit codes | `0` success, `1` type mismatch, `2` missing argument |

**Behaviour:** Identical control flow to `ExecutionDecisionValidator`; discriminator constant is `SkillManifest`.

**Skill contract:** A `SkillManifest` artefact describes a discrete, reusable capability unit that can be composed inside an agentplane session.  Mandatory fields (enforced post schema-bind, §5): `urn`, `name`, `version`, `entrypoint`.

---

### 2.3 SessionReceiptValidator

**File:** `validators/session_receipt.py`

| Attribute | Value |
|---|---|
| Expected `type` discriminator | `SessionReceipt` |
| CLI entry point | `python -m validators.session_receipt <json-file>` |
| Success stdout | `{"ok": true, "validated": "SessionReceipt", "path": "<file>"}` |
| Failure stderr | `expected type='SessionReceipt', got '<actual>'` |
| Exit codes | `0` success, `1` type mismatch, `2` missing argument |

**Behaviour:** Identical control flow; discriminator constant is `SessionReceipt`.

**Receipt contract:** A `SessionReceipt` is an evidence/audit artefact emitted at the end of an agentplane session.  Mandatory fields (enforced post schema-bind, §5): `session_id`, `ts_start`, `ts_end`, `status`.

---

### 2.4 Package Init (`validators/__init__.py`)

```python
"""Validator entrypoints for imagelab capability contract checks."""
```

Single-line docstring that:
- Makes `validators/` a proper Python package.
- Provides a human-readable label when `import validators` is executed.
- Serves as the canonical discovery point for tooling that enumerates validator modules.

---

## 3. Capability Descriptor (CAPD) Patch

**File:** `capd/imagelab.capd.patch.yaml`

This fragment extends `capd/imagelab.capd.v0.yaml` with the additional contract directories and validator entry points introduced in Phase 2.

```yaml
# imagelab.capd.v0.yaml patch fragment
contracts:
  rpc_dir: "rpc"
  schema_dir: "schemas"
  session_dir: "sessions"   # ← new: session receipt artefacts
  skill_dir: "skills"       # ← new: skill manifest artefacts
  memory_dir: "memory"      # ← new: memory/context artefacts
validators:
  executionDecision: "python -m validators.execution_decision"
  skillManifest: "python -m validators.skill_manifest"
  sessionReceipt: "python -m validators.session_receipt"
```

**Integration with `imagelab.capd.v0.yaml`:**

Once `sourceos-spec#1` merges and a CAPD merge tool is available, this patch will be deep-merged into the base descriptor.  Until then it is consumed directly by admission webhook configuration (§4) and CI tooling.

**Contract directory mapping:**

| Key | Path | Artefact type |
|---|---|---|
| `rpc_dir` | `rpc/` | triRPC service definitions |
| `schema_dir` | `schemas/` | JSON Schema files |
| `session_dir` | `sessions/` | `SessionReceipt` JSON artefacts |
| `skill_dir` | `skills/` | `SkillManifest` JSON artefacts |
| `memory_dir` | `memory/` | Memory/context artefacts |

**Validator entry-point mapping:**

| Key | CLI command | Module |
|---|---|---|
| `executionDecision` | `python -m validators.execution_decision` | `validators/execution_decision.py` |
| `skillManifest` | `python -m validators.skill_manifest` | `validators/skill_manifest.py` |
| `sessionReceipt` | `python -m validators.session_receipt` | `validators/session_receipt.py` |

---

## 4. Admission Webhook Integration

### 4.1 Overview

Kubernetes admission webhooks intercept API-server requests before objects are persisted.  The imagelab validators are exposed as a webhook side-car so that agentplane artefacts are validated at admission time — before they reach the controller reconcile loop.

### 4.2 Kubernetes Configuration

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: imagelab-validator
webhooks:
  - name: executiondecision.imagelab.socio
    admissionReviewVersions: ["v1"]
    clientConfig:
      service:
        name: imagelab-validator
        namespace: imagelab-system
        path: /validate/execution-decision
    rules:
      - apiGroups:   ["agentplane.socio"]
        apiVersions: ["v1alpha1"]
        operations:  ["CREATE", "UPDATE"]
        resources:   ["executiondecisions"]
    sideEffects: None

  - name: skillmanifest.imagelab.socio
    admissionReviewVersions: ["v1"]
    clientConfig:
      service:
        name: imagelab-validator
        namespace: imagelab-system
        path: /validate/skill-manifest
    rules:
      - apiGroups:   ["agentplane.socio"]
        apiVersions: ["v1alpha1"]
        operations:  ["CREATE", "UPDATE"]
        resources:   ["skillmanifests"]
    sideEffects: None

  - name: sessionreceipt.imagelab.socio
    admissionReviewVersions: ["v1"]
    clientConfig:
      service:
        name: imagelab-validator
        namespace: imagelab-system
        path: /validate/session-receipt
    rules:
      - apiGroups:   ["agentplane.socio"]
        apiVersions: ["v1alpha1"]
        operations:  ["CREATE"]
        resources:   ["sessionreceipts"]
    sideEffects: None
```

### 4.3 Admission Handler Implementation (pseudocode)

The handler pattern below applies to all three validators:

```python
import json
import subprocess
import tempfile
from pathlib import Path

def handle_admission(review: dict, validator_module: str) -> dict:
    """
    review         – decoded AdmissionReview JSON from Kubernetes API server
    validator_module – e.g. 'validators.execution_decision'
    """
    uid = review["request"]["uid"]
    obj = review["request"]["object"]

    # Write payload to a temp file so the CLI validator can read it
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(obj, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["python", "-m", validator_module, str(tmp_path)],
            capture_output=True,
            text=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    allowed = result.returncode == 0
    message = result.stderr.strip() if not allowed else ""

    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": allowed,
            **({"status": {"message": message}} if not allowed else {}),
        },
    }
```

**Route mapping:**

| HTTP path | Validator module |
|---|---|
| `/validate/execution-decision` | `validators.execution_decision` |
| `/validate/skill-manifest` | `validators.skill_manifest` |
| `/validate/session-receipt` | `validators.session_receipt` |

### 4.4 Security Considerations

- The webhook service must be reachable from the Kubernetes API server over TLS.
- mTLS between the API server and the webhook is recommended.
- Temp files containing payload JSON are deleted immediately after the subprocess call.
- The validator subprocesses run with minimal OS privileges (no network, read-only FS except temp).

---

## 5. Full Schema Binding Roadmap

### 5.1 Current State

At Phase 2 the validators perform **type discrimination only** — they check the top-level `"type"` field and nothing else.  This is intentional: the authoritative JSON Schema definitions live in `sourceos-spec` (pending merge of `sourceos-spec#1`).

### 5.2 Target State (post-`sourceos-spec#1` merge)

Once `sourceos-spec#1` merges, each validator will be extended to perform **full schema validation** against the canonical spec:

```
sourceos-spec (schemas)
        │  imported as git submodule or published package
        ▼
validators/
  execution_decision.py  ──bind──▶  ExecutionDecision.schema.json
  skill_manifest.py      ──bind──▶  SkillManifest.schema.json
  session_receipt.py     ──bind──▶  SessionReceipt.schema.json
```

### 5.3 Migration Steps

1. **Add `sourceos-spec` as a dependency** – either as a git submodule at `vendor/sourceos-spec/` or as a published Python package.
2. **Extend each validator** with a `jsonschema.validate()` call after the type-discriminator check.
3. **Update CAPD patch** – add `schema_ref` keys pointing to the canonical schema IDs.
4. **Update CI** – `make validate` will implicitly exercise schema validation via the existing `tools/validate.sh` gate.
5. **URN pattern enforcement** – add a regex check on `urn` fields using the `socio:` prefix pattern mandated by sourceos-spec.

### 5.4 URN Pattern (anticipated)

Based on sourceos-spec conventions, URNs are expected to follow:

```
socio:<capability>:<resource-type>:<version>:<identifier>
```

Example: `socio:imagelab:skill:v1:image-resize`

The validators will enforce this pattern via `re.fullmatch` once the spec is published.

### 5.5 Schema IDs (anticipated)

| Artefact | Schema `$id` |
|---|---|
| `ExecutionDecision` | `socio.imagelab.executiondecision.v1` |
| `SkillManifest` | `socio.imagelab.skillmanifest.v1` |
| `SessionReceipt` | `socio.imagelab.sessionreceipt.v1` |

---

## 6. Testing Strategy

### 6.1 Unit Tests

Each validator module should have a corresponding unit test file under `tests/validators/`.

**Directory layout (target):**
```
tests/
  validators/
    __init__.py
    test_execution_decision.py
    test_skill_manifest.py
    test_session_receipt.py
  conftest.py
```

### 6.2 Test Cases per Validator

The following table applies to all three validators (replace `<Type>` with the appropriate discriminator):

| # | Test name | Input `type` field | Expected exit code | Expected output |
|---|---|---|---|---|
| 1 | `test_valid_type` | `<Type>` | `0` | `{"ok": true, ...}` on stdout |
| 2 | `test_wrong_type` | `OtherType` | `1` | error message on stderr |
| 3 | `test_missing_type_key` | *(field absent)* | `1` | error message on stderr |
| 4 | `test_no_argument` | *(no file arg)* | `2` | usage message on stderr |
| 5 | `test_malformed_json` | *(invalid JSON)* | non-zero | exception / error on stderr |

### 6.3 Example Unit Test (`test_execution_decision.py`)

```python
import json
import subprocess
import sys
import tempfile
from pathlib import Path


MODULE = "validators.execution_decision"
VALID_TYPE = "ExecutionDecision"


def _run(payload: dict | None, *, no_arg: bool = False) -> subprocess.CompletedProcess:
    if no_arg:
        return subprocess.run(
            [sys.executable, "-m", MODULE],
            capture_output=True, text=True,
        )
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", delete=False, encoding="utf-8"
    ) as f:
        json.dump(payload, f)
        path = f.name
    try:
        return subprocess.run(
            [sys.executable, "-m", MODULE, path],
            capture_output=True, text=True,
        )
    finally:
        Path(path).unlink(missing_ok=True)


def test_valid_type():
    r = _run({"type": VALID_TYPE})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["validated"] == VALID_TYPE


def test_wrong_type():
    r = _run({"type": "SomethingElse"})
    assert r.returncode == 1
    assert VALID_TYPE in r.stderr


def test_missing_type_key():
    r = _run({"other": "field"})
    assert r.returncode == 1


def test_no_argument():
    r = _run(None, no_arg=True)
    assert r.returncode == 2
    assert "usage" in r.stderr.lower()
```

### 6.4 Integration Tests

Integration tests exercise the full admission webhook flow using a mock HTTP server:

1. Start the webhook HTTP server on a local port.
2. POST a synthetic `AdmissionReview` with a valid payload → assert `response.allowed == true`.
3. POST a synthetic `AdmissionReview` with an invalid `type` → assert `response.allowed == false` and `response.status.message` is non-empty.
4. POST a malformed JSON body → assert HTTP `400` or `response.allowed == false`.

### 6.5 Running Tests

```sh
# Once test infrastructure is added:
python -m pytest tests/validators/ -v

# Smoke-run a single validator manually:
echo '{"type":"ExecutionDecision"}' > /tmp/ed.json
python -m validators.execution_decision /tmp/ed.json
# Expected: {"ok": true, "validated": "ExecutionDecision", "path": "/tmp/ed.json"}
```

---

## 7. Current Limitations & Follow-Up Tasks

### 7.1 What Is Done (Phase 2)

- [x] Three validator stub modules with type-discrimination logic.
- [x] `validators/__init__.py` package marker.
- [x] CAPD patch fragment (`capd/imagelab.capd.patch.yaml`) declaring contract dirs and validator entry points.
- [x] CI gate (`make validate` / `tools/validate.sh`) passes on every push.

### 7.2 What Is Deferred

| Item | Blocked on | Priority |
|---|---|---|
| Full JSON Schema validation | `sourceos-spec#1` merge | High |
| URN pattern enforcement | sourceos-spec URN spec published | High |
| Unit test suite (`tests/validators/`) | CI test runner configuration | Medium |
| Admission webhook HTTP server | agentplane k8s operator scaffold | Medium |
| CAPD deep-merge tooling | sourceos-spec CAPD toolchain | Low |
| `session_dir`, `skill_dir`, `memory_dir` creation | agentplane directory scaffold | Low |
| mTLS configuration for webhook | Infrastructure/ops | Low |

### 7.3 Known Limitations

- **No field-level validation** – only the `"type"` discriminator is checked; any other fields in the JSON are accepted without error.
- **No URN validation** – URN format is not yet enforced; malformed URNs will not be rejected.
- **Temp-file race** (admission handler pseudocode) – the temp file could theoretically be read by other processes in a shared environment; production deployments should use a private `/tmp` or memory-backed filesystem.
- **Python runtime required** – the validators require Python 3.8+ in the execution environment; this is not yet declared as a CAPD dependency.

---

## 8. Complete File Inventory

The following 5 files are introduced or modified in this PR:

| # | File | Lines | Description |
|---|---|---|---|
| 1 | `validators/execution_decision.py` | 22 | Validates `ExecutionDecision` artefacts via type-discriminator check |
| 2 | `validators/skill_manifest.py` | 22 | Validates `SkillManifest` artefacts via type-discriminator check |
| 3 | `validators/session_receipt.py` | 22 | Validates `SessionReceipt` artefacts via type-discriminator check |
| 4 | `validators/__init__.py` | 1 | Python package marker with module docstring |
| 5 | `capd/imagelab.capd.patch.yaml` | 11 | CAPD patch: additional contract dirs + validator entry points |

### 8.1 File Sizes & SHA-256 (at time of documentation)

```
validators/execution_decision.py  – 22 lines
validators/skill_manifest.py      – 22 lines
validators/session_receipt.py     – 22 lines
validators/__init__.py            –  1 line
capd/imagelab.capd.patch.yaml     – 11 lines
```

### 8.2 Module Dependency Graph

```
validators/
  __init__.py          (no dependencies)
  execution_decision.py  ← json, sys, pathlib (stdlib only)
  skill_manifest.py      ← json, sys, pathlib (stdlib only)
  session_receipt.py     ← json, sys, pathlib (stdlib only)
```

All validator modules use **Python standard library only** — no third-party dependencies are required at Phase 2.

---

*Document authored for imagelab Phase 2 / `feat/agent-plane-capd-patch-v0`.*  
*Next revision: Phase 3 — Full Schema Binding (pending `sourceos-spec#1`).*
