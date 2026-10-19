#!/usr/bin/env python3
"""Bounded offline inventory for explicitly supplied Markdown inputs."""
import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_FILE_BYTES = 1_000_000
MAX_DEPTH = 8
LINK = re.compile(r"!?\[[^\]]*\]\(([^\s()]+)\)")
FRONT = re.compile(r"^\s*[\w.-]+\s*:\s*[\"']?([^\"'\s#]+)")
PATH = re.compile(r"(?<![\w/])(?:\.{0,2}/)?(?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]{1,8}")
SECRET = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{12,}|github_pat_[A-Za-z0-9_]{16,}|Bearer\s+\S+)")
ABS = re.compile(r"(?:[A-Za-z]:[\/]|/|\\)[^\s`<>\"']+")

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
    return ABS.sub("[PATH]", SECRET.sub("[REDACTED]", text))

def within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def classify_binding(target: str) -> str:
    if target.startswith(("http://", "https://")): return "external"
    if target.startswith(("${", "$", "%")) or "{{" in target: return "dynamic"
    if target.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", target): return "host_absolute"
    if target.startswith(("./", "../")): return "relative"
    return "entity_or_relative"


def extract(text):
    lines = text.splitlines()
    front = len(lines) > 1 and lines[0].strip() == "---"
    end = next((i for i in range(1, min(len(lines), 101)) if lines[i].strip() == "---"), 0) if front else 0
    for number, line in enumerate(lines, 1):
        found = [(m.group(1), "markdown_link") for m in LINK.finditer(line)]
        if front and 1 < number <= end:
            match = FRONT.match(line)
            if match and ("/" in match.group(1) or "." in match.group(1)):
                found.append((match.group(1), "frontmatter_candidate"))
        for match in PATH.finditer(line):
            if not any(target == match.group(0) for target, _ in found):
                found.append((match.group(0), "path_candidate"))
        for target, relation in found:
            yield number, target, relation, line


def build_records(files, roots):
    allowed = [root.resolve(strict=True) for root in roots]
    if not allowed or any(not root.is_dir() for root in allowed):
        raise ValueError("existing directory root required")
    if len(set(allowed)) != len(allowed):
        raise ValueError("duplicate roots")
    inputs = []
    for path in files:
        real = path.resolve(strict=True)
        root_ids = [i for i, root in enumerate(allowed) if within(real, root)]
        if not root_ids:
            raise ValueError("input outside declared roots")
        if not path.is_file():
            raise ValueError("input is not regular file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("input exceeds size limit")
        relative = real.relative_to(allowed[root_ids[0]])
        if len(relative.parts) > MAX_DEPTH:
            raise ValueError("input exceeds depth limit")
        text = path.read_bytes().decode("utf-8", "strict")
        inputs.append((path, f"root{root_ids[0]}/{relative.as_posix()}", text))
    names = {}
    for path, source, _ in inputs:
        names.setdefault(path.name.casefold(), []).append(source)
    records = []
    for path, source, text in inputs:
        for line, target, relation, context in extract(text):
            kind = "dynamic" if re.search(r"(?:\$\{|\$[A-Za-z]|%[A-Za-z])", context) else classify_binding(target)
            exact, entity, candidates = "unchecked", "unchecked", ()
            if kind in {"relative", "entity_or_relative"} and not target.startswith("../"):
                if relation in {"markdown_link", "frontmatter_candidate"}:
                    candidate = (path.parent / target).resolve(strict=False)
                    containing = [root for root in allowed if within(candidate, root)]
                    if containing:
                        if candidate.is_file():
                            exact = "exact_path"
                            candidates = (candidate.relative_to(containing[0]).as_posix(),)
                        else:
                            exact = "not_found_in_scope"
            named = tuple(sorted(names.get(Path(target).name.casefold(), [])))
            if len(named) == 1:
                entity = "entity_match"
            elif len(named) > 1:
                entity, candidates = "ambiguous", named
            if relation == "path_candidate" and entity == "entity_match":
                exact = "not_found_in_scope"
            requirement = "mentioned_only" if re.search(r"(?i)example|for instance|e\.g\.", context) else "unknown"
            records.append(Record("", source, line, sanitize(target), relation, requirement,
                exact, entity, kind, f"line:{line};kind:{relation}", candidates))
    records.sort(key=lambda item: (item.source, item.line, item.target, item.relation))
    return [Record(f"R{i:04d}", item.source, item.line, item.target, item.relation,
        item.requirement, item.exact_path, item.entity_match, item.binding, item.evidence, item.candidates)
        for i, item in enumerate(records, 1)]


def make_report(records):
    rows = [asdict(record) for record in records]
    fields = ("exact_path", "entity_match", "binding", "requirement")
    counts = {field: {value: sum(row[field] == value for row in rows)
        for value in sorted({row[field] for row in rows})} for field in fields}
    return {"schema_version": 1, "records": rows, "counts": counts}

def render_table(data):
    keys = ("id", "source", "line", "target", "relation", "exact_path", "entity_match", "binding", "requirement")
    lines = ["| ID | Source | Line | Target | Relation | Exact path | Entity | Binding | Requirement |",
        "|---|---|---:|---|---|---|---|---|---|"]
    for row in data["records"]:
        cells = [str(row[key]).replace("|", "\\\\|") for key in keys]
        lines.append("| " + " | ".join(cells) + " |")
    return "\\n".join(lines)

def render_mermaid(data):
    lines = ["graph LR"]
    for row in data["records"]:
        source = re.sub(r"[^A-Za-z0-9_]", "_", row["source"])
        target = "T_" + row["id"]
        label = sanitize(f"{row['relation']}:{row['exact_path']}/{row['entity_match']}").replace('"', "'").replace("[", "(").replace("]", ")")
        name = sanitize(row["target"]).replace('"', "'").replace("[", "(").replace("]", ")")
        lines.append(f'  {source}["{row["source"]}"] -->|{label}| {target}["{name}"]')
    return "\\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded offline Markdown reference inventory")
    parser.add_argument("--root", action="append", required=True)
    parser.add_argument("--format", choices=("json", "table", "mermaid", "all"), default="all")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)
    try:
        data = make_report(build_records([Path(x) for x in args.files], [Path(x) for x in args.root]))
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
