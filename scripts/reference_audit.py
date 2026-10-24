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
MAX_TOTAL_BYTES = 10_000_000
MAX_DEPTH = 8
HAS_SECURE_POSIX_OPEN = os.name != "nt" and hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd
MAX_RECORDS = 10000
MAX_LINK_TOKEN = 4096
URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
FRONT = re.compile(r"^\s*[\w.-]+\s*:\s*[\"']?([^\"'\s#]+)")
PATH_RUN = re.compile(r"(?<![\w/])[\w./-]+")
SECRET = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{16,}|Bearer\s+\S+|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|(?:api[_-]?key|access[_-]?token|refresh[_-]?token|aws[_-]?session[_-]?token|id[_-]?token|token|client[_-]?secret|password|passwd)\s*[=:]\s*[\"']?[A-Za-z0-9_./+=-]{12,})")
ENCODED_SECRET = re.compile(r"(?i)(?:api(?:%5f|_)key|access(?:%5f|_)token|refresh(?:%5f|_)token|aws(?:%5f|_)session(?:%5f|_)token|id(?:%5f|_)token|token|client(?:%5f|_)secret|password|passwd)(?:%3d|=)[A-Za-z0-9%._/+=-]{12,}")
URI_AUTHORITY = re.compile(r"(?i)\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/?#]*")
ABS = re.compile(r"(?i)(?<![\w+.-:])file:(?:[^`<>\"']*)|(?<![\w:])(?:[A-Za-z]:[\\/]|(?<![.])(?<![)/}])\/(?!/)|\\\\|(?<![.])\\(?![.\\])|//[^/\s]+/)[^`<>\"']*")
DYNAMIC = re.compile(r"(?:\$\{[^}]{1,512}\}|\$[A-Za-z]\w*|%[A-Za-z]\w*%|\{\{[^}]{1,512}\}\})(?:[\\/][^\s<>()\]]+)?")

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
    text = ENCODED_SECRET.sub("[REDACTED]", text)
    from urllib.parse import unquote
    def redact_encoded_secret(match):
        decoded = unquote(match.group(0))
        return "[REDACTED]" if SECRET.search(decoded) or ENCODED_SECRET.search(decoded) else match.group(0)
    text = re.sub(r"(?i)(?:api|access|aws|id|token|client|password|passwd)(?:%[0-9a-f]{2}|[A-Za-z0-9_=-]){1,512}", redact_encoded_secret, text)
    text = re.sub(r"(?i)bearer(?:%20|\s+)[A-Za-z0-9._~+/%=-]{12,}", redact_encoded_secret, text)
    text = re.sub(r"(?i)authorization(?:%3d|=)(?:bearer|basic)(?:%20|\s+)[A-Za-z0-9._~+/%=-]{12,}", redact_encoded_secret, text)
    def redact_authority(match):
        authority = match.group(0)
        scheme, rest = authority.split("://", 1)
        if "@" not in rest:
            return authority
        _, host = rest.rsplit("@", 1)
        return scheme + "://[REDACTED]@" + host
    text = URI_AUTHORITY.sub(redact_authority, text)
    matches = list(DYNAMIC.finditer(text))
    if not matches:
        result = ABS.sub("[PATH]", text)
    else:
        output = []
        cursor = 0
        for match in matches:
            output.append(ABS.sub("[PATH]", text[cursor:match.start()]))
            output.append(match.group(0))
            cursor = match.end()
        output.append(ABS.sub("[PATH]", text[cursor:]))
        result = "".join(output)
    return result

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
    if target.startswith((".\\", "..\\")) or ("\\" in target and not target.startswith("\\\\")): return "relative"
    if URI.match(target): return "external"
    if target.startswith(("./", "../", ".\\", "..\\")) or "/" in target or "\\" in target: return "relative"
    return "entity_or_relative"


