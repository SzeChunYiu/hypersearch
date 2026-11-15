"""Synthetic pinned-program consumers; the programs are trivial and carry no research question."""
from hypersearch.study_json import digest, encode
from study_fixture import git, make
from test_study_contract import artifact

HOLDS = b'import json, sys\narguments = json.loads(sys.stdin.read())\nprint(json.dumps({"holds": True, "summary": {"echo": arguments}}))\n'


def make_program(root, source=HOLDS, *, arguments=None, timeout=30, memory=512, path="program.py"):
    """A committed synthetic consumer plus the frozen program bundle that names it."""
    core, consumer, study = make(root)
    (consumer / path).write_bytes(source)
    kept = {name: study["artifacts"][name] for name in ("preregistration", "claim_record")}
    kept["program"] = artifact(path, source)
    question = {"adapter": "pinned-program", "program_sha256": digest(source), "arguments": arguments or {},
                "claim_type": "program-output", "assumptions_sha256": kept["preregistration"]["sha256"]}
    limits = {"db_max_attempts": 5, "timeout_seconds": timeout, "commit_margin_seconds": 10, "memory_megabytes": memory}
    manifest = encode({"schema": "hypersearch.program-manifest/v1", "study_id": "fixture-program", "question": question,
                       "limits": limits, "artifact_sha256": {k: v["sha256"] for k, v in kept.items()}})
    (consumer / "program.json").write_bytes(manifest)
    git(consumer, "add", "."); git(consumer, "commit", "-m", "Frozen program fixture")
    bundle = {"schema": "hypersearch.program-bundle/v1", "study_id": "fixture-program",
              "consumer": dict(study["consumer"], commit=git(consumer, "rev-parse", "HEAD")),
              "instrument": dict(study["instrument"], verifier="hypersearch.pinned-program/v1"), "question": question,
              "artifacts": dict(kept, study_manifest=artifact("program.json", manifest)), "limits": limits}
    return core, consumer, bundle
