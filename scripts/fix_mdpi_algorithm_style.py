"""Make Algorithm 1–2 captions/body match MDPI caption + keyword style."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

SRC = Path(r"c:\Users\as\Desktop\bodmas\IEEE_MCP_Paper_Style_Edited.docx")

# Longer keywords first so "else if" wins over "else"/"if"
KEYWORDS = [
    "else if",
    "for all",
    "Input",
    "Output",
    "Require",
    "Ensure",
    "return",
    "else",
    "then",
    "for",
    "do",
    "if",
]


def style_run(run, *, bold=False, italic=False, size=9, font="Courier New"):
    run.bold = bold
    run.italic = italic
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)


def clear_runs(paragraph):
    for r in paragraph.runs:
        r.text = ""


def set_mdpi_caption(paragraph, kind: str, num: int, title: str):
    title = title.strip().rstrip(".")
    # sentence case like Table/Figure captions
    if title:
        title = title[0].upper() + title[1:].lower()
        for ac in ("MCP", "ALLOW", "DENY", "ASK", "YAML"):
            title = re.sub(rf"\b{ac.lower()}\b", ac, title, flags=re.I)
        if not title.endswith("."):
            title += "."
    label = f"{kind} {num}."
    clear_runs(paragraph)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if paragraph.runs:
        paragraph.runs[0].text = label
        style_run(paragraph.runs[0], bold=True, font="Times New Roman")
        for r in paragraph.runs[1:]:
            r.text = ""
        r2 = paragraph.add_run(f" {title}")
        style_run(r2, bold=False, font="Times New Roman")
    else:
        r1 = paragraph.add_run(label)
        style_run(r1, bold=True, font="Times New Roman")
        r2 = paragraph.add_run(f" {title}")
        style_run(r2, bold=False, font="Times New Roman")


def tokenize_with_keywords(text: str) -> list[tuple[str, bool]]:
    """Split text into (chunk, is_keyword) preserving order."""
    # Word boundaries so 'do' does not match inside 'domain'
    pattern = re.compile(
        r"(?<![A-Za-z_])("
        + "|".join(re.escape(k) for k in KEYWORDS)
        + r")(?![A-Za-z_])",
        flags=re.IGNORECASE,
    )
    parts: list[tuple[str, bool]] = []
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            parts.append((text[pos : m.start()], False))
        # Keep original casing for body keywords except Input/Output labels
        kw = m.group(0)
        canon = None
        for k in KEYWORDS:
            if kw.lower() == k.lower():
                canon = k
                break
        # Prefer lowercase for control words; keep Input/Output capitalized
        if canon in {"Input", "Output", "Require", "Ensure"}:
            out = canon
        else:
            out = canon.lower() if canon else kw
        parts.append((out, True))
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], False))
    return parts


def rewrite_algo_line(paragraph):
    text = paragraph.text
    if not text.strip():
        return
    clear_runs(paragraph)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    # Special-case Input:/Output: labels as bold + rest normal
    m = re.match(r"^(Input|Output|Require|Ensure):(.*)$", text)
    chunks: list[tuple[str, bool]]
    if m:
        chunks = [(m.group(1) + ":", True), (m.group(2), False)]
    else:
        chunks = tokenize_with_keywords(text)

    # Ensure at least one run exists
    first = True
    for chunk, is_kw in chunks:
        if not chunk:
            continue
        if first and paragraph.runs:
            run = paragraph.runs[0]
            run.text = chunk
            first = False
        else:
            run = paragraph.add_run(chunk)
            first = False
        style_run(run, bold=is_kw, font="Courier New", size=9)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = Document(str(SRC))

    caption_re = re.compile(r"^Algorithm\s+(\d+)\.\s*(.*)$")
    # Identify algorithm blocks by caption indices
    algo_ranges: list[tuple[int, int]] = []
    captions: list[tuple[int, int, str]] = []
    for i, p in enumerate(doc.paragraphs):
        m = caption_re.match(p.text.strip())
        if m:
            captions.append((i, int(m.group(1)), m.group(2)))

    for idx, (start, num, title) in enumerate(captions):
        end = captions[idx + 1][0] if idx + 1 < len(captions) else None
        # stop before next non-algorithm prose: first non-empty non-code after return
        stop = start + 1
        while stop < len(doc.paragraphs):
            if end is not None and stop >= end:
                break
            t = doc.paragraphs[stop].text.strip()
            if not t:
                # allow one blank inside block; stop if following looks like section prose
                nxt = ""
                if stop + 1 < len(doc.paragraphs):
                    nxt = doc.paragraphs[stop + 1].text.strip()
                if nxt and not (
                    nxt.startswith(("Input:", "Output:", "Require:", "Ensure:"))
                    or re.match(r"^\d+:", nxt)
                    or nxt.startswith("Algorithm ")
                ):
                    break
                stop += 1
                continue
            if t.startswith("Algorithm ") and caption_re.match(t):
                break
            if not (
                t.startswith(("Input:", "Output:", "Require:", "Ensure:"))
                or re.match(r"^\d+:", t)
            ):
                break
            stop += 1
        algo_ranges.append((start, stop, num, title))

    for start, stop, num, title in algo_ranges:
        set_mdpi_caption(doc.paragraphs[start], "Algorithm", num, title)
        for j in range(start + 1, stop):
            if doc.paragraphs[j].text.strip():
                rewrite_algo_line(doc.paragraphs[j])

    doc.save(str(SRC))
    print(f"Saved {SRC}")
    print("Algorithm blocks:")
    for start, stop, num, title in algo_ranges:
        print(f"  Algorithm {num}: paras {start}-{stop - 1}")
        print("   caption:", doc.paragraphs[start].text)
        print("   first line:", doc.paragraphs[start + 1].text)
        # show a keyword-styled sample
        sample = doc.paragraphs[min(start + 5, stop - 1)]
        print(
            "   sample runs:",
            [(r.text, bool(r.bold)) for r in sample.runs if r.text][:8],
        )


if __name__ == "__main__":
    main()
