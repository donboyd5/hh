"""Render the mailing-list md as HTML for import as a NEW Google Doc (local-only, PII).

Drive's HTML->Docs importer produces a real table from <table> markup (feeding it
markdown renders the pipes literally), and mishandles rowspan/colspan (shifts columns),
so every cell is emitted, blanks included - same shape as the md's own table. Each
version is uploaded under a NEW dated/versioned title (Don, 2026-09-13: colleagues
comment on the Doc, and those comments must never be overwritten), never over the
existing Doc.

Writes data/20_processed/drive-csv/final-mailing-list-draft.html

Usage:
    python scripts/export_drive_doc_html.py [suffix]
"""
from __future__ import annotations

import html
import re
import sys

from hh import config


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
    return s


def render(md: str) -> str:
    out: list[str] = ["<html><head><meta charset='utf-8'></head><body>"]
    lines = md.splitlines()
    i = 0
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            flush_para(); out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            flush_para(); out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("|"):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append("<table border='1' cellpadding='4' style='border-collapse:collapse'>")
            for r, cells in enumerate(rows):
                tag = "th" if r == 0 else "td"
                out.append("<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells) + "</tr>")
            out.append("</table>")
            continue
        elif line.startswith("- "):
            flush_para()
            out.append("<ul>")
            while i < len(lines) and lines[i].startswith("- "):
                out.append(f"<li>{_inline(lines[i][2:])}</li>"); i += 1
            out.append("</ul>")
            continue
        elif line.strip() == "":
            flush_para()
        else:
            para.append(line.strip())
        i += 1
    flush_para()
    out.append("</body></html>")
    return "\n".join(out)


def main() -> None:
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    md_path = config.layer_dir("processed") / f"final-mailing-list-draft{suffix}.md"
    out = config.layer_dir("processed") / "drive-csv" / "final-mailing-list-draft.html"
    out.write_text(render(md_path.read_text()))
    print(f"{md_path.name} -> {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
