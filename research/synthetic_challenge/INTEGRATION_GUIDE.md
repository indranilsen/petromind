# Session A handoff — frozen synthetic-physics-v1.1

**Integration readiness: passed offline, with mandatory per-case isolation.** No
model was called. This handoff adds transport, verification and documentation;
all frozen scenarios, reference verdicts and scoring weights remain unchanged.

## Owner recovery, verified from the saved copy

Download the existing owner file **PetroMind-Sprint-B-PRIVATE-Evaluator.tar.gz**
from ChatGPT Library (owner link supplied with the PR handoff). Keep the downloaded
archive private. Verified version: original version 0, 361,716 bytes, SHA-256:

```
10f06578af1255e92bad13d1f4c8735c24c1f3d4f2e1947ad5cde3d45b5e5294
```

This pass downloaded that saved version rather than relying on scratch copies.
Extraction recovered `private_sprint_b/` (corrected v1.1) and
`private_sprint_b_v1_frozen/` (original known-defective v1 and results). The v1.1
package contains its answer key, seven sensor vaults, generator, scorer, baseline,
verification scripts, owner instructions and prior transcripts. Regeneration and
numerical verification produced byte-identical public inputs, key, vaults and
verification report. No original scratch files are required for recovery.

Use a trusted owner machine and Python >=3.12 for the safe extraction command below
(the frozen generator/evaluator themselves require only Python >=3.10). Substitute
the archive's downloaded absolute path and this PR checkout's absolute path:

```bash
umask 077
PM_ARCHIVE="/absolute/path/PetroMind-Sprint-B-PRIVATE-Evaluator.tar.gz"
PM_RELEASE_ROOT="/absolute/path/petromind/research/synthetic_challenge"
PM_REPO_ROOT="/absolute/path/petromind"
PM_OWNER_ROOT="$HOME/.local/share/petromind-sprint-b-owner"
mkdir -p "$PM_OWNER_ROOT"
python3 - "$PM_ARCHIVE" "$PM_OWNER_ROOT" <<'PY'
import hashlib,sys,tarfile
from pathlib import Path
archive=Path(sys.argv[1]);root=Path(sys.argv[2])/'recovered-v1.1'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='10f06578af1255e92bad13d1f4c8735c24c1f3d4f2e1947ad5cde3d45b5e5294'
root.mkdir(mode=0o700) # fresh destination; refuse overwrite
with tarfile.open(archive,'r:gz') as t:
    for m in t.getmembers():
        p=Path(m.name)
        assert not p.is_absolute() and '..' not in p.parts and not m.issym() and not m.islnk()
    t.extractall(root,filter='data')
PY
PM_PRIVATE_ROOT="$PM_OWNER_ROOT/recovered-v1.1/private_sprint_b"
python3 "$PM_RELEASE_ROOT/integration/verify_readiness.py" \
  --release-root "$PM_RELEASE_ROOT" --private-root "$PM_PRIVATE_ROOT" \
  --repo-root "$PM_REPO_ROOT"
python3 "$PM_PRIVATE_ROOT/generate.py" --out "$PM_OWNER_ROOT/regenerated-v1.1"
python3 "$PM_PRIVATE_ROOT/verify.py" "$PM_OWNER_ROOT/regenerated-v1.1" \
  > "$PM_OWNER_ROOT/regenerated-verification.private.json"
python3 "$PM_PRIVATE_ROOT/test_physics.py"
```

Always use normal Python, not `python -O`: frozen verification/scoring code uses
assertions. `verify_readiness.py` validates 36 frozen public entries and 34 private
core entries and checks the commitments themselves. The original private manifest
also committed stale prior-v1 log/metadata references. They remain documented in
FREEZE_ADDENDUM.json; the 34-file core is an exact subset of that original
pre-evaluation commitment. Do not describe the entire original private manifest
as a clean self-contained manifest of only v1.1 files.

## Trust boundary for Session A

Session A may write and run the orchestrator on the trusted owner side. **Muse
receives only one `packet()` and serialized tool results**, in a fresh context per
case. No filesystem, shell, Python object, callback, repository search, arbitrary
URL/document fetch or other tool is granted to Muse. The owner process must use a
separate UID/container/filesystem boundary from any agent that has local file tools.
The bridge itself is not an OS sandbox or authenticated network service.

Never give Muse the archive, generator, scorer, baseline, reference answers,
private score files, raw host logs, this handoff, the whole repository, archive/v1,
or the complete public case directory. Some channels hidden in one variant are
initially visible in another because the variants share the incident. Whole-corpus
retrieval would bypass the sensor budget. The within-case packets contain only
initial readings and no hidden reference fields. A requested sensor is deliberately
released only through the frozen budgeted tool; unrequested sensors stay private.

The trusted host reads only a case-specific sensor vault. It does **not** read the
answer key. The scorer runs separately after the model session has closed, and
its reference-bearing stdout stays private. Do not feed scores or validation
reference labels back into Muse or tune interventions between benchmark cases.
Only protocol-level structural errors from the frozen adapter may be returned.

## Runnable JSON-lines bridge

The owner starts one bridge process per case, with a fresh audit path:

```bash
mkdir -p "$PM_OWNER_ROOT/runs/run-001"
python3 "$PM_RELEASE_ROOT/integration/trusted_host.py" \
  --release-root "$PM_RELEASE_ROOT" --private-root "$PM_PRIVATE_ROOT" \
  --case c-13df --audit-out "$PM_OWNER_ROOT/runs/run-001/c-13df.audit.private.json"
```

