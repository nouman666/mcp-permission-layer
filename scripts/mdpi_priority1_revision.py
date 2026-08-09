"""
MDPI Computers Priority-1 manuscript revision on Style_Edited.docx.
Focus: novelty positioning, claim honesty, abstract length, section labels, back matter.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.text.paragraph import Paragraph

SRC = Path(r"c:\Users\as\Desktop\bodmas\IEEE_MCP_Paper_Style_Edited.docx")


def style_run(run, *, bold=False, italic=False, size=10):
    run.bold = bold
    run.italic = italic
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)


def set_para_text(p: Paragraph, text: str, *, bold=False, size=10, center=False, first_indent=True):
    for r in p.runs:
        r.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    if first_indent and not center and not bold:
        pf.first_line_indent = Inches(0.25)
    else:
        pf.first_line_indent = Inches(0)
    if p.runs:
        p.runs[0].text = text
        style_run(p.runs[0], bold=bold, size=size)
        for r in p.runs[1:]:
            r.text = ""
    else:
        r = p.add_run(text)
        style_run(r, bold=bold, size=size)


def insert_after(paragraph: Paragraph) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    return Paragraph(new_p, paragraph._parent)


def find_startswith(doc: Document, prefix: str) -> Paragraph:
    for p in doc.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    raise ValueError(prefix)


def replace_in_all(doc: Document, mapping: list[tuple[str, str]]):
    for p in doc.paragraphs:
        t = p.text
        newt = t
        for a, b in mapping:
            newt = newt.replace(a, b)
        if newt != t and p.runs:
            # preserve rough formatting by dumping into first run
            for r in p.runs:
                r.text = ""
            p.runs[0].text = newt
            style_run(p.runs[0], bold=bool(p.runs[0].bold), size=10 if not p.runs[0].font.size else int(p.runs[0].font.size.pt))


ABSTRACT = (
    "Tool poisoning can induce Model Context Protocol (MCP) agents to perform harmful host actions "
    "through manipulated tool metadata or arguments. Rather than detecting poisoned descriptions, "
    "this paper presents a client-side runtime least-privilege enforcement layer that intercepts each "
    "tool call, infers six behavioural permission categories from names and arguments, and applies "
    "default-deny YAML profiles with ALLOW, DENY, or ASK outcomes without modifying MCP clients or "
    "servers. Under a limited-network profile, pilot design-set ASR is 1.64% with TSR 76.92%, "
    "template-stress ASR is 2.92% with TSR 78.74%, and organic/live hold-outs show observed ASR 0% "
    "with small-n upper bounds reported in the Results. The layer outperforms the evaluated "
    "name-allowlist, definition-scan, and lightweight gateway baselines at sub-millisecond "
    "decision-path latency. The contribution is argument-aware runtime authorization of "
    "poisoning-induced tool actions, not ML-based poisoning detection."
)


NOVELTY_HEADING = "E. Differentiation from AgentBound and Runtime MCP Governance"


NOVELTY_P1 = (
    "Because runtime MCP access control is an active research area, the contribution of this work "
    "must be stated relative to AgentBound [4] and to Microsoft’s Agent Governance Toolkit (AGT) "
    "control-plane design [15], rather than only relative to static allowlists. AgentBound is a "
    "server-centric access-control framework: MCP servers declare resource needs in an AgentManifest, "
    "and an enforcement engine (AgentBox) constrains server execution to those declared capabilities "
    "without modifying server source [4]. Its primary boundary is therefore the MCP server’s "
    "execution sandbox and declared OS-level capability set. In contrast, the present layer is a "
    "client-side mediation proxy that intercepts every tools/call before upstream execution, infers "
    "categories from the concrete call (name and arguments), and decides ALLOW/DENY/ASK under "
    "operator YAML profiles. The two systems are complementary: AgentBound can limit what a server "
    "process may touch, whereas this work authorises what an already-connected client is allowed to "
    "request on each call."
)

NOVELTY_P2 = (
    "Microsoft AGT likewise sits between an MCP client and tool servers and evaluates per-call "
    "policies with allow/deny/approval outcomes, audit logging, and sub-millisecond policy evaluation "
    "in internal microbenchmarks [15]. AGT is a broader governance toolkit: it additionally emphasises "
    "tool-definition scanning before tools enter model context, response inspection, cryptographic "
    "agent identity, and multi-framework adapters. The present work is narrower and more specialised. "
    "It contributes (i) a compact six-category behavioural permission taxonomy derived from observed "
    "poisoning side effects, (ii) a three-layer inference procedure with sensitive-path elevation and "
    "fail-closed unknown handling, (iii) explicit security–utility profiles with ablation evidence, "
    "and (iv) a staged evaluation protocol that separates design-set, template-stress, and hold-out/"
    "live evidence. We do not claim to outperform AGT or AgentBound under a shared harness; those "
    "systems are related runtime-governance baselines discussed qualitatively because a fair "
    "head-to-head deployment was outside the present experimental scope."
)

NOVELTY_P3 = (
    "Accordingly, the novelty claim is not “the first runtime MCP gate,” but a reproducible "
    "argument-aware least-privilege mediation layer specialised to poisoning-induced tool actions, "
    "with measured utility trade-offs and component ablations. Table 1 summarises this positioning."
)


RQ_BLOCK = (
    "Research Questions. The evaluation is organised around four questions. "
    "RQ1: Can argument-aware runtime permission enforcement reduce malicious MCP tool-call success "
    "while preserving legitimate task utility? "
    "RQ2: Which inference components contribute most to security and utility? "
    "RQ3: Does the frozen enforcement logic remain effective under remapped-name, organic, adaptive, "
    "and live MCP conditions? "
    "RQ4: What security–utility trade-offs are induced by alternative policy profiles? "
    "RQ1 is addressed by Tables 4–8, RQ2 by the ablation study, RQ3 by Phase-C hold-outs, and RQ4 by "
    "the profile comparison and trade-off analysis."
)


BACK_MATTER = [
    (
        "Author Contributions",
        "Conceptualization, M.N. and S.I.H.; methodology, M.N.; software, M.N.; validation, M.N., S.I.H. and R.U.; "
        "formal analysis, M.N.; investigation, M.N.; writing—original draft preparation, M.N.; "
        "writing—review and editing, S.I.H. and R.U.; supervision, R.U. "
        "[CONFIRM CRediT roles with all co-authors before submission.]",
    ),
    (
        "Funding",
        "This research received no external funding. "
        "[Replace if a grant or institutional funder applies.]",
    ),
    (
        "Data Availability Statement",
        "The prototype code, evaluation scripts, configuration files, and study datasets supporting the "
        "reported results are provided in the accompanying artifact package "
        "(mcp_permission_layer). A public repository URL/DOI will be inserted here for review and "
        "publication. During peer review, the artifact can also be supplied as supplementary material "
        "upon request. [INSERT PUBLIC REPO URL / DOI.]",
    ),
    (
        "Acknowledgments",
        "The authors thank colleagues who provided feedback on earlier drafts of this manuscript.",
    ),
    (
        "Conflicts of Interest",
        "The authors declare no conflicts of interest. "
        "[Confirm with all co-authors before submission.]",
    ),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = Document(str(SRC))

    # Guard against double-run of novelty section
    already = any(p.text.strip().startswith("E. Differentiation from AgentBound") for p in doc.paragraphs)
    if already:
        print("Novelty section already present; continuing with other edits.")

    # 1) Title
    set_para_text(
        doc.paragraphs[0],
        "Argument-Aware Runtime Least-Privilege Enforcement Against "
        "Tool-Poisoning-Induced Actions in MCP-Based Agentic Systems",
        bold=True,
        size=16,
        center=True,
        first_indent=False,
    )

    # 2) Abstract (single paragraph, ~190 words)
    # Keep heading; merge body into para 5; clear para 6 if second abstract para
    set_para_text(doc.paragraphs[5], ABSTRACT, size=10)
    if doc.paragraphs[6].text.strip() and not doc.paragraphs[6].text.startswith("Index"):
        # second abstract paragraph -> clear into empty or keep index
        if "Index Terms" not in doc.paragraphs[6].text and "Keywords" not in doc.paragraphs[6].text:
            set_para_text(doc.paragraphs[6], "", first_indent=False)
    print("Abstract words:", len(ABSTRACT.split()))

    # 3) Keywords
    for p in doc.paragraphs:
        if p.text.strip().startswith("Index Terms") or p.text.strip().startswith("Keywords"):
            set_para_text(
                p,
                "Keywords: Model Context Protocol; tool poisoning; agentic systems; runtime enforcement; "
                "least privilege; access control; LLM security; MCP proxy",
                first_indent=False,
            )
            break

    # 4) Claim softenings across document
    replace_in_all(
        doc,
        [
            (
                "mitigating tool poisoning attacks",
                "mitigating tool-poisoning-induced harmful tool actions",
            ),
            (
                "for MCP tool poisoning",
                "for tool-poisoning-induced MCP tool actions",
            ),
            (
                "Despite this evidence, popular clients such as Cursor, Claude Desktop, Cline, and Continue still center their UX on approval dialogs and static allowlists",
                "Despite this evidence, current MCP client documentation commonly exposes user approval and tool/server configuration controls; these controls do not by themselves establish a uniform argument-aware least-privilege enforcement boundary",
            ),
            (
                "it outperforms name-allowlist, definition-scan, and gateway-class baselines",
                "it outperforms the evaluated name-allowlist, definition-scan, and lightweight gateway baselines",
            ),
            (
                "outperforms name-allowlist, definition-scan, and gateway-class baselines",
                "outperforms the evaluated name-allowlist, definition-scan, and lightweight gateway baselines",
            ),
            (
                "denied calls do not reach potentially malicious or over-privileged servers",
                "when traffic is correctly routed through the proxy, denied calls are prevented from reaching the upstream server",
            ),
            (
                "denied calls never reach potentially malicious or over-privileged servers",
                "when traffic is correctly routed through the proxy, denied calls are prevented from reaching the upstream server",
            ),
            (
                "an 87-case pilot used only for design freeze",
                "an 87-case design/development set used only for design freeze",
            ),
            (
                "pilot used only for design freeze",
                "pilot design/development set used only for design freeze",
            ),
            (
                "On pilot_87",
                "On the pilot design/development set (pilot_87)",
            ),
            (
                "B1–B3 are specified for follow-on",
                "B1–B3 are representative lightweight baselines rather than claimed state-of-the-art systems, and are specified for follow-on",
            ),
        ],
    )

    # 5) Heading renames toward MDPI
    heading_map = {
        "I. Introduction": "1. Introduction",
        "II. Related Work and Research Positioning": "2. Related Work and Research Positioning",
        "III. System Design": "3. Materials and Methods",
        "IV. Implementation": "3.5. Implementation",
        "V. Evaluation Methodology and Experimental Protocol": "3.6. Experimental Protocol and Metrics",
        "VI. Experimental Results": "4. Results",
        "VII. Discussion": "5. Discussion",
        "VIII. Conclusion": "6. Conclusions",
        "References": "References",
    }
    for p in doc.paragraphs:
        t = p.text.strip()
        if t in heading_map:
            set_para_text(p, heading_map[t], bold=True, size=12, first_indent=False)

    # Subheading renames under methods (exact unique titles only)
    sub_map = {
        "A. Threat Model and Assumptions": "3.1. Threat Model and Assumptions",
        "B. Permission Taxonomy Derivation": "3.2. Permission Taxonomy Derivation",
        "C. Policy Profiles": "3.3. Policy Profiles",
        "D. Runtime Architecture and Inference": "3.4. Runtime Architecture and Inference",
        "E. Formal Decision Algorithms": "3.4.1. Formal Decision Algorithms",
        "A. Prototype Organisation": "3.5.1. Prototype Organisation",
        "B. Deployment Model": "3.5.2. Deployment Model",
        "A. Evaluation Phases and Dataset Independence": "3.6.1. Evaluation Phases and Dataset Independence",
        "B. Metrics and Evaluation Protocol": "3.6.2. Metrics and Evaluation Protocol",
    }
    for p in doc.paragraphs:
        t = p.text.strip()
        if t in sub_map:
            set_para_text(p, sub_map[t], bold=True, size=11, first_indent=False)

    # Results/Discussion lettered subsections -> 4.x / 5.x
    results_map = {
        "A. Phase A/B: Pilot and Template Stress": "4.1. Pilot Design-Set and Template Stress",
        "B. Baseline Comparison": "4.2. Baseline Comparison",
        "C. Phase C: Hold-Out and Organic Validity": "4.3. Remapped and Organic Hold-Outs",
        "D. Phase C: Live MCP Deployment": "4.4. Live MCP Evaluation",
        "E. Phase C: Adaptive and Multi-Step Attacks": "4.5. Adaptive and Multi-Step Evaluation",
        "F. Component Ablation": "4.6. Component Ablation",
        "G. Statistical Analysis, Latency, and Human-in-the-Loop ASK": "4.7. Latency and Human-in-the-Loop ASK",
        "A. Research Identity and Security–Utility Trade-off": "5.1. Security–Utility Trade-Off and Research Identity",
        "B. Residual Risk, Unknown Tools, and Misconfiguration": "5.2. Residual Risk, Unknown Tools, and Misconfiguration",
        "C. Deployment Implications": "5.3. Deployment Implications",
        "D. Limitations and Future Work": "5.4. Limitations and Future Work",
    }
    for p in doc.paragraphs:
        t = p.text.strip()
        if t in results_map:
            set_para_text(p, results_map[t], bold=True, size=11, first_indent=False)

    # 6) Insert novelty subsection after Research Gap heading's following content?
    # Insert after "D. Research Gap and Positioning" paragraph block - find that heading then after next 1-2 paras before III/Materials
    if not already:
        gap = find_startswith(doc, "D. Research Gap")
        # find last paragraph before Materials/System Design
        insert_point = gap
        for p in doc.paragraphs:
            if p.text.strip().startswith("3. Materials and Methods") or p.text.strip().startswith("III. System Design"):
                break
            # keep advancing while we are still in section II
            if p._p.getparent() is not None:
                # use document order: after gap until Materials
                pass
        # Walk paragraphs after gap until Materials
        started = False
        last = gap
        for p in doc.paragraphs:
            if p.text.strip().startswith("D. Research Gap"):
                started = True
                last = p
                continue
            if started:
                if p.text.strip().startswith("3. Materials") or p.text.strip().startswith("III."):
                    break
                if p.text.strip():
                    last = p
        h = insert_after(last)
        set_para_text(h, NOVELTY_HEADING, bold=True, size=11, first_indent=False)
        p1 = insert_after(h)
        set_para_text(p1, NOVELTY_P1)
        p2 = insert_after(p1)
        set_para_text(p2, NOVELTY_P2)
        p3 = insert_after(p2)
        set_para_text(p3, NOVELTY_P3)
        print("Inserted novelty subsection")

    # 7) Insert RQs after Contributions paragraph
    contrib = None
    for p in doc.paragraphs:
        if p.text.strip().startswith("Contributions."):
            contrib = p
            break
    if contrib is not None and "Research Questions." not in "\n".join(x.text for x in doc.paragraphs):
        rq = insert_after(contrib)
        set_para_text(rq, RQ_BLOCK)
        print("Inserted RQs")

    # 8) Upgrade Table 1 rows for AgentBound / Microsoft
    if doc.tables:
        t0 = doc.tables[0]
        # Expand header if still old schema
        headers = [c.text.strip() for c in t0.rows[0].cells]
        # Update AgentBound and Gateway rows text in existing columns
        for row in t0.rows[1:]:
            work = row.cells[0].text.strip()
            if work.startswith("AgentBound"):
                row.cells[1].text = "Server manifest + sandbox enforcement"
                row.cells[2].text = "No (server-side)"
                row.cells[3].text = "Server capability perms"
                row.cells[4].text = "No server source change"
                row.cells[5].text = "Limited"
            if "Gateway" in work or "[15]" in work:
                row.cells[0].text = "Microsoft AGT [15]"
                row.cells[1].text = "Client–server control plane"
                row.cells[2].text = "Yes (mediation)"
                row.cells[3].text = "Policy + def. scan (broad)"
                row.cells[4].text = "Adapter/config"
                row.cells[5].text = "Internal reports"
            if work.startswith("This work"):
                row.cells[1].text = "Arg-aware least-privilege mediation"
                row.cells[2].text = "Yes"
                row.cells[3].text = "Yes (6-cat + paths/domains)"
                row.cells[4].text = "Yes (config only)"
                row.cells[5].text = "Yes (ASR+TSR+ablation)"
        # Add gateway row if Microsoft replaced gateway - add a short firewall row at end if needed
        print("Updated Table 1 positioning rows")

    # 9) Non-dominated definition near trade-off language
    for p in doc.paragraphs:
        if "non-dominated" in p.text and "ASR(A)" not in p.text:
            extra = (
                " Formally, profile A dominates B if ASR(A) ≤ ASR(B) and TSR(A) ≥ TSR(B), with at least "
                "one inequality strict; limited-network is non-dominated among the measured profiles when "
                "neither read-only, no-code-exec, nor approval-gated improves both axes simultaneously."
            )
            if "Formally, profile A dominates" not in p.text:
                set_para_text(p, p.text.rstrip() + extra)
                print("Added non-dominated definition")
                break

    # 10) Baseline wording in baseline section
    for p in doc.paragraphs:
        if p.text.strip().startswith("4.2. Baseline") or p.text.strip().startswith("B. Baseline"):
            # next non-empty para
            pass
    for i, p in enumerate(doc.paragraphs):
        if "B0" in p.text and "B1" in p.text and "static allowlist" in p.text.lower():
            if "representative lightweight" not in p.text:
                set_para_text(
                    p,
                    p.text.rstrip()
                    + " Baselines B1–B3 are representative lightweight controls used to isolate the value of "
                    "argument-aware category inference and restriction checks; they are not claimed to be "
                    "complete reimplementations of AgentBound or Microsoft AGT.",
                )
                print("Strengthened baseline caveat")
            break

    # 11) Soften live generalization if present
    replace_in_all(
        doc,
        [
            (
                "validates effectiveness in real-world deployments",
                "demonstrates feasibility under live MCP mediation",
            ),
            (
                "real-world MCP environments",
                "controlled live MCP deployments in our testbed",
            ),
            (
                "ASR was zero",
                "no successful malicious calls were observed (ASR 0%)",
            ),
            (
                "ASR is 0%",
                "observed ASR is 0%",
            ),
            (
                "ASR of 0%",
                "observed ASR of 0%",
            ),
            (
                "ASK study",
                "exploratory author-as-user ASK study",
            ),
        ],
    )

    # 12) Back matter before References
    if "Author Contributions" not in "\n".join(p.text for p in doc.paragraphs):
        prev = None
        for i, p in enumerate(doc.paragraphs):
            if p.text.strip() == "References":
                prev = doc.paragraphs[i - 1]
                break
        if prev is None:
            raise RuntimeError("References heading not found")
        cur = prev
        for title, body in BACK_MATTER:
            h = insert_after(cur)
            set_para_text(h, title, bold=True, size=11, first_indent=False)
            b = insert_after(h)
            set_para_text(b, body)
            cur = b
        print("Inserted MDPI back matter")

    # 13) Conclusion soften tool poisoning phrasing
    for p in doc.paragraphs:
        if p.text.startswith("This paper presented a client-side"):
            set_para_text(
                p,
                p.text.replace(
                    "for MCP tool poisoning",
                    "for mitigating tool-poisoning-induced harmful MCP tool actions",
                ).replace(
                    "MCP tool poisoning. The proposed layer",
                    "tool-poisoning-induced MCP tool actions. The proposed layer",
                ),
            )
            break

    doc.save(str(SRC))
    print("Saved", SRC)

    # verify
    d2 = Document(str(SRC))
    text = "\n".join(p.text for p in d2.paragraphs)
    checks = [
        "Argument-Aware Runtime Least-Privilege",
        "Keywords:",
        "Differentiation from AgentBound",
        "Research Questions.",
        "3. Materials and Methods",
        "4. Results",
        "5. Discussion",
        "6. Conclusions",
        "Author Contributions",
        "Data Availability Statement",
        "Conflicts of Interest",
        "evaluated name-allowlist",
        "design/development set",
        "Microsoft AGT",
    ]
    for c in checks:
        print(("OK" if c in text else "MISSING"), c)
    # abstract word count
    for p in d2.paragraphs:
        if p.text.startswith("Tool poisoning can induce") or p.text.startswith("Tool poisoning manipulates"):
            print("Abstract words now:", len(p.text.split()))
            break


if __name__ == "__main__":
    main()