def markdown_links(line):
    links = []
    closing_brackets = [match.start() for match in re.finditer(r"\]", line)]
    opening_brackets = [match.start() for match in re.finditer(r"\[", line)]
    i = 0
    while i < len(line):
        opener = line.find("[", i)
        if opener < 0:
            break
        close_index = bisect_left(closing_brackets, opener + 1)
        if close_index >= len(closing_brackets):
            break
        label_end = closing_brackets[close_index]
        search_limit = min(len(line), opener + MAX_LINK_TOKEN + 1)
        next_opener = bisect_left(opening_brackets, opener + 1)
        if label_end >= search_limit:
            i = opening_brackets[next_opener] if next_opener < len(opening_brackets) and opening_brackets[next_opener] < search_limit else search_limit
            continue
        if label_end + 1 >= len(line) or line[label_end + 1] != "(":
            i = label_end + 1
            continue
        if label_end - opener > MAX_LINK_TOKEN:
            i = label_end + 1
            continue
        cursor = label_end + 2
        while cursor < len(line) and line[cursor].isspace():
            cursor += 1
        if cursor < len(line) and line[cursor] == "<":
            destination_start = cursor + 1
            destination_end = line.find(">", destination_start, min(len(line), destination_start + MAX_LINK_TOKEN + 1))
            if destination_end < 0:
                i = max(opener + 1, min(len(line), destination_start + MAX_LINK_TOKEN))
                continue
            close_dest = destination_end + 1
        else:
            destination_start = cursor
            destination_end = cursor
            while destination_end < len(line) and destination_end - destination_start < MAX_LINK_TOKEN and not line[destination_end].isspace() and line[destination_end] not in ")(<>":
                destination_end += 1
            if destination_end == destination_start or (destination_end < len(line) and line[destination_end] in "(<>"):
                i = max(opener + 1, destination_end)
                continue
            close_dest = destination_end
        cursor = close_dest
        while cursor < len(line) and line[cursor].isspace():
            cursor += 1
        if cursor < len(line) and line[cursor] in "\\\"'":
            quote = line[cursor]
            title_end = line.find(quote, cursor + 1, min(len(line), cursor + MAX_LINK_TOKEN + 1))
            if title_end < 0:
                i = max(opener + 1, min(len(line), cursor + MAX_LINK_TOKEN))
                continue
            cursor = title_end + 1
            while cursor < len(line) and line[cursor].isspace():
                cursor += 1
        if cursor < len(line) and line[cursor] == ")":
            links.append((line[destination_start:destination_end], (destination_start, destination_end)))
            i = cursor + 1
        else:
            i = max(opener + 1, cursor)
    return links


def extract(text, record_budget=None, max_records=None):
    if max_records is None:
        max_records = MAX_RECORDS
    if record_budget is None:
        record_budget = [0]
    lines = text.splitlines()
    front = len(lines) > 1 and lines[0].strip() == "---"
    frontmatter_end = next((i for i in range(1, min(len(lines), 101)) if lines[i].strip() == "---"), 0) if front else 0
    for number, line in enumerate(lines, 1):
        found = []
        for destination, destination_span in markdown_links(line):
            if record_budget[0] + len(found) >= max_records:
                raise ValueError("record limit exceeded")
            found.append((destination, "markdown_link", destination_span))
        uri_spans = sorted(m.span() for m in re.finditer(r"(?i)\b[A-Za-z][A-Za-z0-9+.-]*:[^\s<>()]+", line)
                     if not re.match(r"(?i)^[A-Z]:[\\/]", m.group(0)))
        def overlaps_uri(match):
            return overlaps_span(match.start(), match.end())
        def overlaps_span(start, end):
            i = bisect_left(uri_spans, (start, -1))
            return (i > 0 and uri_spans[i - 1][1] > start) or (i < len(uri_spans) and uri_spans[i][0] < end)
        markdown_spans = sorted(span for _, _, span in found)
        accepted_spans = []
        candidates = []
        candidates.extend((m.group(0), "path_candidate", m.span()) for m in re.finditer(r"(?<![:\w])//[^/\s]+/[^\s<>()]+", line) if not overlaps_uri(m))
        for match in re.finditer(r"(?i)\bfile:[^\s<>()]+|(?<![\w:])(?:[A-Za-z]:[\\/]|(?<![.])(?<![)/}])/(?!/)|\\\\)[^\s`<>\"']+", line):
            token_end = match.start()
            while token_end < len(line) and not line[token_end].isspace() and line[token_end] not in "<>\"'`()[]{}":
                token_end += 1
            if token_end > match.start() and not overlaps_span(match.start(), token_end):
                candidates.append((line[match.start():token_end], "path_candidate", (match.start(), token_end)))
        candidates.extend((m.group(0), "path_candidate", m.span()) for m in re.finditer(r"(?<![\w:])\\[A-Za-z0-9_.-]+(?:\\[^\s<>\"']+)+", line) if not overlaps_uri(m))
        candidates.extend((m.group(0), "dynamic_candidate", m.span()) for m in DYNAMIC.finditer(line) if not overlaps_uri(m))
        if front and 1 < number <= frontmatter_end:
            match = FRONT.match(line)
            if match and ("/" in match.group(1) or "." in match.group(1)):
                candidates = [candidate for candidate in candidates if candidate[2][0] >= match.end(1) or candidate[2][1] <= match.start(1)]
                candidates.append((match.group(1), "frontmatter_candidate", match.span(1)))
        for run in PATH_RUN.finditer(line):
            value = run.group(0).rstrip(".")
            prefix = ""
            for relative_prefix in ("../", "./"):
                if value.startswith(relative_prefix):
                    prefix, value = relative_prefix, value[len(relative_prefix):]
                    break
            parts = value.split("/")
            basename = parts[-1]
            stem, dot, extension = basename.rpartition(".")
            valid_parts = all(part not in {"", ".", ".."} for part in parts[:-1]) and bool(stem)
            valid_extension = bool(dot) and 1 <= len(extension) <= 8 and extension.isalnum()
            if not (valid_parts and valid_extension):
                continue
            start, end = run.start(), run.start() + len(prefix) + len(value)
            if not overlaps_span(start, end):
                candidates.append((prefix + value, "path_candidate", (start, end)))
        candidates.sort(key=lambda item: (item[2][0], item[2][1], item[1]))
        merged = []
        for candidate in candidates:
            if merged and candidate[2][0] < merged[-1][2][1]:
                previous = merged[-1]
                if previous[1] == candidate[1] == "path_candidate":
                    start, stop = previous[2][0], max(previous[2][1], candidate[2][1])
                    merged[-1] = (line[start:stop], "path_candidate", (start, stop))
                continue
            merged.append(candidate)
        for candidate in merged:
            span = candidate[2]
            i = bisect_left(markdown_spans, (span[0], -1))
            if (i > 0 and markdown_spans[i - 1][1] > span[0]) or (i < len(markdown_spans) and markdown_spans[i][0] < span[1]):
                continue
            if accepted_spans and accepted_spans[-1][1] > span[0]:
                continue
            found.append(candidate)
            accepted_spans.append(span)
        if record_budget[0] + len(found) > max_records:
            raise ValueError("record limit exceeded")
        record_budget[0] += len(found)
        for target, relation, _ in sorted(found, key=lambda item: item[2]):
            yield number, target, relation, line