For a real orchestration harness use `subprocess.Popen(..., stdin=PIPE,
stdout=PIPE, text=True)` with the same arguments. The first stdout line is
`{"result": <one public case packet>}`. Put only its `result` in Muse's initial
context. Translate each whitelisted function call into one stdin JSON line:

```json
{"name":"query_sensor","arguments":{"sensor":"SYN-Q-PROD"}}
{"name":"lookup_graph","arguments":{"node":"P-TPT","hops":2}}
```

Read exactly one response line and give only its `result` to Muse. Allowed names:
query_sensor, read_document, lookup_graph, search_history, submit_audit; shapes are
in README.md. Serialize calls sequentially. Never use eval, pass-through shell
commands or model-supplied paths. Submit using the unchanged verdict/findings/
numeric_observations shape. Findings must copy each supplied atomic statement
exactly. `offline_smoke.py` provides a complete executable orchestrator example.
It uses a generic abstention fixture, not a scientifically correct answer.

The frozen adapter counts initial sensors, enforces the five-sensor budget,
caches repeat requests and allows at most 24 calls and two submission repairs.
The bridge additionally bounds input lines and total transport requests, suppresses
exception details, writes mode-0600 audit files and refuses existing output paths.
Its stdout never contains audit records or evaluator results. A validated submission
closes the bridge. Keep the final audit hash in a trusted run manifest before scoring.

After all seven case processes have finished, assemble their host audit files:

```bash
python3 - "$PM_OWNER_ROOT/runs/run-001" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);files=sorted(root.glob('*.audit.private.json'))
audits={}
for path in files:
    events=json.loads(path.read_text())
    case_id=events[0]['result']['case_id']
    assert case_id not in audits
    audits[case_id]=events
assert len(audits)==7
(root/'suite-audits.private.json').write_text(json.dumps(audits)+'\n')
(root/'final-digests.private.json').write_text(json.dumps({k:v[-1]['digest'] for k,v in audits.items()})+'\n')
PY
python3 "$PM_PRIVATE_ROOT/evaluate.py" --public "$PM_RELEASE_ROOT/public" \
  --key "$PM_PRIVATE_ROOT/build/private/answer_key.json" \
  --audits "$PM_OWNER_ROOT/runs/run-001/suite-audits.private.json" \
  > "$PM_OWNER_ROOT/runs/run-001/score.private.json"
```

Detailed scores contain reference verdicts: owner/reviewer access only. A full
100-point total requires the frozen human semantic review fields. Automated score
production alone is not a scientific pass. No Muse calls are authorized by this
handoff; any later experiment must retain the already specified reservation cap
and separate provider-usage accounting.

## Offline verification performed

Run the exact smoke on the recovered copy, with a fresh output destination:

```bash
python3 "$PM_RELEASE_ROOT/integration/offline_smoke.py" \
  --release-root "$PM_RELEASE_ROOT" --private-root "$PM_PRIVATE_ROOT" \
  --out "$PM_OWNER_ROOT/smoke-001"
python3 -m unittest discover -s "$PM_RELEASE_ROOT/integration" -p 'test_*.py'
python3 -m pytest -q "$PM_RELEASE_ROOT/tests"
```

The smoke loaded one public case (3 initial channels), obtained one initially
hidden production-flow channel through the bridge (4 charged sensors), retrieved
4 connected graph edges, accepted a structured assessment and produced a private
score using the unchanged evaluator in a separate process. Its all-abstention
fixture is intentionally incomplete: the unchanged full-suite scorer counted the
other six cases as missing, yielding 2.497835/29 mechanical points and no semantic
total. This is a transport test, not a model result or single-case accuracy score.

The recovered fixed full-suite baseline separately reproduced 29/29 mechanical
points. Tests passed: 16 frozen interface tests, 6 private physics/reproducibility
tests and 4 new transport-boundary tests. Zero model calls and $0 estimated API
spend. The public verification report is INTEGRATION_VERIFICATION.json. Private
transcripts, detailed scores and recovery evidence are saved separately for owner
review, not committed to this PR.

## Production isolation and remaining limits

The synthetic adapter imports no production auditor. atomic_auditor.py,
reliable_auditor.py, scope_auditor.py and claim_auditor.py remain byte-identical to
the frozen base commit. V5's `verified_causal_rule_unavailable` rejection remains
in place. Use the synthetic bridge only for this declared model; never select it
for a real-data investigation or alter the production validator to accept synthetic
findings. Structured acceptance checks syntax/citation membership, not physical
entailment: an unsupported diagnostic assertion can be accepted structurally and
must still lose scientific points in the private scorer/review.

One modeled incident and seven dependent variants do not support population
accuracy. Generic source semantics and the published example are externally
checked; topology, coefficients, thermal forcing, calibration and history are
synthetic assumptions. There is no industrial certification, multiphase or hydrate
chemistry simulation, or completed human semantic review. Hash chains require a
trusted recorder and externally retained digest; they do not authenticate a wholly
forged transcript. The bridge is sequential/local-only, has no remote authentication
or crash-resume facility, and still requires the stated OS/context isolation.
Keep protocol versions separate; retain v1's documented defect and v1.1's original
freeze/addendum. All cases, reference verdicts and scoring weights are unchanged.
