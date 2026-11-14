"""New public synthetic consumers; no external data or credentials."""
import base64
from pathlib import Path
import shutil
import subprocess

from hypersearch.study_json import digest, encode
from test_study_contract import bundle


def git(root, *args):
    return subprocess.run(["/usr/bin/git", "-C", str(root), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def initialize(root, origin):
    git(root, "init"); git(root, "config", "user.name", "Synthetic fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "remote", "add", "origin", origin)
    git(root, "add", "."); git(root, "commit", "-m", "Frozen fixture")
    return git(root, "rev-parse", "HEAD")


def make(root, multi=False, false=False):
    source = Path(__file__).resolve().parents[1]
    core, consumer = root / "core", root / "consumer"
    core.mkdir(); consumer.mkdir()
    shutil.copytree(source / "src", core / "src", ignore=shutil.ignore_patterns("__pycache__"))
    (core / "governance").mkdir()
    shutil.copyfile(source / "governance/release.json", core / "governance/release.json")
    (core / ".gitignore").write_text("__pycache__/\n")
    value = bundle(multi, false)
    value["instrument"]["commit"] = initialize(core, value["instrument"]["repository"])
    paths = [p for p in (core / "src/hypersearch").rglob("*.py")]
    paths.append(core / "governance/release.json")
    value["instrument"]["source_sha256"] = {p.relative_to(core).as_posix(): digest(p.read_bytes()) for p in paths}
    for item in value["artifacts"].values():
        (consumer / item["path"]).write_bytes(base64.b64decode(item["base64"]))
    (consumer / "entry.py").write_bytes(b"# fixture\n")
    value["consumer"]["commit"] = initialize(consumer, value["consumer"]["repository"])
    return core, consumer, value
