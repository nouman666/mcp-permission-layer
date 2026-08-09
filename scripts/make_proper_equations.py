"""Replace plain-text equations with proper Word OMML math equations."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

SRC = Path(r"c:\Users\as\Desktop\bodmas\IEEE_MCP_Paper_Style_Edited.docx")
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def m(tag: str):
    return OxmlElement(f"m:{tag}")


def w(tag: str):
    return OxmlElement(f"w:{tag}")


def mr(text: str, italic: bool | None = None):
    """Math run."""
    r = m("r")
    rpr = m("rPr")
    sty = m("sty")
    if italic is True:
        sty.set(qn("m:val"), "p")  # plain? actually i=italic, p=plain
        # In OMML: sty val "p" = upright, default is italic for variables
        rpr.append(sty)
    elif italic is False:
        sty.set(qn("m:val"), "p")
        rpr.append(sty)
    r.append(rpr)
    t = m("t")
    # preserve spaces
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    r.append(t)
    return r


def mplain(text: str):
    """Upright math text (function names, labels)."""
    r = m("r")
    rpr = m("rPr")
    sty = m("sty")
    sty.set(qn("m:val"), "p")
    rpr.append(sty)
    r.append(rpr)
    t = m("t")
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    r.append(t)
    return r


def mfrac(num_nodes, den_nodes):
    f = m("f")
    num = m("num")
    for n in num_nodes:
        num.append(n)
    den = m("den")
    for n in den_nodes:
        den.append(n)
    f.append(num)
    f.append(den)
    return f


def msub(base_nodes, sub_nodes):
    s = m("sSub")
    e = m("e")
    for n in base_nodes:
        e.append(n)
    sub = m("sub")
    for n in sub_nodes:
        sub.append(n)
    s.append(e)
    s.append(sub)
    return s


def msup(base_nodes, sup_nodes):
    s = m("sSup")
    e = m("e")
    for n in base_nodes:
        e.append(n)
    sup = m("sup")
    for n in sup_nodes:
        sup.append(n)
    s.append(e)
    s.append(sup)
    return s


def mrows(*nodes):
    return list(nodes)


def mcases(rows: list[list]):
    """
    rows: list of [left_nodes, right_condition_nodes]
    Rendered as { left    right
    """
    d = m("d")
    dpr = m("dPr")
    beg = m("begChr")
    beg.set(qn("m:val"), "{")
    end = m("endChr")
    end.set(qn("m:val"), "")
    dpr.append(beg)
    dpr.append(end)
    d.append(dpr)

    e = m("e")
    eq = m("eqArr")
    for left_nodes, right_nodes in rows:
        ee = m("e")
        for n in left_nodes:
            ee.append(n)
        # spacer
        ee.append(mplain("    "))
        for n in right_nodes:
            ee.append(n)
        eq.append(ee)
    e.append(eq)
    d.append(e)
    return d


def build_omath(children):
    om = m("oMath")
    for c in children:
        om.append(c)
    return om


def set_equation_paragraph(paragraph, omath, number: int):
    """Replace paragraph content with centered OMML equation + (n)."""
    p = paragraph._p
    # remove all children except pPr
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)

    # ensure pPr alignment center
    pPr = p.find(qn("w:pPr"))
    if pPr is None:
        pPr = w("pPr")
        p.insert(0, pPr)
    jc = pPr.find(qn("w:jc"))
    if jc is None:
        jc = w("jc")
        pPr.append(jc)
    jc.set(qn("w:val"), "center")

    # spacing tight
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        spacing = w("spacing")
        pPr.append(spacing)
    spacing.set(qn("w:before"), "80")
    spacing.set(qn("w:after"), "80")

    # oMathPara wrapper
    omp = m("oMathPara")
    ompPr = m("oMathParaPr")
    jc2 = m("jc")
    jc2.set(qn("m:val"), "center")
    ompPr.append(jc2)
    omp.append(ompPr)
    omp.append(omath)
    p.append(omp)

    # equation number as normal run on same paragraph
    r = w("r")
    rpr = w("rPr")
    rfonts = w("rFonts")
    rfonts.set(qn("w:ascii"), "Times New Roman")
    rfonts.set(qn("w:hAnsi"), "Times New Roman")
    sz = w("sz")
    sz.set(qn("w:val"), "20")  # 10pt
    szCs = w("szCs")
    szCs.set(qn("w:val"), "20")
    rpr.append(rfonts)
    rpr.append(sz)
    rpr.append(szCs)
    r.append(rpr)
    t = w("t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = f"    ({number})"
    r.append(t)
    p.append(r)


def eq1():
    # P = P_name ∪ P_args ∪ P_sens
    return build_omath(
        [
            mr("P"),
            mplain(" = "),
            msub([mr("P")], [mplain("name")]),
            mplain(" ∪ "),
            msub([mr("P")], [mplain("args")]),
            mplain(" ∪ "),
            msub([mr("P")], [mplain("sens")]),
        ]
    )


def eq2():
    # path(v) ∧ writeContext(n)=true ⇒ P ← P ∪ {fs.write}
    return build_omath(
        [
            mplain("path"),
            mplain("("),
            mr("v"),
            mplain(") ∧ writeContext("),
            mr("n"),
            mplain(") = true  ⇒  "),
            mr("P"),
            mplain(" ← "),
            mr("P"),
            mplain(" ∪ {fs.write}"),
        ]
    )


def eq3():
    return build_omath(
        [
            mplain("path"),
            mplain("("),
            mr("v"),
            mplain(") ∧ writeContext("),
            mr("n"),
            mplain(") = false  ⇒  "),
            mr("P"),
            mplain(" ← "),
            mr("P"),
            mplain(" ∪ {fs.read}"),
        ]
    )


def eq4():
    # if P=∅ then P←{code.exec}, h←true
    return build_omath(
        [
            mplain("if "),
            mr("P"),
            mplain(" = ∅ then "),
            mr("P"),
            mplain(" ← {code.exec},  "),
            mr("h"),
            mplain(" ← true"),
        ]
    )


def eq5():
    return build_omath(
        [
            mr("D"),
            mplain("["),
            mr("c"),
            mplain("] = DENY"),
            mplain("    if "),
            mr("r"),
            mplain(".allow = false ∨ restrictions("),
            mr("r"),
            mplain(","),
            mr("τ"),
            mplain(") violated"),
        ]
    )


def eq6():
    return build_omath(
        [
            mr("D"),
            mplain("["),
            mr("c"),
            mplain("] = "),
            mr("r"),
            mplain(".mode"),
            mplain("    if "),
            mr("r"),
            mplain(".allow = true ∧ restrictions("),
            mr("r"),
            mplain(","),
            mr("τ"),
            mplain(") satisfied"),
        ]
    )


def eq10():
    # ASR = |{τ∈M:d(τ)=ALLOW}| / |M|
    num = [
        mplain("|{"),
        mr("τ"),
        mplain(" ∈ "),
        mr("M"),
        mplain(" : "),
        mr("d"),
        mplain("("),
        mr("τ"),
        mplain(") = ALLOW}|"),
    ]
    den = [mplain("|"), mr("M"), mplain("|")]
    return build_omath([mplain("ASR = "), mfrac(num, den)])


def eq11():
    num = [
        mplain("|{"),
        mr("τ"),
        mplain(" ∈ "),
        mr("M"),
        mplain(" : "),
        mr("d"),
        mplain("("),
        mr("τ"),
        mplain(") = DENY}|"),
    ]
    den = [mplain("|"), mr("M"), mplain("|")]
    return build_omath(
        [
            mplain("Block = 1 − ASR = "),
            mfrac(num, den),
        ]
    )


def eq12():
    num = [
        mplain("|{"),
        mr("τ"),
        mplain(" ∈ "),
        mr("B"),
        mplain(" : "),
        mr("d"),
        mplain("("),
        mr("τ"),
        mplain(") = ALLOW}|"),
    ]
    den = [mplain("|"), mr("B"), mplain("|")]
    return build_omath([mplain("TSR = "), mfrac(num, den)])


def eq13():
    return build_omath(
        [
            mplain("TP = |{"),
            mr("τ"),
            mplain(" ∈ "),
            mr("M"),
            mplain(" : "),
            mr("d"),
            mplain("("),
            mr("τ"),
            mplain(") = DENY}|,   FP = |{"),
            mr("τ"),
            mplain(" ∈ "),
            mr("B"),
            mplain(" : "),
            mr("d"),
            mplain("("),
            mr("τ"),
            mplain(") = DENY}|"),
        ]
    )


def eq14():
    return build_omath(
        [
            mplain("FN = |{"),
            mr("τ"),
            mplain(" ∈ "),
            mr("M"),
            mplain(" : "),
            mr("d"),
            mplain("("),
            mr("τ"),
            mplain(") = ALLOW}|,   TN = |{"),
            mr("τ"),
            mplain(" ∈ "),
            mr("B"),
            mplain(" : "),
            mr("d"),
            mplain("("),
            mr("τ"),
            mplain(") = ALLOW}|"),
        ]
    )


def eq15():
    num = [mplain("2 ⋅ TP")]
    den = [mplain("2 ⋅ TP + FP + FN")]
    return build_omath([mplain("F1 = "), mfrac(num, den)])


def eq16():
    # ASR_UB = 1 - 0.05^(1/n)
    return build_omath(
        [
            msub([mplain("ASR")], [mplain("UB")]),
            mplain(" = 1 − "),
            msup([mplain("0.05")], [mfrac([mplain("1")], [mr("n")])]),
        ]
    )


def eq_d_cases():
    """Proper cases form for aggregation (will replace eqs 7-9 display)."""
    rows = [
        (
            [mplain("DENY")],
            [mplain("if  ∃"), mr("c"), mplain(" ∈ "), mr("P"), mplain(" : "), mr("D"), mplain("["), mr("c"), mplain("] = DENY")],
        ),
        (
            [mplain("ASK")],
            [mplain("else if  ∃"), mr("c"), mplain(" ∈ "), mr("P"), mplain(" : "), mr("D"), mplain("["), mr("c"), mplain("] = ASK")],
        ),
        (
            [mplain("ALLOW")],
            [mplain("otherwise")],
        ),
    ]
    return build_omath([mr("d"), mplain(" = "), mcases(rows)])


def eq_D_cases():
    rows = [
        (
            [mplain("DENY")],
            [mplain("if "), mr("r"), mplain(".allow = false ∨ restrictions("), mr("r"), mplain(","), mr("τ"), mplain(") violated")],
        ),
        (
            [mr("r"), mplain(".mode")],
            [mplain("if "), mr("r"), mplain(".allow = true ∧ restrictions("), mr("r"), mplain(","), mr("τ"), mplain(") satisfied")],
        ),
    ]
    return build_omath([mr("D"), mplain("["), mr("c"), mplain("] = "), mcases(rows)])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = Document(str(SRC))

    # Map: equation number -> builder. For 5-6 and 7-9 use cases on first and clear others.
    builders = {
        1: eq1,
        2: eq2,
        3: eq3,
        4: eq4,
        5: eq_D_cases,  # combined cases for D[c]
        10: eq10,
        11: eq11,
        12: eq12,
        13: eq13,
        14: eq14,
        15: eq15,
        16: eq16,
    }

    # Find paragraphs
    eq_paras: dict[int, any] = {}
    for p in doc.paragraphs:
        t = p.text.strip().replace("\u2003", "")
        mobj = re.search(r"\((\d+)\)\s*$", t)
        if mobj and (
            "=" in t
            or t.startswith("if P")
            or t.startswith("path")
            or t.startswith("D[")
            or t.startswith("d =")
            or t.startswith("P =")
            or t.startswith("ASR")
            or t.startswith("Block")
            or t.startswith("TSR")
            or t.startswith("TP")
            or t.startswith("FN")
            or t.startswith("F1")
        ):
            eq_paras[int(mobj.group(1))] = p

    print("Found equations:", sorted(eq_paras))

    # Replace 1-4, 10-16 normally; 5 becomes D cases numbered (5); remove 6 content by merging note
    # 7 becomes d cases numbered (7); clear 8 and 9 into empty/deleted explanatory merge

    for num, builder in builders.items():
        if num not in eq_paras:
            print("MISSING para for", num)
            continue
        set_equation_paragraph(eq_paras[num], builder(), num)
        print("Wrote OMML eq", num)

    # Eq 6: replace with short pointer text (since folded into 5), keep number for refs
    if 6 in eq_paras:
        set_equation_paragraph(eq_paras[6], eq6(), 6)
        # Actually user wants proper form - keep both 5 and 6 as cases-style single lines OR
        # replace 5 with cases and delete 6's math by making 6 a note.
        # Better: eq5 = D cases as (5), and remove equation 6 paragraph content to a prose note.
        p6 = eq_paras[6]
        for child in list(p6._p):
            if child.tag != qn("w:pPr"):
                p6._p.remove(child)
        # leave a short italic note instead of duplicate
        r = w("r")
        rpr = w("rPr")
        i = w("i")
        rpr.append(i)
        rfonts = w("rFonts")
        rfonts.set(qn("w:ascii"), "Times New Roman")
        rfonts.set(qn("w:hAnsi"), "Times New Roman")
        rpr.append(rfonts)
        r.append(rpr)
        t = w("t")
        t.text = (
            "Equation (5) is the closed form of Algorithm 2, steps 6–8 "
            "(DENY on disallow/violation; otherwise D[c] = r.mode)."
        )
        r.append(t)
        p6._p.append(r)
        # center
        pPr = p6._p.find(qn("w:pPr"))
        if pPr is None:
            pPr = w("pPr")
            p6._p.insert(0, pPr)
        jc = pPr.find(qn("w:jc"))
        if jc is None:
            jc = w("jc")
            pPr.append(jc)
        jc.set(qn("w:val"), "both")
        print("Folded eq6 into note under (5)")

    # Replace 7 with cases; fold 8 and 9
    if 7 in eq_paras:
        set_equation_paragraph(eq_paras[7], eq_d_cases(), 7)
        print("Wrote OMML cases eq 7")
    for num in (8, 9):
        if num not in eq_paras:
            continue
        p = eq_paras[num]
        for child in list(p._p):
            if child.tag != qn("w:pPr"):
                p._p.remove(child)
        r = w("r")
        rpr = w("rPr")
        i = w("i")
        rpr.append(i)
        rfonts = w("rFonts")
        rfonts.set(qn("w:ascii"), "Times New Roman")
        rfonts.set(qn("w:hAnsi"), "Times New Roman")
        rpr.append(rfonts)
        r.append(rpr)
        t = w("t")
        if num == 8:
            t.text = (
                "Equation (7) is the closed form of Algorithm 2, steps 11–14 "
                "(priority DENY ≻ ASK ≻ ALLOW), matching PermissionChecker._aggregate()."
            )
        else:
            t.text = (
                "If d = ASK and no ask-handler is configured, the proxy applies d ← DENY (fail-closed), "
                "then appends the audit record (τ, P, h, D, d)."
            )
        r.append(t)
        p._p.append(r)
        print("Folded eq", num, "into note")

    # Update intro numbering text: (1)–(9) still ok; mention (7) as cases
    doc.save(str(SRC))
    print("Saved", SRC)

    # verify OMML present
    d2 = Document(str(SRC))
    omml = 0
    for p in d2.paragraphs:
        xml = p._p.xml
        if "oMath" in xml:
            omml += 1
    print("Paragraphs containing oMath:", omml)


if __name__ == "__main__":
    main()
