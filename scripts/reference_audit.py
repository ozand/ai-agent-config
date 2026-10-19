#!/usr/bin/env python3
"""Bounded offline inventory for explicitly supplied Markdown inputs."""
import argparse
from bisect import bisect_left, insort
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
LINK = re.compile(r'!?\[[^\]]*\]\(\s*(<[^>]+>|[^\s()]+)(?:\s+["\'][^"\']*["\'])?\s*\)')
URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
FRONT = re.compile(r"^\s*[\w.-]+\s*:\s*[\"']?([^\"'\s#]+)")
PATH = re.compile(r"(?<![\w/])(?:\.{0,2}/)?(?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]{1,8}")
SECRET = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{16,}|Bearer\s+\S+|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[=:]\s*[\"']?[A-Za-z0-9_./+=-]{12,})")
USERINFO = re.compile(r"(?i)([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+(?::[^/@\s]*)?@")
ABS = re.compile(r"(?i)file:(?:/{1,3}|\\\\)[^`<>\"']*|(?<![\w:])(?:[A-Za-z]:[\\/]|(?<![.])(?<!/)\/(?!/)|\\\\|\\(?!\\)|//[^/\s]+/)[^`<>\"']*")
DYNAMIC = re.compile(r"(?:\$\{[^}]+\}|\$[A-Za-z]\w*|%[A-Za-z]\w*%|\{\{[^}]+\}\})(?:[\\/][^\s<>()\]]+)?")

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
    search_scope: str = ""

def sanitize(text: str) -> str:
    text = "".join(char if char in "\\t\\n\\r" or (ord(char) >= 32 and not 0x7f <= ord(char) <= 0x9f) else "�" for char in text)
    text = SECRET.sub("[REDACTED]", text)
    text = USERINFO.sub(r"\1[REDACTED]@", text)
    text = re.sub(r"(?<=[)}])/(?!/)", "[SLASH]", text)
    text = DYNAMIC.sub(lambda match: match.group(0).replace("/", "[SLASH]"), text)
    text = re.sub(r"(?i)file:(?:/{1,3}|\\\\)[^`<>\"']*", "[PATH]", text)
    text = re.sub(r"(?i)(?<=file:)/{1,3}", "[SLASH]", text)
    return ABS.sub("[PATH]", text).replace("[SLASH]", "/")

def normalize_windows_final_path(value: str) -> str:
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[len("\\\\?\\UNC\\"):]
    if value.startswith("\\\\?\\"):
        return value[len("\\\\?\\"):]
    return value


def within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def choose_root(path: Path, roots: list[Path], max_depth: int = MAX_DEPTH) -> int | None:
    eligible = [i for i, root in enumerate(roots) if within(path, root) and len(path.relative_to(root).parts) <= max_depth]
    return min(eligible, key=lambda i: (len(path.relative_to(roots[i]).parts), i)) if eligible else None


def classify_binding(target: str) -> str:
    if re.match(r"^[A-Za-z]:[\\/]", target) or target.startswith(("/", "\\")): return "host_absolute"
    if DYNAMIC.fullmatch(target): return "dynamic"
    if URI.match(target): return "external"
    if target.startswith(("./", "../")) or "/" in target: return "relative"
    return "entity_or_relative"


def extract(text):
    lines = text.splitlines()
    front = len(lines) > 1 and lines[0].strip() == "---"
    end = next((i for i in range(1, min(len(lines), 101)) if lines[i].strip() == "---"), 0) if front else 0
    for number, line in enumerate(lines, 1):
        links = list(LINK.finditer(line))
        found = [(m.group(1).strip("<>"), "markdown_link", m.span(1)) for m in links]
        markdown_spans = sorted(span for _, _, span in found)
        accepted_spans = []
        candidates = []
        candidates.extend((m.group(0), "path_candidate", m.span()) for m in re.finditer(r"(?<![:\w])//[^/\s]+/[^\s<>()]+", line))
        candidates.extend((m.group(0), "path_candidate", m.span()) for m in re.finditer(r"(?<![\w:])\\[A-Za-z0-9_.-]+(?:\\[^\s<>\"']+)+", line))
        candidates.extend((m.group(0), "dynamic_candidate", m.span()) for m in DYNAMIC.finditer(line))
        if front and 1 < number <= end:
            match = FRONT.match(line)
            if match and ("/" in match.group(1) or "." in match.group(1)):
                candidates.append((match.group(1), "frontmatter_candidate", match.span(1)))
        candidates.extend((m.group(0), "path_candidate", m.span()) for m in re.finditer(r"(?i)\b[A-Z]:[\\/][^\s<>()]+", line))
        uri_spans = sorted(m.span() for m in re.finditer(r"(?i)\b[A-Za-z][A-Za-z0-9+.-]*:[^\s<>()]+", line)
                     if not re.match(r"(?i)^[A-Z]:[\\/]", m.group(0)))
        def overlaps_uri(match):
            i = bisect_left(uri_spans, (match.start(), -1))
            return (i > 0 and uri_spans[i - 1][1] > match.start()) or (i < len(uri_spans) and uri_spans[i][0] < match.end())
        candidates.extend((m.group(0), "path_candidate", m.span()) for m in PATH.finditer(line)
                          if not overlaps_uri(m))
        for candidate in sorted(candidates, key=lambda item: (item[2][0], item[2][1], item[1])):
            span = candidate[2]
            i = bisect_left(markdown_spans, (span[0], -1))
            if (i > 0 and markdown_spans[i - 1][1] > span[0]) or (i < len(markdown_spans) and markdown_spans[i][0] < span[1]):
                continue
            if accepted_spans and accepted_spans[-1][1] > span[0]:
                continue
            found.append(candidate)
            accepted_spans.append(span)
        for target, relation, _ in sorted(found, key=lambda item: item[2]):
            yield number, target, relation, line


