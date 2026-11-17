"""Experimental input validation for a future Lean route; no execution or verdict.

Source bytes remain untrusted. A digest identifies a snapshot, not its origin,
dependency completeness, mathematical meaning, or safety to elaborate.
"""
from .study_json import artifact_bytes, digest, encode, fields, relative

SCHEMA = "hypersearch.lean-source-snapshot/draft1"
MAX_FILES = 128
MAX_FILE_BYTES = 262144
MAX_TOTAL_BYTES = 1048576


def validate_snapshot(value):
    fields(value, "schema files")
    if value["schema"] != SCHEMA or type(value["files"]) is not list:
        raise ValueError("unsupported source snapshot")
    if not 1 <= len(value["files"]) <= MAX_FILES:
        raise ValueError("source file count outside bounds")
    paths, contents, total = [], {}, 0
    for item in value["files"]:
        raw = artifact_bytes(item, maximum=MAX_FILE_BYTES)
        path = relative(item["path"])
        # One portable spelling and source-only envelope. No compiled imports,
        # archives, executable scripts, or filesystem-link representations.
        parts = path.split("/")
        if (any(not part.isascii() or not part or part.startswith(".")
                or any(not (c.isalnum() or c in "_-.") for c in part) for part in parts)
                or not (path.endswith(".lean") or path in
                        {"lakefile.toml", "lean-toolchain", "lake-manifest.json"})):
            raise ValueError("unsupported source path")
        folded = path.casefold()
        for prior in paths:
            if folded == prior or folded.startswith(prior + "/") or prior.startswith(folded + "/"):
                raise ValueError("duplicate, case-colliding, or file/directory-conflicting path")
        paths.append(folded)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("source snapshot exceeds total byte bound")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("source must be UTF-8 text") from error
        if "\x00" in text or "\r" in text:
            raise ValueError("source must not contain NUL or carriage returns")
        contents[path] = raw
    return contents


def snapshot_digest(value):
    """Identity is independent of file-list order, but sensitive to exact bytes."""
    contents = validate_snapshot(value)
    entries = [{"path": path, "bytes": len(raw), "sha256": digest(raw)}
               for path, raw in sorted(contents.items())]
    return digest(encode({"schema": SCHEMA, "files": entries}))
