"""
Generate all paper diagrams as true vector SVG (+ high-DPI PNG for Word).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Polygon
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "svg"
PNG = ROOT / "figures" / "png"

# IEEE-friendly palette
C_BLUE = "#BDD7EE"
C_ORANGE = "#F8CBAD"
C_GREEN = "#C6EFCE"
C_YELLOW = "#FFE699"
C_TEAL = "#A9D08E"
C_PURPLE = "#D0A9E0"
C_RED = "#F4B183"
C_PINK = "#F8CBAD"
C_GREY = "#D9D9D9"
C_SALMON = "#F4CCCC"
EDGE = "#222222"


def _setup():
    OUT.mkdir(parents=True, exist_ok=True)
    PNG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.linewidth": 0.8,
            "svg.fonttype": "none",  # real text in SVG
        }
    )


def save(fig, name: str):
    svg_path = OUT / f"{name}.svg"
    png_path = PNG / f"{name}.png"
    fig.savefig(svg_path, format="svg", bbox_inches="tight", pad_inches=0.15)
    fig.savefig(png_path, format="png", dpi=220, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("Wrote", svg_path.name, "and", png_path.name)


def rounded(ax, xy, w, h, facecolor, text, fontsize=9, weight="bold", text_color="black"):
    x, y = xy
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2,
        edgecolor=EDGE,
        facecolor=facecolor,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color=text_color,
        wrap=True,
    )
    return box


def arrow(ax, p1, p2, color=EDGE, lw=1.4, style="-|>", connectionstyle="arc3"):
    ax.add_patch(
        FancyArrowPatch(
            p1,
            p2,
            arrowstyle=style,
            mutation_scale=12,
            linewidth=lw,
            color=color,
            connectionstyle=connectionstyle,
        )
    )


def color_legend(ax, items, x=0.25, y=0.12, cols=4, sw=0.28, sh=0.22, dx=2.85, dy=0.38, fontsize=7.2):
    """Draw a compact color key: items = [(facecolor, label), ...]."""
    ax.text(x, y + dy * ((len(items) - 1) // cols) + 0.32, "Color key", fontsize=8, fontweight="bold", ha="left")
    for i, (facecolor, label) in enumerate(items):
        r, c = divmod(i, cols)
        px = x + c * dx
        py = y + ((len(items) - 1) // cols - r) * dy
        box = FancyBboxPatch(
            (px, py),
            sw,
            sh,
            boxstyle="round,pad=0.01,rounding_size=0.04",
            linewidth=0.8,
            edgecolor=EDGE,
            facecolor=facecolor,
        )
        ax.add_patch(box)
        ax.text(px + sw + 0.08, py + sh / 2, label, ha="left", va="center", fontsize=fontsize)


def fig1_architecture():
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7.6)
    ax.axis("off")
    ax.set_title(
        "System Architecture: Runtime Permission Enforcement Layer",
        fontsize=13,
        fontweight="bold",
        pad=10,
    )

    # Top row
    rounded(ax, (0.3, 5.4), 2.4, 1.1, C_BLUE, "MCP Client\n(Cursor / Claude /\nCline / Continue)", 8)
    rounded(ax, (3.4, 5.4), 2.4, 1.1, C_ORANGE, "Enforcement\nProxy", 10)
    rounded(ax, (6.5, 5.4), 2.4, 1.1, C_GREEN, "Permission\nChecker", 10)
    rounded(ax, (9.5, 5.4), 2.2, 1.1, C_PURPLE, "MCP\nServer(s)", 10)

    # Mid / bottom
    rounded(ax, (3.4, 3.6), 2.4, 0.9, C_TEAL, "Policy Manager", 9)
    rounded(ax, (3.4, 2.1), 2.4, 0.9, C_GREY, "YAML Policy\nProfiles", 9)
    rounded(ax, (6.5, 3.2), 2.4, 1.0, C_YELLOW, "Category\nInference", 9)
    rounded(ax, (9.3, 3.2), 2.4, 1.0, C_SALMON, "Audit Logger", 9)
    rounded(ax, (9.3, 1.7), 2.4, 0.9, C_GREY, "JSONL Audit Log", 9)

    arrow(ax, (2.7, 5.95), (3.4, 5.95))
    ax.text(3.0, 6.15, "tool call", fontsize=8, ha="center")
    arrow(ax, (5.8, 6.1), (6.5, 6.1))
    arrow(ax, (6.5, 5.8), (5.8, 5.8))
    ax.text(6.15, 6.3, "evaluate", fontsize=8, ha="center")
    arrow(ax, (8.9, 5.95), (9.5, 5.95))
    ax.text(9.2, 6.15, "forward if\nALLOW", fontsize=7, ha="center")

    arrow(ax, (4.6, 5.4), (4.6, 4.5))
    arrow(ax, (4.6, 3.6), (4.6, 3.0))
    arrow(ax, (7.7, 5.4), (7.7, 4.2))
    arrow(ax, (5.8, 5.5), (9.3, 4.0), color="#C00000", connectionstyle="arc3,rad=-0.25")
    arrow(ax, (8.9, 3.7), (9.3, 3.7), color="#C00000")
    arrow(ax, (10.5, 3.2), (10.5, 2.6), color="#C00000")
    arrow(ax, (10.5, 2.6), (10.5, 3.2), color="#C00000")

    color_legend(
        ax,
        [
            (C_BLUE, "Client (entry)"),
            (C_ORANGE, "Enforcement proxy"),
            (C_GREEN, "Permission checker"),
            (C_PURPLE, "Upstream server"),
            (C_TEAL, "Policy manager"),
            (C_YELLOW, "Category inference"),
            (C_SALMON, "Audit logger"),
            (C_GREY, "Persistent store"),
            ("#C00000", "Red arrows = audit path"),
        ],
        x=0.3,
        y=0.15,
        cols=3,
        dx=3.8,
    )

    save(fig, "fig1_architecture")


def fig2_pipeline():
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 3.8)
    ax.axis("off")
    ax.set_title("Five-Stage Decision Pipeline", fontsize=13, fontweight="bold", pad=8)

    stages = [
        (0.3, C_BLUE, "1. Parse\nToolCall"),
        (3.0, C_YELLOW, "2. Infer\nCategories"),
        (5.7, C_TEAL, "3. Policy\nLookup"),
        (8.4, C_ORANGE, "4. Restriction\nCheck"),
        (11.1, C_GREEN, "5. Aggregate\nDeny>Ask>Allow"),
    ]
    for x, color, text in stages:
        rounded(ax, (x, 1.35), 2.3, 1.5, color, text, 9)
    for x in (2.6, 5.3, 8.0, 10.7):
        arrow(ax, (x, 2.1), (x + 0.4, 2.1))
    color_legend(
        ax,
        [
            (C_BLUE, "Parse input"),
            (C_YELLOW, "Infer categories"),
            (C_TEAL, "Policy lookup"),
            (C_ORANGE, "Restriction check"),
            (C_GREEN, "Aggregate decision"),
        ],
        x=0.3,
        y=0.2,
        cols=5,
        dx=2.7,
        fontsize=7,
    )
    save(fig, "fig2_pipeline")


def fig3_inference():
    fig, ax = plt.subplots(figsize=(9.5, 6.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8.4)
    ax.axis("off")
    ax.set_title("Category Inference: Three-Layer Design", fontsize=13, fontweight="bold", pad=8)

    boxes = [
        (6.2, C_BLUE, "Tool Call (name + arguments)"),
        (4.6, C_YELLOW, "Layer 1: Name Heuristics  →  fs.read / fs.write / code.exec / net.http / …"),
        (3.0, C_ORANGE, "Layer 2: Argument Inspection  →  paths, URLs, shell meta, env patterns"),
        (1.4, C_SALMON, "Layer 3: Sensitive Elevation  →  env.read + high_risk (fail-closed if empty)"),
    ]
    for y, color, text in boxes:
        rounded(ax, (0.6, y), 8.8, 1.2, color, text, 9)
    for y1, y2 in ((6.2, 5.8), (4.6, 4.2), (3.0, 2.6)):
        arrow(ax, (5.0, y1), (5.0, y2))
    color_legend(
        ax,
        [
            (C_BLUE, "Input tool call"),
            (C_YELLOW, "Layer 1 name heuristics"),
            (C_ORANGE, "Layer 2 argument inspection"),
            (C_SALMON, "Layer 3 sensitive elevation"),
        ],
        x=0.6,
        y=0.2,
        cols=2,
        dx=4.6,
    )
    save(fig, "fig3_inference")


def fig4_decision_flow():
    fig, ax = plt.subplots(figsize=(9.2, 11.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.9, 12)
    ax.axis("off")
    ax.set_title("Implementation: Tool-Call Decision Flow", fontsize=13, fontweight="bold", pad=4)
    ax.text(
        5,
        11.35,
        "Runs for every tool call  |  No client/server source change",
        ha="center",
        fontsize=9,
        style="italic",
        color="#444444",
    )

    steps = [
        (9.8, C_BLUE, "1. Client issues tool call (name + arguments)"),
        (8.7, C_ORANGE, "2. EnforcementProxy.handle_tool_call()"),
        (7.6, C_YELLOW, "3. InferCategories (3 layers)\nname + args + sensitive paths"),
        (6.4, C_TEAL, "4. Policy lookup per category\n(default-deny if missing)"),
        (5.2, C_PURPLE, "5. Restriction checks (paths / domains)"),
    ]
    for y, color, text in steps:
        rounded(ax, (1.8, y), 6.4, 0.95, color, text, 9)
    for y1, y2 in ((9.8, 9.65), (8.7, 8.55), (7.6, 7.35), (6.4, 6.15)):
        arrow(ax, (5.0, y1), (5.0, y2))

    # Diamond
    diamond = Polygon(
        [(5.0, 4.95), (6.7, 4.2), (5.0, 3.45), (3.3, 4.2)],
        closed=True,
        facecolor="#FCE4D6",
        edgecolor=EDGE,
        linewidth=1.2,
    )
    ax.add_patch(diamond)
    ax.text(5.0, 4.2, "Aggregate\nDeny > Ask > Allow?", ha="center", va="center", fontsize=8, fontweight="bold")
    arrow(ax, (5.0, 5.2), (5.0, 4.95))

    # Outcomes
    rounded(ax, (0.4, 2.0), 2.6, 1.15, "#F4CCCC", "DENY\nBlock call\nLog record", 8)
    rounded(ax, (3.7, 2.0), 2.6, 1.15, C_YELLOW, "ASK\nask_handler or\nfail-closed DENY", 8)
    rounded(ax, (7.0, 2.0), 2.6, 1.15, C_GREEN, "ALLOW\nForward to\nMCP Server", 8)
    arrow(ax, (3.6, 3.9), (1.7, 3.15), color="#C00000")
    arrow(ax, (5.0, 3.45), (5.0, 3.15), color="#BF8F00")
    arrow(ax, (6.4, 3.9), (8.3, 3.15), color="#548235")

    rounded(
        ax,
        (0.8, 0.55),
        8.4,
        1.1,
        C_GREY,
        "6. AuditLogger.append(DecisionRecord)\nJSON Lines: categories, decision, latency_ms",
        9,
    )
    arrow(ax, (1.7, 2.0), (3.5, 1.65), color="#666666")
    arrow(ax, (5.0, 2.0), (5.0, 1.65), color="#666666")
    arrow(ax, (8.3, 2.0), (6.5, 1.65), color="#666666")
    color_legend(
        ax,
        [
            ("#F4CCCC", "DENY (block)"),
            (C_YELLOW, "ASK (human / fail-closed)"),
            (C_GREEN, "ALLOW (forward)"),
            (C_GREY, "Audit log sink"),
            ("#C00000", "Red arrow = deny"),
            ("#BF8F00", "Amber arrow = ask"),
            ("#548235", "Green arrow = allow"),
        ],
        x=0.3,
        y=-0.75,
        cols=4,
        dx=2.4,
        fontsize=6.8,
    )
    save(fig, "fig4_decision_flow")


def fig5_eval_pipeline():
    fig, ax = plt.subplots(figsize=(11.2, 4.4))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 4.8)
    ax.axis("off")
    ax.set_title("Experimental Setup: Evaluation Pipeline", fontsize=13, fontweight="bold", pad=8)

    items = [
        (0.2, C_BLUE, "Dataset\n(Pilot 87 or\nLarge-scale 20k)", "Same cases under\nevery policy", "#2F5496"),
        (3.2, C_ORANGE, "Policy Profile\n(read_only /\nlimited_network / …)", "", None),
        (6.2, C_GREEN, "Enforcement Proxy\n(same binary)", "Zero code change\nbetween conditions", "#548235"),
        (9.2, C_PURPLE, "Decision\nALLOW / DENY\n(+ latency)", "", None),
        (12.2, C_SALMON, "Metrics\nASR, TSR,\nF1, ms", "ASK treated\nas DENY", "#C00000"),
    ]
    for x, color, text, note, note_c in items:
        rounded(ax, (x, 2.2), 2.7, 1.7, color, text, 8)
        if note:
            ax.text(x + 1.35, 1.45, note, ha="center", va="center", fontsize=7.5, color=note_c)
    for x in (2.9, 5.9, 8.9, 11.9):
        arrow(ax, (x, 3.05), (x + 0.3, 3.05))
    color_legend(
        ax,
        [
            (C_BLUE, "Dataset / input"),
            (C_ORANGE, "Policy under test"),
            (C_GREEN, "Enforcement proxy"),
            (C_PURPLE, "Decision record"),
            (C_SALMON, "Metrics output"),
        ],
        x=0.3,
        y=0.25,
        cols=5,
        dx=2.9,
        fontsize=7,
    )
    ax.text(
        7.5,
        0.05,
        "Pilot and large-scale runs use the identical prototype; only the input corpus changes.",
        ha="center",
        fontsize=8,
        color="#555555",
        style="italic",
    )
    save(fig, "fig5_eval_pipeline")


def fig6_asr_tsr():
    policies = ["read_only", "limited_network", "no_code_exec", "approval_gated"]
    asr = [2.92, 2.92, 17.68, 10.48]
    tsr = [57.62, 78.74, 97.32, 81.38]
    # One stable color per policy (shared across ASR/TSR panels)
    colors = {
        "read_only": "#E24A33",
        "limited_network": "#3A7D44",
        "no_code_exec": "#F08C2D",
        "approval_gated": "#7A68A6",
    }
    colors_asr = [colors[p] for p in policies]
    colors_tsr = [colors[p] for p in policies]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8))
    fig.suptitle("Large-Scale Evaluation (20,000 cases)", fontsize=13, fontweight="bold")

    ax = axes[0]
    bars = ax.bar(policies, asr, color=colors_asr, edgecolor=EDGE, linewidth=0.8)
    ax.set_title("ASR (lower is better)", fontsize=11)
    ax.set_ylabel("Attack Success Rate (%)")
    ax.set_ylim(0, 50)
    ax.tick_params(axis="x", rotation=18)
    for b, v in zip(bars, asr):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.0, f"{v:.2f}%", ha="center", fontsize=8, fontweight="bold")

    ax = axes[1]
    bars = ax.bar(policies, tsr, color=colors_tsr, edgecolor=EDGE, linewidth=0.8)
    ax.set_title("TSR (higher is better)", fontsize=11)
    ax.set_ylabel("Task Success Rate (%)")
    ax.set_ylim(0, 110)
    ax.tick_params(axis="x", rotation=18)
    for b, v in zip(bars, tsr):
        ax.text(b.get_x() + b.get_width() / 2, v + 2.0, f"{v:.2f}%", ha="center", fontsize=8, fontweight="bold")

    handles = [mpatches.Patch(facecolor=colors[p], edgecolor=EDGE, label=p) for p in policies]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=4,
        frameon=True,
        title="Color key (policy identity; same color in both panels)",
        fontsize=8,
        title_fontsize=8,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, "fig6_asr_tsr")


def fig7_tradeoff():
    # TSR, Block rate (= 100 - ASR)
    points = {
        "read_only": (57.62, 97.08, "#E24A33"),
        "limited_network": (78.74, 97.08, "#3A7D44"),
        "approval_gated": (81.38, 89.52, "#7A68A6"),
        "no_code_exec": (97.32, 82.32, "#F08C2D"),
    }
    fig, ax = plt.subplots(figsize=(7.2, 5.8))
    ax.set_title("Security–Utility Trade-off (20k cases)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Task Success Rate — Utility (%)")
    ax.set_ylabel("Attack Block Rate — Security (%)")
    ax.set_xlim(50, 105)
    ax.set_ylim(55, 105)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.axvline(75, color="#9DC3E6", linestyle="--", linewidth=1.2, label="Utility guide (TSR=75%)")
    ax.axhline(95, color="#A9D08E", linestyle="--", linewidth=1.2, label="Security guide (Block=95%)")

    for label, (x, y, c) in points.items():
        ax.scatter([x], [y], s=220, c=c, edgecolors=EDGE, linewidths=1.0, zorder=3, label=label.replace("_", " "))
        ax.text(x, y + 2.2, label.replace("_", " "), ha="center", fontsize=9, fontweight="bold")

    ax.legend(
        loc="lower left",
        fontsize=8,
        frameon=True,
        title="Color key (policy identity; dashed = reference guides)",
        title_fontsize=8,
    )
    fig.tight_layout()
    save(fig, "fig7_tradeoff")


def main():
    _setup()
    fig1_architecture()
    fig2_pipeline()
    fig3_inference()
    fig4_decision_flow()
    fig5_eval_pipeline()
    fig6_asr_tsr()
    fig7_tradeoff()
    print("SVG dir:", OUT)
    print("PNG dir:", PNG)


if __name__ == "__main__":
    main()