def safe_id(value: str, prefix: str = "S") -> str:
    return prefix + hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()[:12]

def public_text(value: str) -> str:
    return sanitize(value)

def public_record(record: Record) -> dict:
    row = asdict(record)
    for key in ("source", "target", "evidence", "search_scope"):
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
        selected_root = choose_root(real, allowed)
        if selected_root is None:
            raise ValueError("input exceeds depth limit")
        root = allowed[selected_root]
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
                final = Path(normalize_windows_final_path(buffer.value))
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
        logical = safe_id(f"root{selected_root}/{relative.as_posix()}")
        locator = sanitize(relative.as_posix())
        inputs.append((real, selected_root, logical, locator, text))
    names = {}
    for path, _, source, _, _ in inputs:
        names.setdefault(path.name.casefold(), []).append(source)
    records = []
    source_map = {source: locator for _, _, source, locator, _ in inputs}
    for path, _, source, _, text in inputs:
        for line, target, relation, context in extract(text):
            kind = classify_binding(target)
            exact, entity, candidates = "unchecked", "unchecked", ()
            if kind in {"relative", "entity_or_relative"} and not URI.match(target):
                if relation in {"markdown_link", "frontmatter_candidate"} and kind != "dynamic":
                    local_target = re.split(r"[?#]", target, maxsplit=1)[0]
                    if not local_target:
                        exact = "unchecked"
                    elif local_target:
                        local_target = local_target.replace("%20", " ")
                        unresolved = path.parent / local_target
                        candidate = unresolved.resolve(strict=False)
                        containing = [root for root in allowed if within(candidate, root)]
                        if not containing:
                            exact = "out_of_scope"
                        elif candidate.is_file():
                            exact = "exact_path"
                        elif candidate.is_dir():
                            exact = "unchecked"
                        else:
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
            if relation == "dynamic_candidate":
                kind = "dynamic"
                exact, entity, candidates = "unchecked", "unchecked", ()
            requirement = "unknown"
            scope = f"exact_path:declared_roots({len(allowed)});entity_match:supplied_input_basenames"
            records.append(Record("", source, line, sanitize(target), relation, requirement,
                exact, entity, kind, f"line:{line};kind:{relation}", candidates, scope))
    records.sort(key=lambda item: (item.source, item.line, item.target, item.relation))
    rows = [Record(f"R{i:04d}", item.source, item.line, item.target, item.relation,
        item.requirement, item.exact_path, item.entity_match, item.binding, item.evidence, item.candidates, item.search_scope)
        for i, item in enumerate(records, 1)]
    source_map = {source: locator for _, _, source, locator, _ in inputs}
    return rows, source_map


def make_report(records, source_map=None):
    rows = [public_record(record) for record in records]
    fields = ("exact_path", "entity_match", "binding", "requirement")
    counts = {field: {value: sum(row[field] == value for row in rows)
        for value in sorted({row[field] for row in rows})} for field in fields}
    return {"schema_version": 1, "sources": dict(sorted((source_map or {}).items())), "records": rows, "counts": counts}

def table_text(value: str) -> str:
    return sanitize(str(value)).replace("|", "\\\\|").replace("\r", " ").replace("\n", " ").replace("�", " ")

def render_table(data):
    lines = ["| Source ID | Source path | ID | Line | Target | Relation | Exact path | Entity | Binding | Requirement | Search scope |",
        "|---|---|---:|---:|---|---|---|---|---|---|---|"]
    paths = data.get("sources", {})
    for row in data["records"]:
        cells = [table_text(row[key]) for key in ("source", "id")]
        cells.insert(1, table_text(paths.get(row["source"], "[UNKNOWN]")))
        cells.extend([str(row["line"]), *(table_text(row.get(key, "")) for key in ("target", "relation", "exact_path", "entity_match", "binding", "requirement", "search_scope"))])
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
        records, source_map = build_records([Path(x) for x in args.files], roots)
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
