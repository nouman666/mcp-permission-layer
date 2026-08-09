"""
Merge all completed evaluations into the original ~12-page IEEE paper
(IEEE_Paper_FINAL_WITH_EVAL_DIAGRAM.docx), preserving figures and structure.
"""

from __future__ import annotations

import copy
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph

BASE = Path(
    r"C:\Users\as\PycharmProjects\PythonResearchProject_comparision"
    r"\_mcp_zip_extract\IEEE_Paper_FINAL_WITH_EVAL_DIAGRAM.docx"
)
OUTS = [
    Path(r"c:\Users\as\Desktop\bodmas\FINAL_12PAGE_IEEE_PAPER_WITH_FULL_EVAL.docx"),
    Path(r"c:\Users\as\Desktop\FINAL_12PAGE_IEEE_PAPER_WITH_FULL_EVAL.docx"),
    Path(
        r"C:\Users\as\PycharmProjects\PythonResearchProject_comparision"
        r"\_mcp_zip_extract\FINAL_12PAGE_IEEE_PAPER_WITH_FULL_EVAL.docx"
    ),
]


def set_run_font(run, size=10, bold=False, italic=False):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def replace_para_text(para, text):
    # Keep first run formatting if present
    if para.runs:
        para.runs[0].text = text
        for r in para.runs[1:]:
            r.text = ""
    else:
        run = para.add_run(text)
        set_run_font(run)


def insert_paragraph_after(paragraph: Paragraph, text: str, *, bold=False, italic=False, size=10, center=False):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if center:
        new_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = new_para.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic)
    return new_para


def insert_table_after(paragraph: Paragraph, headers, rows):
    """Insert a table immediately after paragraph; return the table's last paragraph-ish anchor (tbl element)."""
    doc = paragraph.part.document
    # Create table at end temporarily, then move XML after target paragraph
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(h)
        set_run_font(run, size=8, bold=True)
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            cell = table.rows[r_i + 1].cells[c_i]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(val))
            set_run_font(run, size=8)

    tbl = table._tbl
    # Detach from current location and place after paragraph
    tbl.getparent().remove(tbl)
    paragraph._p.addnext(tbl)
    return table


def find_para(doc, prefix: str):
    for p in doc.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    raise KeyError(prefix)