def safe_id(value: str, prefix: str = "S") -> str:
    return prefix + hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()[:12]

def public_text(value: str) -> str:
    return sanitize(value)

def public_record(record: Record) -> dict:
    row = asdict(record)
    for key in ("source", "target", "evidence", "search_scope"):
        row[key] = public_safe_text(public_text(str(row[key])))
    row["candidates"] = [public_safe_text(public_text(str(candidate))) for candidate in row["candidates"]]
    return row

def mermaid_text(value: str) -> str:
    return str(value).replace('"', "'").replace("[", "(").replace("]", ")").replace("\n", " ").replace("\r", " ")

def build_records(files, roots, max_records=None):
    if max_records is None:
        max_records = MAX_RECORDS
    allowed = [root.resolve(strict=True) for root in roots]
    if not allowed or any(not root.is_dir() for root in allowed):
        raise ValueError("existing directory root required")
    if len(set(allowed)) != len(allowed):
        raise ValueError("duplicate roots")
    inputs = []
    seen_inputs = set()
    total_bytes = 0
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
                remaining = MAX_TOTAL_BYTES - total_bytes
                with os.fdopen(fd, "rb") as handle_file:
                    raw = handle_file.read(min(MAX_FILE_BYTES, remaining) + 1)
                    fd = -1
                if len(raw) > MAX_FILE_BYTES:
                    raise ValueError("input exceeds size limit")
                if len(raw) > remaining:
                    raise ValueError("aggregate input size limit exceeded")
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
                    remaining = MAX_TOTAL_BYTES - total_bytes
                    raw = handle.read(min(MAX_FILE_BYTES, remaining) + 1)
                    if len(raw) > MAX_FILE_BYTES:
                        raise ValueError("input exceeds size limit")
                    if len(raw) > remaining:
                        raise ValueError("aggregate input size limit exceeded")
            finally:
                for opened_fd in reversed(opened_fds):
                    os.close(opened_fd)
                os.close(root_fd)
        total_bytes += len(raw)
        text = raw.decode("utf-8", "strict")
        logical = safe_id(f"root{selected_root}/{relative.as_posix()}")
        locator = relative.as_posix()
        inputs.append((real, selected_root, logical, locator, text))
    names = {}
    for path, _, source, _, _ in inputs:
        names.setdefault(path.name.casefold(), []).append(source)
    records = []
    source_map = {source: locator for _, _, source, locator, _ in inputs}
    record_budget = [0]
    for path, _, source, _, text in inputs:
        for line, target, relation, context in extract(text, record_budget, max_records):
            kind = classify_binding(target)
            decoded_target = None
            exact, entity, candidates = "unchecked", "unchecked", ()
            if "\x00" in target:
                exact, entity = "unchecked", "unchecked"
            if kind in {"relative", "entity_or_relative"} and "\x00" not in target and not URI.match(target):
                if relation in {"markdown_link", "frontmatter_candidate"} and kind != "dynamic":
                    local_target = re.split(r"[?#]", target, maxsplit=1)[0]
                    if not local_target:
                        exact = "unchecked"
                    elif local_target:
                        from urllib.parse import unquote, urlsplit
                        parsed = urlsplit(local_target)
                        decoded_target = None
                        try:
                            local_target = unquote(parsed.path, errors="strict")
                            decoded_target = local_target
                        except UnicodeDecodeError:
                            exact, local_target = "unchecked", ""
                        if local_target:
                            try:
                                if Path(local_target).is_absolute() or ".." in Path(local_target).parts or ".." in Path(local_target.replace("\\\\", "/")).parts:
                                    candidate = (path.parent / local_target).resolve(strict=False)
                                    if not any(within(candidate, root) for root in allowed):
                                        exact = "out_of_scope"
                                        local_target = ""
                            except ValueError:
                                exact, local_target = "unchecked", ""
                        if local_target:
                            normalized_target = local_target.replace("\\\\", "/")
                            unresolved = path.parent / normalized_target
                            try:
                                candidate = unresolved.resolve(strict=False)
                            except ValueError:
                                exact, candidate = "unchecked", None
                            containing = [root for root in allowed if candidate is not None and within(candidate, root)]
                            if candidate is None:
                                exact = "unchecked"
                            elif not containing:
                                exact = "out_of_scope"
                            else:
                                try:
                                    mode = candidate.stat().st_mode
                                except FileNotFoundError:
                                    exact = "not_found_in_scope"
                                except OSError:
                                    exact = "unchecked"
                                else:
                                    if stat.S_ISREG(mode):
                                        exact = "exact_path"
                                    elif stat.S_ISDIR(mode):
                                        exact = "unchecked"
                                    else:
                                        exact = "unchecked"
            lookup_target = decoded_target if decoded_target is not None else target
            try:
                lookup_basename = Path(re.split(r"[?#]", lookup_target, maxsplit=1)[0]).name.casefold()
            except ValueError:
                lookup_basename = ""
            named = tuple(sorted(names.get(lookup_basename, []))) if kind != "dynamic" and exact != "out_of_scope" and "\x00" not in target else ()
            if kind == "dynamic":
                named = ()
            if len(named) == 1:
                entity = "entity_match"
            elif len(named) > 1:
                entity, candidates = "ambiguous", named
            if relation == "path_candidate" and entity == "entity_match":
                exact = "unchecked"
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
    safe_sources = {key: public_locator(value) for key, value in (source_map or {}).items()}
    return {"schema_version": 1, "sources": dict(sorted(safe_sources.items())), "records": rows, "counts": counts}

def public_safe_text(value: str) -> str:
    output = []
    for char in value:
        if char == "~":
            output.append("~~")
        elif 0xDC80 <= ord(char) <= 0xDCFF:
            output.append(f"~u{ord(char):04X}~")
        else:
            output.append(char)
    return "".join(output)


def public_locator(value: str) -> str:
    safe = []
    for char in str(value):
        if char == "~":
            safe.append("~~")
        elif 0xDC80 <= ord(char) <= 0xDCFF:
            safe.append(f"~u{ord(char):04X}~")
        else:
            safe.append(char)
    return sanitize("".join(safe))


def table_text(value: str) -> str:
    value = str(value).replace("\r", " ").replace("\n", " ").replace("�", " ")
    output = []
    i = 0
    segment = 0
    while i < len(value):
        if value[i] != "|":
            i += 1
            continue
        slash_start = i
        while slash_start > segment and value[slash_start - 1] == "\\":
            slash_start -= 1
        output.append(sanitize(value[segment:slash_start]))
        count = i - slash_start
        output.append("\\" * count + ("\\" if count % 2 == 0 else "") + "|")
        i += 1
        segment = i
    output.append(sanitize(value[segment:]))
    return "".join(output)

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
        name = mermaid_text(public_text(row["target"]))
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
