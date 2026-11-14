"""Check managed material coverage and local release policy.

This validates repository files, not GitHub rulesets, reviewer independence,
artifact authenticity, deployability, or scientific correctness. CI must be a
required remote check before these rules become merge enforcement.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tomllib

MATERIALS_SCHEMA = "hypersearch.materials/v1"
RELEASE_SCHEMA = "hypersearch.release/v1"
ROLES = {"code", "test", "documentation", "configuration", "governance", "license", "automation"}
LIFECYCLES = {"active", "experimental", "deprecated", "archived"}
STATUSES = {"development", "release-candidate", "released", "deprecated"}
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?\Z")
INTERFACE = re.compile(r"hypersearch\.[a-z0-9][a-z0-9.-]*/v[1-9][0-9]*\Z")


def _path(value):
    return (isinstance(value, str) and bool(value)
            and '\\' not in value and '\x00' not in value
            and not PurePosixPath(value).is_absolute()
            and '..' not in PurePosixPath(value).parts
            and str(PurePosixPath(value)) == value)


def _load(path):
    def unique_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate JSON key: {key}")
            obj[key] = value
        return obj
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)


def check(root, tracked_paths=None):
    """Return errors; optional explicit tracked_paths supports isolated fixtures."""
    root = Path(root).resolve()
    errors = []
    if tracked_paths is None:
        try:
            result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                                    check=True, capture_output=True)
            tracked_paths = result.stdout.decode("utf-8").rstrip('\x00').split('\x00')
        except (subprocess.CalledProcessError, OSError, UnicodeError) as error:
            return [f"cannot enumerate tracked files: {error}"]
    tracked = set(tracked_paths)
    if not tracked or any(not _path(p) for p in tracked):
        return ["tracked file list contains invalid paths or is empty"]
    for path in sorted(tracked):
        target = root / path
        # Checking every ancestor avoids symlink directories escaping the root.
        ancestors = [root.joinpath(*PurePosixPath(path).parts[:i])
                     for i in range(1, len(PurePosixPath(path).parts) + 1)]
        if any(parent.is_symlink() for parent in ancestors):
            errors.append(f"symlink path is not managed material: {path}")
        elif not target.is_file():
            errors.append(f"tracked material missing or not a file: {path}")
    try:
        manifest = _load(root / "governance/materials.json")
        if (type(manifest) is not dict or set(manifest) != {"schema", "materials"}
                or manifest["schema"] != MATERIALS_SCHEMA or type(manifest["materials"]) is not list):
            raise ValueError("invalid materials manifest schema")
        registered = set()
        for row in manifest["materials"]:
            if type(row) is not dict or set(row) != {"path", "owner", "role", "lifecycle"}:
                raise ValueError("invalid material entry fields")
            path = row["path"]
            if not _path(path):
                raise ValueError("invalid material path")
            if path in registered:
                raise ValueError(f"duplicate material path: {path}")
            if not isinstance(row["owner"], str) or not row["owner"].strip():
                raise ValueError(f"missing accountable owner for {path}")
            if not isinstance(row["role"], str) or row["role"] not in ROLES:
                raise ValueError(f"invalid material role: {path}")
            if not isinstance(row["lifecycle"], str) or row["lifecycle"] not in LIFECYCLES:
                raise ValueError(f"invalid lifecycle: {path}")
            registered.add(path)
        errors += [f"unregistered tracked material: {p}" for p in sorted(tracked - registered)]
        errors += [f"registered material is not tracked: {p}" for p in sorted(registered - tracked)]
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        errors.append(f"materials manifest: {error}")
    try:
        release = _load(root / "governance/release.json")
        if (type(release) is not dict or set(release) != {"schema", "version", "api", "status", "schemas", "verifiers"}
                or release["schema"] != RELEASE_SCHEMA):
            raise ValueError("invalid release manifest schema")
        if not isinstance(release["version"], str) or not VERSION.fullmatch(release["version"]):
            raise ValueError("invalid package version")
        if not isinstance(release["api"], str) or not INTERFACE.fullmatch(release["api"]):
            raise ValueError("invalid versioned API identity")
        if not isinstance(release["status"], str) or release["status"] not in STATUSES:
            raise ValueError("invalid release status")
        schemas = release["schemas"]
        if (type(schemas) is not list or not schemas
                or any(not isinstance(s, str) or not INTERFACE.fullmatch(s) for s in schemas)
                or len(set(schemas)) != len(schemas)):
            raise ValueError("schemas must be unique versioned identities")
        verifiers = release["verifiers"]
        if (type(verifiers) is not list or not verifiers
                or any(not isinstance(v, str) or not INTERFACE.fullmatch(v) for v in verifiers)
                or len(set(verifiers)) != len(verifiers)):
            raise ValueError("verifiers must be unique versioned identities")
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        module = ast.parse((root / "src/hypersearch/__init__.py").read_text(encoding="utf-8"))
        values = [ast.literal_eval(node.value) for node in module.body
                  if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)]
        if values != [release["version"]] or project.get("project", {}).get("version") != release["version"]:
            errors.append("package version differs between release manifest, pyproject and __init__")
    except (ValueError, OSError, UnicodeError, SyntaxError, TypeError, RecursionError) as error:
        errors.append(f"release manifest: {error}")
    # Conservative, intentionally small policy: each literal uses directive must
    # have a single-line pinned external ref. GitHub dependency lockfiles are not
    # supported by this checker yet; this repo uses direct immutable refs.
    for path in sorted(tracked):
        if not path.startswith(".github/workflows/") or not path.endswith((".yml", ".yaml")):
            continue
        try:
            content = (root / path).read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), 1):
                match = re.match(r"\s*(?:-\s*)?[\"']?uses[\"']?\s*:\s*(.*?)\s*$", line)
                if not match:
                    if re.search(r"(?:^|[\s{,])[\"']?uses[\"']?\s*:", line) and not line.lstrip().startswith("#"):
                        errors.append(f"unsupported inline workflow uses syntax: {path}:{line_no}")
                    continue
                ref = match.group(1).split(" #", 1)[0].strip().strip("\"'")
                local = ref.startswith("./") and _path(ref[2:]) and (root / ref[2:]).is_dir()
                pinned_action = re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}", ref)
                pinned_container = re.fullmatch(r"docker://[^\s@]+@sha256:[0-9a-f]{64}", ref)
                if not (local or pinned_action or pinned_container):
                    errors.append(f"workflow uses ref must be local or immutable: {path}:{line_no}")
        except (OSError, UnicodeError) as error:
            errors.append(f"workflow unreadable: {path}: {error}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    errors = check(args.root)
    print(json.dumps({"passed": not errors, "errors": errors,
                      "scope": "local tracked material and release policy; not remote enforcement"}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
