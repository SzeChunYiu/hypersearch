"""Cooperative checkout and output boundaries; no network or remote attestation."""
from pathlib import Path
import stat
import subprocess

from .study_json import artifact_bytes, digest, parse


def git(root, *args):
    return subprocess.run(["/usr/bin/git", "--no-replace-objects", "-C", str(root), *args],
                          capture_output=True, check=True).stdout


def plain_file(root, relative):
    path = root
    for part in Path(relative).parts[:-1]:
        path = path / part
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise ValueError("non-directory or symlink source parent")
    path = root / relative
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("source must be a regular file")
    return path


def checkout(root, commit, repository):
    root = Path(root).resolve(strict=True)
    if Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
        raise ValueError("source root must be checkout root")
    if git(root, "rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("source commit mismatch")
    if git(root, "remote", "get-url", "origin").decode().strip().removesuffix(".git") != repository.removesuffix(".git"):
        raise ValueError("source origin mismatch")
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("source checkout is dirty")
    tracked = set()
    for item in git(root, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not item:
            continue
        meta, filename = item.split(b"\t", 1)
        mode, kind, oid = meta.split()
        name = filename.decode("utf-8")
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise ValueError("unsupported source object mode")
        path = plain_file(root, name)
        if bool(path.stat().st_mode & 0o111) != (mode == b"100755"):
            raise ValueError("source executable mode mismatch")
        if path.read_bytes() != git(root, "cat-file", "blob", oid.decode("ascii")):
            raise ValueError("source working bytes mismatch")
        tracked.add(name)
    return root, tracked


def verify_sources(bundle, core_root, consumer_root):
    instrument, consumer = bundle["instrument"], bundle["consumer"]
    core, tracked = checkout(core_root, instrument["commit"], instrument["repository"])
    consumer_root, consumer_tracked = checkout(consumer_root, consumer["commit"], consumer["repository"])
    if core == consumer_root or core in consumer_root.parents or consumer_root in core.parents:
        raise ValueError("core and consumer source roots must not overlap")
    expected = {p for p in tracked if p.startswith("src/hypersearch/") and p.endswith(".py")}
    expected.add("governance/release.json")
    if set(instrument["source_sha256"]) != expected:
        raise ValueError("instrument source inventory mismatch")
    for name in expected:
        if digest(plain_file(core, name).read_bytes()) != instrument["source_sha256"][name]:
            raise ValueError("instrument source digest mismatch")
    release = parse(plain_file(core, "governance/release.json").read_bytes())
    required = {"hypersearch.study-manifest/v1", "hypersearch.study-bundle/v1",
                "hypersearch.study-execution/v1", "hypersearch.study-receipt/v1"}
    if (type(release) is not dict or release.get("schema") != "hypersearch.release/v1"
            or release.get("status") not in {"development", "release-candidate", "released"}
            or release.get("api") != instrument["api"]
            or release.get("version") != instrument["release_version"]
            or type(release.get("schemas")) is not list
            or any(type(s) is not str for s in release["schemas"])
            or not required.issubset(release["schemas"])
            or type(release.get("verifiers")) is not list
            or any(type(v) is not str for v in release["verifiers"])
            or instrument["verifier"] not in release["verifiers"]):
        raise ValueError("release does not support the pinned study contract")
    for path in (core / "src").rglob("*"):
        if path.is_symlink():
            raise ValueError("symlinked executable source")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".pyc", ".so", ".pyd"}:
            if path.relative_to(core).as_posix() not in tracked:
                raise ValueError("untracked executable source")
    for item in bundle["artifacts"].values():
        if item["path"] not in consumer_tracked or plain_file(consumer_root, item["path"]).read_bytes() != artifact_bytes(item):
            raise ValueError("consumer artifact does not match pinned source")
    name = consumer["entrypoint"]
    if name not in consumer_tracked or digest(plain_file(consumer_root, name).read_bytes()) != consumer["entrypoint_sha256"]:
        raise ValueError("consumer entrypoint identity mismatch")
    return core, consumer_root


def output_paths(database, export, roots, inputs=()):
    database, export = Path(database), Path(export)
    # SQLite may create, rewrite or remove these alongside the main file.
    sidecars = tuple(Path(str(database) + suffix) for suffix in ("-journal", "-wal", "-shm"))
    # Reject symlink aliases even when their targets are outside source roots.
    for candidate in (database, export, *sidecars):
        absolute = candidate.absolute()
        if any(p.is_symlink() for p in (absolute, *absolute.parents)):
            raise ValueError("symlink output path")
    database, export = database.resolve(), export.resolve()
    sidecars = tuple(p.resolve() for p in sidecars)
    for path in (database, export, *sidecars):
        for root in (*roots, *(Path(p).resolve() for p in inputs)):
            if path == root or root in path.parents or path in root.parents:
                raise ValueError("output overlaps a pinned source or input")
    for path in (database, *sidecars):
        if path == export or path in export.parents or export in path.parents:
            raise ValueError("database/sidecar and export paths overlap")
    for path in (database, *sidecars):
        if path.is_file() and path.stat().st_nlink != 1:
            raise ValueError("hardlinked database or SQLite sidecar")
    for path in sidecars:
        if path.exists() and (not path.is_file() or not database.exists()):
            raise ValueError("unowned or non-file SQLite sidecar")
    if not database.parent.is_dir() or not export.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    if database.exists() and not database.is_file():
        raise ValueError("database path is not a file")
    if export.exists() and not export.is_dir():
        raise ValueError("export path is not a directory")
    return database, export
