"""Real receipts for the export check: synthetic consumers run through the frozen routes."""
import copy
from pathlib import Path
from unittest.mock import patch

from hypersearch import study
from hypersearch.program import program_route
from hypersearch.study_json import digest, encode, parse
from program_fixture import make_program

# Two summary fields, so that one of them can be left out of a registered prediction.
COUNTS = (b'import json, sys\narguments = json.loads(sys.stdin.read())\n'
          b'print(json.dumps({"holds": True, "summary": {"count": arguments["n"], "note": "not registered"}}))\n')


def produce(make_route, core, consumer, bundle, root):
    """Run one original and one replay; return both receipts as their committed bytes."""
    route = make_route()
    with patch("hypersearch.study.CORE_ROOT", core):
        first = study.execute(route.wrapper(bundle), consumer_root=consumer, database=root / "tasks.sqlite",
                              export=root / "originals", route=route)
        raw = Path(first["receipt_path"]).read_bytes()
        again = route.wrapper(bundle, parent=first["receipt_sha256"], replay_id="replay-1")
        second = study.execute(again, consumer_root=consumer, database=root / "tasks.sqlite", export=root / "replays",
                               parent_receipt=route.trusted_receipt(raw, first["receipt_sha256"]), route=route)
    return raw, Path(second["receipt_path"]).read_bytes()


def family(root):
    """Two program studies, each with an original and a matching replay: {study_id: (original, replay)}."""
    made = {}
    for name, n in (("fixture-first", 1), ("fixture-second", 2)):
        (root / name).mkdir()
        core, consumer, bundle = make_program(root / name, COUNTS, arguments={"n": n}, study_id=name)
        made[name] = produce(program_route, core, consumer, bundle, root / name)
    return made


def place(directory, *receipts):
    """Write committed receipt bytes under their digests, as an export does."""
    directory.mkdir(exist_ok=True)
    for raw in receipts:
        (directory / (digest(raw) + ".json")).write_bytes(raw)
    return directory


def forged(raw, route=None, **changes):
    """A receipt the validators accept, made by editing a real one: receipts carry no signature."""
    route = route or program_route()
    value = dict(copy.deepcopy(parse(raw, len(raw))), **changes)
    value["task_id"], value["execution_sha256"] = route.execution_identity(value["execution"])
    value["outcome_sha256"] = digest(encode(value["outcome"]))
    return encode(route.validate_receipt(value))


def released(pair, version, route=None):
    """An original and its replay as a release that differs only in its version wrote them.

    Validators unchanged but for the version string are what check-export reads for EARLIER releases. The
    rewrite changes the version, the identities derived from it and the replay's parent digest, nothing
    else; with the package's version patched to that release, its own validators accept the result.
    """
    route = route or program_route()
    with patch("hypersearch.study_contract.__version__", version):
        original = parse(pair[0], len(pair[0]))
        original["execution"]["bundle"]["instrument"]["release_version"] = version
        original = forged(encode(original), route)
        replay = parse(pair[1], len(pair[1]))
        replay["execution"] = dict(replay["execution"], bundle=parse(original)["execution"]["bundle"],
                                   parent_receipt_sha256=digest(original))
        return original, forged(encode(replay), route)


def expected(require_replay=True, change=None):
    """What a consumer registers before running the family; `change` replaces or adds study entries."""
    value = {"schema": "hypersearch.expected-outcomes/v1", "require_replay": require_replay, "studies": {
        name: {"status": "PROGRAM_HOLDS", "summary_sha256": digest(encode({"count": n})),
               "unregistered_summary_fields": ["note"]} for name, n in (("fixture-first", 1), ("fixture-second", 2))}}
    value["studies"].update(change or {})
    return value
