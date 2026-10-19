#!/usr/bin/env python3
"""Bounded offline inventory for explicitly supplied Markdown inputs."""
import argparse
import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_FILE_BYTES = 1_000_000
MAX_DEPTH = 8
HAS_SECURE_POSIX_OPEN = os.name != "nt" and hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd
LINK = re.compile(r"!?\[[^\]]*\]\(([^\s()]+)\)")
URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
FRONT = re.compile(r"^\s*[\w.-]+\s*:\s*[\"']?([^\"'\s#]+)")
PATH = re.compile(r"(?<![\w/])(?:\.{0,2}/)?(?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]{1,8}")
SECRET = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{16,}|Bearer\s+\S+)")
ABS = re.compile(r"(?i)file:(?:/{1,3}|\\\\)[^\s`<>\"']*|(?<![\w:])(?:[A-Za-z]:[\\/]|(?<!/)\/(?!/)|\\\\)[^\s`<>\"']+")

@dataclass(frozen=True)
class Record:
    id: str
    source: str
    line: int
    target: str
    relation: str
    requirement: str
    exact_path: str
    entity_match: str
    binding: str
    evidence: str
    candidates: tuple[str, ...]

def sanitize(text: str) -> str:
    text = SECRET.sub("[REDACTED]", text)
    text = re.sub(r"(?<=[)}])/(?!/)", "[SLASH]", text)
    text = re.sub(r"(?i)file:(?:/{1,3}|\\\\)[^\s`<>\"']*", "[PATH]", text)
    text = re.sub(r"(?i)(?<=file:)/{1,3}", "[SLASH]", text)
    return ABS.sub("[PATH]", text).replace("[SLASH]", "/")

def within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def classify_binding(target: str) -> str:
    if re.search(r"(?:\$\{|\$[A-Za-z]|%[A-Za-z])", target) or "{{" in target: return "dynamic"
    if URI.match(target): return "external"
    if target.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", target): return "host_absolute"
    if target.startswith(("./", "../")) or "/" in target: return "relative"
    return "entity_or_relative"


def extract(text):
    lines = text.splitlines()
    front = len(lines) > 1 and lines[0].strip() == "---"
    end = next((i for i in range(1, min(len(lines), 101)) if lines[i].strip() == "---"), 0) if front else 0
    for number, line in enumerate(lines, 1):
        links = list(LINK.finditer(line))
        found = [(m.group(1), "markdown_link", m.span(1)) for m in links]
        dynamic_spans = [m.span() for m in re.finditer(r"(?:\$\{[^}]+\}|\$[A-Za-z]\w*|%[A-Za-z]\w*)(?:/[^\s]+)?", line)]
        if front and 1 < number <= end:
            match = FRONT.match(line)
            if match and ("/" in match.group(1) or "." in match.group(1)):
                found.append((match.group(1), "frontmatter_candidate", match.span(1)))
        for match in PATH.finditer(line):
            if not any(match.start() < span[1] and span[0] < match.end() for _, _, span in found + [("", "dynamic", span) for span in dynamic_spans]):
                found.append((match.group(0), "path_candidate", match.span()))
        uri_spans = [m.span() for m in re.finditer(r"(?i)\b[A-Za-z][A-Za-z0-9+.-]*:[^\s<>()]+", line)]
        for match in PATH.finditer(line):
            if any(match.start() < end and start < match.end() for start, end in uri_spans):
                continue
            if not any(match.start() < span[1] and span[0] < match.end() for _, _, span in found):
                found.append((match.group(0), "path_candidate", match.span()))
        for target, relation, _ in found:
            yield number, target, relation, line


def safe_id(value: str, prefix: str = "S") -> str:
    return prefix + hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()[:12]

def public_text(value: str) -> str:
    return sanitize(value)

def public_record(record: Record) -> dict:
    row = asdict(record)
    for key in ("source", "target", "evidence"):
        row[key] = public_text(str(row[key]))
    row["candidates"] = [public_text(str(candidate)) for candidate in row["candidates"]]
    return row

def mermaid_text(value: str) -> str:
    return sanitize(value).replace('"', "'").replace("[", "(").replace("]", ")").replace("\n", " ").replace("\r", " ")

