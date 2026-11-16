"""Synthetic exploration consumers; the programs are trivial and carry no research question."""
from hypersearch.study_json import digest, encode
from study_fixture import git, make
from test_study_contract import artifact

OBSERVES = (b'import json, sys\narguments = json.loads(sys.stdin.read())\n'
            b'print(json.dumps({"observations": {"echo": arguments}}))\n')


def make_exploration(root, source=OBSERVES, *, arguments=None, timeout=30, memory=512, path="explore.py",
                     attempts=5, study_id="fixture-exploration"):
    """A committed synthetic consumer plus the frozen exploration bundle that names it."""
    core, consumer, study = make(root)
    (consumer / path).write_bytes(source)
    kept = {name: study["artifacts"][name] for name in ("preregistration", "claim_record")}
    kept["program"] = artifact(path, source)
    question = {"adapter": "exploration-program", "program_sha256": digest(source), "arguments": arguments or {},
                "claim_type": "exploration-log", "assumptions_sha256": kept["preregistration"]["sha256"]}
    limits = {"db_max_attempts": attempts, "timeout_seconds": timeout, "commit_margin_seconds": 10,
              "memory_megabytes": memory}
    manifest = encode({"schema": "hypersearch.exploration-manifest/v1", "study_id": study_id, "question": question,
                       "limits": limits, "artifact_sha256": {k: v["sha256"] for k, v in kept.items()}})
    (consumer / "exploration.json").write_bytes(manifest)
    git(consumer, "add", "."); git(consumer, "commit", "-m", "Frozen exploration fixture")
    bundle = {"schema": "hypersearch.exploration-bundle/v1", "study_id": study_id,
              "consumer": dict(study["consumer"], commit=git(consumer, "rev-parse", "HEAD")),
              "instrument": dict(study["instrument"], verifier="hypersearch.exploration/v1"), "question": question,
              "artifacts": dict(kept, study_manifest=artifact("exploration.json", manifest)), "limits": limits}
    return core, consumer, bundle