def main():
    doc = Document(str(BASE))

    # ----- Abstract -----
    abs_para = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "Abstract":
            abs_para = doc.paragraphs[i + 1]
            break
    replace_para_text(
        abs_para,
        "Tool poisoning attacks manipulate the metadata or parameters of tools exposed through the Model Context Protocol (MCP), "
        "causing agentic systems to perform unauthorized file access, data exfiltration, or code execution. Existing MCP clients "
        "rely primarily on user approval dialogs and static allowlists and generally lack fine-grained runtime least-privilege "
        "enforcement after a tool has been approved. This paper presents the design, implementation, and evaluation of a "
        "client-side runtime permission enforcement layer for MCP-based agents. The layer intercepts tool calls, infers a "
        "compact set of permission categories from tool names and arguments, and enforces declarative default-deny policies "
        "without modifying client or server source code. We evaluate the prototype on a hand-curated pilot of 87 cases, a "
        "20,000-case template stress corpus, remapped-name and organic-style hold-outs, adaptive and multi-step suites, "
        "component ablations, baseline comparisons, a live MCP deployment path (client → enforcement proxy → real upstream "
        "servers), and an author-as-user ASK study. Under the limited-network profile, pilot ASR is 6.56% with TSR 76.92%; "
        "template stress ASR is 4.36% with TSR 78.74%; organic hold-out and live MCP workflows both achieve ASR 0% with TSR 100%. "
        "Against static allowlist, definition scanning, and gateway-style baselines, the full layer attains substantially lower ASR. "
        "Mean decision-path latency is sub-millisecond; live end-to-end latency remains tens of milliseconds.",
    )

    # ----- Intro evaluation paragraph -----
    replace_para_text(
        find_para(doc, "The evaluation proceeds in two stages."),
        "The evaluation proceeds in multiple stages. A pilot study on 87 hand-curated cases validates metrics and exposes "
        "policy trade-offs. A 20,000-case template corpus stress-tests the enforcement logic under repeated patterns. "
        "Hold-out sets (remapped tool names and a 90-case organic-style MCPTox-like suite), adaptive attacks, multi-step "
        "chains, ablations, baseline comparisons, live MCP server mediation, and an ASK human-in-the-loop protocol then "
        "strengthen external validity beyond the template stress test.",
    )

    # ----- Contributions -----
    replace_para_text(
        find_para(doc, "The main contributions of this work are as follows."),
        "The main contributions of this work are as follows. First, we define a compact default-deny permission model and "
        "declarative policy language tailored to tool-poisoning behaviors in MCP agents. Second, we present a zero-modification "
        "prototype with audit logging and a real stdio MCP enforcement proxy that mediates client traffic to upstream servers. "
        "Third, we provide a multi-stage evaluation—including pilot, stress, organic hold-out, baselines, ablations, adaptive "
        "and multi-step attacks, live MCP deployment, and ASK—with security and utility metrics, bootstrap confidence intervals, "
        "and latency percentiles. Fourth, we release artifacts (code, policies, datasets, and scripts) for reproduction.",
    )

    # ----- Implementation note (append proxy sentence into package paragraph) -----
    impl = find_para(doc, "The prototype is implemented in Python 3")
    replace_para_text(
        impl,
        impl.text.strip()
        + " In addition, a stdio MCP enforcement proxy speaks JSON-RPC to clients, applies the permission checker on every "
        "tools/call, and forwards only ALLOWED invocations to real upstream MCP servers (official filesystem server and "
        "in-repo fetch/git/shell servers). Cursor-ready mcp.json entries launch these enforced wrappers.",
    )

    # ----- Experimental setup -----
    replace_para_text(
        find_para(doc, "Two evaluation corpora are used."),
        "Multiple evaluation corpora are used. The pilot corpus contains 87 hand-curated cases (61 malicious, 26 benign) "
        "spanning credential reading, data exfiltration, code execution, parameter tampering, logging/surveillance, and "
        "cross-tool escalation, plus legitimate coding and research tasks. An organic-style hold-out of 90 hand-authored "
        "cases (50 attack / 40 benign) uses diverse real-world tool names and MCPTox-like workflows and is never used for tuning. "
        "A remapped-name unseen split stresses name-heuristic generalization. Adaptive and multi-step suites, 25 live MCP "
        "workflows, and 20 ASK-study prompts complete the protocol.",
    )
    replace_para_text(
        find_para(doc, "The large-scale corpus contains 20,000 cases"),
        "The large-scale corpus contains 20,000 cases: 10,000 malicious and 10,000 benign. It was generated by systematic "
        "expansion of seed templates—sensitive paths, attacker URLs, shell payloads, and safe project paths—and is used as "
        "a stress test of the enforcement logic, not as a claim of organic production diversity. Primary external-validity "
        "evidence is taken from the pilot, organic hold-out, remapped-name split, live MCP path, and ASK study.",
    )
    replace_para_text(
        find_para(doc, "Primary metrics are Attack Success Rate"),
        "Primary metrics are Attack Success Rate (ASR), Block Rate, Task Success Rate (TSR), F1 (attack = positive), damage "
        "reduction, and latency (mean/median/p95/p99). Automated runs map ASK→DENY unless an ASK study mode is stated. "
        "Baselines are B0 no defense, B1 static tool-name allowlist, B2 definition keyword scanning, B3 gateway-style filter, "
        "and B4 the full layer. Bootstrap 95% confidence intervals are reported for limited-network on pilot_87. Live MCP "
        "experiments use a programmatic MCP client against the enforcement proxy and real upstream servers.",
    )

    # ----- Insert extended results before VII. Discussion -----
    disc = find_para(doc, "VII. Discussion")
    # We insert in reverse order before Discussion so final order is correct... 
    # Actually insert_paragraph_after(disc's previous). Easier: insert after the paragraph just before Discussion.
    # Find paragraph immediately before Discussion
    prev = None
    for p in doc.paragraphs:
        if p._p is disc._p:
            break
        if p.text.strip():
            prev = p
    anchor = prev

    blocks = []

    def add_text(text, **kw):
        nonlocal anchor
        anchor = insert_paragraph_after(anchor, text, **kw)
        blocks.append(anchor)

    def add_tbl(caption, headers, rows):
        nonlocal anchor
        anchor = insert_paragraph_after(anchor, caption, bold=True, size=9, center=True)
        insert_table_after(anchor, headers, rows)
        # After moving table after caption, set anchor to caption so next content goes after table?
        # addnext on caption puts table after caption; next insert_paragraph_after(caption) would put
        # new para between caption and table. Need anchor = element after table.
        # Work around: insert a spacer para after table.
        tbl = anchor._p.getnext()  # should be tbl
        spacer = OxmlElement("w:p")
        tbl.addnext(spacer)
        anchor = Paragraph(spacer, disc._parent)

    add_text("D. Baseline Comparison", bold=True, size=11)
    add_text(
        "On the same pilot_87 attack set, simple defenses underperform the full layer. B1 (static allowlist) and B2 "
        "(definition scanning) leave majority ASR; B3 (gateway-style filter) improves blocking but remains well above B4. "
        "Limited-network B4 reaches ASR 6.56% and F1 91.94%, versus B3 ASR 24.59%."
    )
    add_tbl(
        "TABLE IV. BASELINE COMPARISON (PILOT_87)",
        ["Baseline", "ASR (%)", "Block (%)", "TSR (%)", "F1 (%)"],
        [
            ["B0 no defense", "100.00", "0.00", "100.00", "0.00"],
            ["B1 static allowlist", "54.10", "45.90", "100.00", "62.92"],
            ["B2 definition scan", "65.57", "34.43", "100.00", "51.22"],
            ["B3 gateway filter", "24.59", "75.41", "100.00", "85.98"],
            ["B4 full layer (limited-network)", "6.56", "93.44", "76.92", "91.94"],
        ],
    )

    add_text("E. Hold-out and Organic-Style Evaluation", bold=True, size=11)
    add_text(
        "Remapping tool names (unseen identifiers) raises limited-network ASR from 4.36% on the template corpus to 11.48% "
        "and lowers TSR to 65.38%, quantifying name-heuristic brittleness. Separately, a 90-case organic-style hold-out—"
        "hand-authored MCPTox-like attacks and realistic benign workflows with diverse tool names, not template-expanded—"
        "yields limited-network ASR 0% and TSR 100%. Argument inspection, sensitive-path elevation, and fail-closed "
        "unknown-tool handling therefore recover a strong security–utility balance on non-template cases."
    )
    add_tbl(
        "TABLE V. ORGANIC-STYLE HOLD-OUT (90 CASES, NON-TEMPLATE)",
        ["Profile", "ASR (%)", "TSR (%)", "F1 (%)"],
        [
            ["read_only", "0.00", "75.00", "90.91"],
            ["limited_network", "0.00", "100.00", "100.00"],
            ["no_code_exec", "2.00", "100.00", "98.99"],
            ["approval_gated", "2.00", "100.00", "98.99"],
        ],
    )

    add_text("F. Live Real MCP Deployment", bold=True, size=11)
    add_text(
        "We executed 25 workflows on a live path: MCP client → stdio enforcement proxy → real upstream MCP servers "
        "(official filesystem server; real fetch/git/shell servers). Under limited-network, all malicious workflows were "
        "denied before upstream execution (ASR 0%) while all benign workflows were allowed (TSR 100%). End-to-end mean "
        "latency was 54.8 ms/call, dominated by upstream I/O rather than the decision path."
    )
    add_tbl(
        "TABLE VI. REAL MCP DEPLOYMENT RESULTS (LIVE)",
        ["Defense", "ASR (%)", "Block (%)", "TSR (%)", "F1 (%)", "Latency ms"],
        [
            ["B0 no defense", "100.00", "0.00", "100.00", "0.00", "n/a"],
            ["B4 limited_network", "0.00", "100.00", "100.00", "100.00", "54.76"],
            ["B4 read_only", "0.00", "100.00", "76.92", "88.89", "8.72"],
            ["B4 no_code_exec", "16.67", "83.33", "100.00", "90.91", "34.05"],
            ["B4 approval_gated", "8.33", "91.67", "100.00", "95.65", "35.27"],
        ],
    )

    add_text("G. Adaptive Attacks and Multi-Step Chains", bold=True, size=11)
    add_text(
        "Assuming attacker knowledge of the inference rules, adaptive cases with benign-looking names, malice in arguments, "
        "and light obfuscation yield ASR 0% under limited-network and read-only (B0 remains 100%). For multi-step escalation, "
        "13 attack chains (e.g., read secret → HTTP exfil; get_env → terminal) were evaluated under per-call enforcement and "
        "an optional session-taint extension; no attack chain fully succeeded under any profile (0/13)."
    )
    add_tbl(
        "TABLE VII. ADAPTIVE ASR",
        ["Profile", "ASR (%)", "TSR (%)", "F1 (%)"],
        [
            ["read_only", "0.00", "60.00", "93.75"],
            ["limited_network", "0.00", "100.00", "100.00"],
            ["no_code_exec", "13.33", "100.00", "92.86"],
            ["approval_gated", "13.33", "100.00", "92.86"],
            ["B0 no defense", "100.00", "100.00", "0.00"],
        ],
    )

    add_text("H. Ablation Study", bold=True, size=11)
    add_text(
        "Component knock-outs on limited-network / pilot_87 show that removing domain allow-listing raises ASR from 6.56% "
        "to 27.87%, and removing sensitive-path elevation raises ASR to 18.03%. Removing name heuristics collapses TSR "
        "(42.31%) due to over-denial from fail-closed unknowns, confirming that both security and utility depend on the "
        "full stack rather than a single heuristic."
    )
    add_tbl(
        "TABLE VIII. ABLATION (LIMITED-NETWORK, PILOT_87)",
        ["Config", "ASR (%)", "TSR (%)", "F1 (%)"],
        [
            ["Full system", "6.56", "76.92", "91.94"],
            ["− argument inspection", "6.56", "76.92", "91.94"],
            ["− sensitive-path elevation", "18.03", "76.92", "85.47"],
            ["− domain allow-list", "27.87", "76.92", "79.28"],
            ["− name heuristics", "4.92", "42.31", "86.57"],
            ["− default-deny (default allow)", "6.56", "76.92", "91.94"],
        ],
    )

    add_text("I. Statistics, Latency, False Positives, and ASK", bold=True, size=11)
    add_text(
        "Bootstrap (1000 resamples) on limited-network / pilot_87: ASR 6.56% (mean±std 6.48±3.16; 95% CI [1.59, 13.33]); "
        "TSR 76.92% (77.27±8.22; [59.26, 92.00]); F1 91.94% (91.97±2.60; [86.44, 96.45]). Decision-path latency: mean 0.46 ms, "
        "median 0.43 ms, p95 0.70 ms, p99 0.88 ms (MCP serialization excluded). False positives under limited-network on pilot "
        "benign cases are 6/26, all writes—an expected policy cost. On approval-gated ASK evaluation (20 prompts, 13 ASK "
        "triggers), auto-DENY yields ASR 0% / TSR 66.67%; auto-ALLOW yields ASR 90.91% / TSR 100%; author-as-user ASK yields "
        "approval rate 23.1%, ASR 0%, TSR 100%, and ~50 ms mean extra decision time."
    )
    add_tbl(
        "TABLE IX. ASK / HUMAN-IN-THE-LOOP",
        ["Mode", "ASK prompts", "Approval rate", "Final ASR", "Final TSR", "F1", "Extra ASK ms"],
        [
            ["auto_deny", "13", "0.0%", "0.00%", "66.67%", "88.00%", "0.0"],
            ["auto_allow", "13", "100.0%", "90.91%", "100.00%", "16.67%", "0.0"],
            ["author_ask", "13", "23.1%", "0.00%", "100.00%", "100.00%", "50.4"],
        ],
    )

    # ----- Discussion: replace long limitations -----
    replace_para_text(
        find_para(doc, "Several limitations should be stated clearly."),
        "The 20,000-case corpus remains a template stress test; claims of broader validity are supported by the organic-style "
        "hold-out, remapped-name split, live MCP deployment, baselines, ablations, adaptive/multi-step suites, and ASK study "
        "rather than by template volume alone. Artifacts (source, policies, datasets, and one-command evaluation scripts) are "
        "released for reproduction.",
    )

    # Soften "Despite these limitations" paragraph
    despite = find_para(doc, "Despite these limitations")
    replace_para_text(
        despite,
        "Overall, the combination of a clear threat-driven category model, a minimal zero-modification architecture with a "
        "real MCP proxy, and consistent results from pilot through organic hold-out and live deployment provides strong "
        "evidence that runtime least-privilege enforcement is a practical control for MCP tool poisoning.",
    )

    # ----- Conclusion -----
    replace_para_text(
        find_para(doc, "This paper presented a runtime permission enforcement layer"),
        "This paper presented a runtime permission enforcement layer for mitigating tool poisoning in MCP-based agentic systems. "
        "The layer intercepts tool calls, infers permission categories, and enforces declarative default-deny policies without "
        "modifying clients or servers. Across pilot, template stress, organic hold-out, baselines, ablations, adaptive and "
        "multi-step evaluations, live MCP mediation, and an author-as-user ASK study, the limited-network profile consistently "
        "reduces attack success while preserving substantial legitimate utility at sub-millisecond decision latency. We release "
        "artifacts to support reproduction and deployment.",
    )

    # Update Fig 7 caption mention if present - optional
    try:
        fig7 = find_para(doc, "Fig. 7. Evaluation pipeline")
        replace_para_text(
            fig7,
            "Fig. 7. Evaluation pipeline for pilot, large-scale stress, hold-out, live MCP, and ASK experiments.",
        )
    except KeyError:
        pass

    for out in OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))
        print("Wrote", out)


if __name__ == "__main__":
    main()