def build_records(files, roots):
    allowed = [root.resolve(strict=True) for root in roots]
    if not allowed or any(not root.is_dir() for root in allowed):
        raise ValueError("existing directory root required")
    if len(set(allowed)) != len(allowed):
        raise ValueError("duplicate roots")
    inputs = []
    seen_inputs = set()
    for path in files:
        real = path.resolve(strict=True)
        if real in seen_inputs:
            continue
        seen_inputs.add(real)
        root_ids = [i for i, root in enumerate(allowed) if within(real, root)]
        if not root_ids:
            raise ValueError("input outside declared roots")
        root = allowed[root_ids[0]]
        relative = real.relative_to(root)
        if not relative.parts:
            raise ValueError("input must be a file beneath a declared root")
        if len(relative.parts) > MAX_DEPTH:
            raise ValueError("input exceeds depth limit")
        if os.name == "nt":
            import ctypes
            import msvcrt
            fd = os.open(real, os.O_RDONLY | getattr(os, "O_BINARY", 0))
            try:
                handle = msvcrt.get_osfhandle(fd)
                get_final = ctypes.windll.kernel32.GetFinalPathNameByHandleW
                get_final.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
                get_final.restype = ctypes.c_uint32
                buffer = ctypes.create_unicode_buffer(32768)
                length = get_final(handle, buffer, len(buffer), 0)
                if not length or length >= len(buffer):
                    raise ValueError("cannot verify opened input path")
                final = Path(buffer.value.removeprefix("\\\\?\\"))
                if not within(final.resolve(strict=True), root):
                    raise ValueError("input outside declared roots")
                file_stat = os.fstat(fd)
                if not stat.S_ISREG(file_stat.st_mode):
                    raise ValueError("input is not regular file")
                if file_stat.st_size > MAX_FILE_BYTES:
                    raise ValueError("input exceeds size limit")
                with os.fdopen(fd, "rb") as handle_file:
                    raw = handle_file.read(MAX_FILE_BYTES + 1)
                    fd = -1
                if len(raw) > MAX_FILE_BYTES:
                    raise ValueError("input exceeds size limit")
            finally:
                if fd >= 0:
                    os.close(fd)
        else:
            if not HAS_SECURE_POSIX_OPEN:
                raise ValueError("secure bounded file opening is unsupported on this platform")
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
            root_fd = os.open(root, flags | getattr(os, "O_DIRECTORY", 0))
            opened_fds = []
            try:
                current_fd = root_fd
                for component in relative.parts[:-1]:
                    current_fd = os.open(component, flags | getattr(os, "O_DIRECTORY", 0), dir_fd=current_fd)
                    opened_fds.append(current_fd)
                fd = os.open(relative.parts[-1], flags, dir_fd=current_fd)
                with os.fdopen(fd, "rb") as handle:
                    file_stat = os.fstat(handle.fileno())
                    if not stat.S_ISREG(file_stat.st_mode):
                        raise ValueError("input is not regular file")
                    if file_stat.st_size > MAX_FILE_BYTES:
                        raise ValueError("input exceeds size limit")
                    raw = handle.read(MAX_FILE_BYTES + 1)
                    if len(raw) > MAX_FILE_BYTES:
                        raise ValueError("input exceeds size limit")
            finally:
                for opened_fd in reversed(opened_fds):
                    os.close(opened_fd)
                os.close(root_fd)
        text = raw.decode("utf-8", "strict")
        logical = safe_id(f"root{root_ids[0]}/{relative.as_posix()}")
        locator = sanitize(relative.as_posix())
        inputs.append((real, logical, locator, text))
    names = {}
    for path, source, _, _ in inputs:
        names.setdefault(path.name.casefold(), []).append(source)
    records = []
    source_map = {source: locator for _, source, locator, _ in inputs}
    for path, source, _, text in inputs:
        for line, target, relation, context in extract(text):
            kind = classify_binding(target)
            exact, entity, candidates = "unchecked", "unchecked", ()
            if kind in {"relative", "entity_or_relative"} and not target.startswith("../") and not URI.match(target):
                if relation in {"markdown_link", "frontmatter_candidate"} and kind != "dynamic":
                    local_target = re.split(r"[?#]", target, maxsplit=1)[0]
                    if not local_target:
                        exact = "unchecked"
                    elif local_target:
                        local_target = local_target.replace("%20", " ")
                        unresolved = path.parent / local_target
                        if unresolved.is_symlink():
                            exact = "out_of_scope"
                        else:
                            candidate = unresolved.resolve(strict=False)
                            containing = [root for root in allowed if within(candidate, root)]
                            if containing and candidate.is_file():
                                exact = "exact_path"
                            elif containing and candidate.is_dir():
                                exact = "unchecked"
                            elif containing:
                                exact = "not_found_in_scope"
            named = tuple(sorted(names.get(Path(re.split(r"[?#]", target, maxsplit=1)[0]).name.casefold(), []))) if kind != "dynamic" and exact != "out_of_scope" else ()
            if kind == "dynamic":
                named = ()
            if len(named) == 1:
                entity = "entity_match"
            elif len(named) > 1:
                entity, candidates = "ambiguous", named
            if relation == "path_candidate" and entity == "entity_match":
                exact = "not_found_in_scope"
            if relation == "path_candidate" and classify_binding(target) == "host_absolute" and re.search(r"(?:\$\{|\$[A-Za-z]|%[A-Za-z])", context):
                kind = "dynamic"
                exact, entity, candidates = "unchecked", "unchecked", ()
            requirement = "unknown"
            records.append(Record("", source, line, sanitize(target), relation, requirement,
                exact, entity, kind, f"line:{line};kind:{relation}", candidates))
    records.sort(key=lambda item: (item.source, item.line, item.target, item.relation))
    return [Record(f"R{i:04d}", item.source, item.line, item.target, item.relation,
        item.requirement, item.exact_path, item.entity_match, item.binding, item.evidence, item.candidates)
        for i, item in enumerate(records, 1)]


def make_report(records, source_map=None):
    rows = [public_record(record) for record in records]
    fields = ("exact_path", "entity_match", "binding", "requirement")
    counts = {field: {value: sum(row[field] == value for row in rows)
        for value in sorted({row[field] for row in rows})} for field in fields}
    return {"schema_version": 1, "sources": dict(sorted((source_map or {}).items())), "records": rows, "counts": counts}

def table_text(value: str) -> str:
    return str(value).replace("|", "\\\\|").replace("\r", " ").replace("\n", " ")

def render_table(data):
    lines = ["| Source ID | Source path | ID | Line | Target | Relation | Exact path | Entity | Binding | Requirement |",
        "|---|---|---:|---:|---|---|---|---|---|---|"]
    paths = data.get("sources", {})
    for row in data["records"]:
        cells = [table_text(row[key]) for key in ("source", "id")]
        cells.insert(1, table_text(paths.get(row["source"], "[UNKNOWN]")))
        cells.extend([str(row["line"]), *(table_text(row[key]) for key in ("target", "relation", "exact_path", "entity_match", "binding", "requirement"))])
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

def render_mermaid(data):
    lines = ["graph LR"]
    for row in data["records"]:
        source = safe_id(row["source"])
        source_path = mermaid_text(data.get("sources", {}).get(row["source"], "[UNKNOWN]"))
        target = "T_" + row["id"]
        label = mermaid_text(f"{row['relation']}:{row['exact_path']}/{row['entity_match']}")
        name = mermaid_text(row["target"])
        lines.append(f'  {source}["{source_path}"] -->|{label}| {target}["{name}"]')
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded offline Markdown reference inventory")
    parser.add_argument("--root", action="append", required=True)
    parser.add_argument("--format", choices=("json", "table", "mermaid", "all"), default="all")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)
    try:
        roots = [Path(x).resolve(strict=True) for x in args.root]
        records = build_records([Path(x) for x in args.files], roots)
        source_map = {safe_id(f"root{index}/{relative.as_posix()}"): sanitize(relative.as_posix())
            for index, root in enumerate(roots) for path in dict.fromkeys(Path(x).resolve(strict=True) for x in args.files)
            if within(path, root) for relative in [path.relative_to(root)]}
        data = make_report(records, source_map)
        output = []
        if args.format in {"json", "all"}:
            output.append(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
        if args.format in {"table", "all"}:
            output.append(render_table(data))
        if args.format in {"mermaid", "all"}:
            output.append("```mermaid\n" + render_mermaid(data) + "\n```")
        print("\n\n".join(output))
    except (OSError, UnicodeError, ValueError) as exc:
        print("reference audit failed: " + sanitize(str(exc)), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
