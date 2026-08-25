#!/usr/bin/env python3
"""Build CORPUS_GRAPH_OFFLINE_REVIEW.md (and optionally PDF via pandoc)."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd


def short_title(text: object, n: int = 90) -> str:
    s = "" if pd.isna(text) else str(text).strip().replace("|", "/")
    return s if len(s) <= n else s[: n - 3] + "..."


def md_table(df: pd.DataFrame, cols: list[str], headers: list[str] | None = None) -> str:
    headers = headers or cols
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(cols)) + "|",
    ]
    for _, row in df.iterrows():
        cells = []
        for col in cols:
            value = row[col]
            if col == "title":
                value = short_title(value, 90)
            elif pd.isna(value):
                value = ""
            elif isinstance(value, float) and value == int(value):
                value = int(value)
            cells.append(str(value).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def md_figure(rel_path: str, caption: str) -> str:
    return f"\n![{caption}]({rel_path})\n\n*{caption}*\n"


def tier_row(view: dict, label: str) -> dict:
    for row in view["by_tier"]:
        if row["label"] == label:
            return row
    return {}


def build_markdown(out: Path) -> Path:
    views = json.loads((out / "corpus_graph_views.json").read_text())
    people = json.loads((out / "people_counts.json").read_text())
    full100 = pd.read_csv(out / "people_full_top100.csv")
    integ100_path = out / "people_integrated_top100.csv"
    rescue100_path = out / "people_integrated_plus_rescue_top100.csv"
    integ100 = pd.read_csv(integ100_path if integ100_path.exists() else out / "people_prime_top100.csv")
    rescue100 = pd.read_csv(rescue100_path if rescue100_path.exists() else out / "people_prime_top100.csv")
    full_last = pd.read_csv(out / "people_full_top100_by_last.csv")
    rescue_last_path = out / "people_integrated_plus_rescue_top100_by_last.csv"
    rescue_last = pd.read_csv(
        rescue_last_path if rescue_last_path.exists() else out / "people_prime_top100_by_last.csv"
    )

    ultra_path = out / "label_ultra_core_ranked.csv"
    core_path = out / "label_core_ranked.csv"
    ultra = pd.read_csv(ultra_path if ultra_path.exists() else out / "label_ultra_core.csv")
    core = pd.read_csv(core_path) if core_path.exists() else None

    for frame in (full100, integ100, rescue100, full_last, rescue_last):
        if "rank" not in frame.columns:
            frame.insert(0, "rank", range(1, len(frame) + 1))

    dropped_wu = views["dropped_weak_unlinked"]
    dropped_ng = views.get("dropped_no_graph", {})
    full = views["full"]
    integrated = views["integrated"]
    rescued = views["integrated_plus_rescue"]
    prime = views["prime"]  # legacy audit cut only
    fig = "viz/figures"
    ppl_integ = people.get("integrated", people.get("prime", {}))
    ppl_rescue = people.get("integrated_plus_rescue", people.get("prime", {}))

    parts: list[str] = []
    parts.append(
        f"""# Connectomics corpus graph review

**Date:** {date.today().isoformat()}  
**Screening:** IA-007-v3 agent adjudication (complete)  
**Scope:** IA-013 layers (full → integrated → integrated+rescue), citation roles, authorship (trim_middle), people, ultra-core and core paper lists, figures

---

## 1. Executive summary

Preferred nested corpus views over the v3 inclusive set (core + adjacent + role_bridge):

| | Full | Integrated | Integrated+rescue |
|---|---:|---:|---:|
| Inclusive works | {full['works']:,} | {integrated['works']:,} | {rescued['works']:,} |
| Core | {full['decision_counts'].get('core_relevant', 0):,} | {integrated['decision_counts'].get('core_relevant', 0):,} | {rescued['decision_counts'].get('core_relevant', 0):,} |
| Adjacent | {full['decision_counts'].get('adjacent_relevant', 0):,} | {integrated['decision_counts'].get('adjacent_relevant', 0):,} | {rescued['decision_counts'].get('adjacent_relevant', 0):,} |
| Role bridge | {full['decision_counts'].get('role_bridge', 0):,} | {integrated['decision_counts'].get('role_bridge', 0):,} | {rescued['decision_counts'].get('role_bridge', 0):,} |
| Ultra-core | {full['ultra_core']} | {integrated['ultra_core']} | {rescued['ultra_core']} |
| People (trim_middle) | {people['full']['unique_persons_trim_middle']:,} | {ppl_integ.get('unique_persons_trim_middle', 0):,} | {ppl_rescue.get('unique_persons_trim_middle', 0):,} |

**Integrated** = full minus **`no_graph`** and minus **`weak_unlinked`** (in = 0 and in+out ≤ 2).  
**Integrated+rescue** = integrated ∪ high-value `no_graph` reinstatements (ultra ∨ cites ≥ 100 ∨ (core ∧ cites ≥ 50)).

Dropped from full to reach integrated: {dropped_ng.get('works', 0)} `no_graph` and {dropped_wu['works']} `weak_unlinked`. Rescue brings back {dropped_ng.get('rescued', 0)} of the `no_graph` papers (including all ultra that were off-graph).

**Legacy prime** (audit only) = full − `weak_unlinked` while **keeping** `no_graph` → {prime['works']:,} works. Prefer integrated / integrated+rescue for “citation-integrated” claims (IA-013).

**Use full** for high-recall audit and periphery review. **Use integrated** for strict graph analyses. **Use integrated+rescue** for checkpoint / curriculum when coverage gaps matter.

Machine-readable lists: `label_ultra_core_ranked.csv` (n={len(ultra)}), `label_core_ranked.csv` (n={len(core) if core is not None else full['decision_counts'].get('core_relevant', 0)}).

---

## 2. Shared rules

1. **Semantic tiers** from IA-007-v3 agent adjudication (strict nanoscale / synaptic wiring core).
2. **Citation graph** is directed and asymmetric; high out/in is normal.
3. **Link strength:** weak_unlinked / weak / moderate / strong (weak if total degree <= 2; weak_unlinked if also in = 0); `no_graph` when degrees are undefined.
4. **Authorship trim (`trim_middle`):** exclude authors whose *only* corpus credit is a single middle-author slot (including middle on a consortium paper when that is their sole inclusion). Consortium middles with other credit elsewhere are kept. First/last weighted higher for community assignment.
5. **ultra_core:** core_relevant AND (citations >= 200 OR landmark title AND citations >= 100).

---

## 3. Screening ladder (v2 -> v3 + IA-013)

| Rung | v2 | v3 full | Integrated | +rescue |
|---|---:|---:|---:|---:|
| Inclusive | 1,912 | **{full['works']:,}** | **{integrated['works']:,}** | **{rescued['works']:,}** |
| core | 1,075 | **{full['decision_counts'].get('core_relevant', 0):,}** | **{integrated['decision_counts'].get('core_relevant', 0):,}** | **{rescued['decision_counts'].get('core_relevant', 0):,}** |
| ultra_core | 65 | **{full['ultra_core']}** | **{integrated['ultra_core']}** | **{rescued['ultra_core']}** |

v3 demotes many v2 false cores (macro MRI, reviews, adjacent biology). Integrated drops both unmeasured (`no_graph`) and thin (`weak_unlinked`) attachments; rescue restores coverage-critical `no_graph` works without claiming they are graph-integrated.
"""
    )
    parts.append(md_figure(f"{fig}/01_ia013_layer_ladder.png", "Figure 1. IA-013 layer ladder (full → integrated → +rescue)"))
    parts.append(
        """
---

## 4. Citation position by tier
"""
    )

    parts.append(
        "| Tier | Full works | Full med total deg | Full weak_unlinked | Full no_graph | Integrated works | +rescue works |\n"
        "|---|---:|---:|---:|---:|---:|---:|"
    )
    for label, short in [
        ("core_relevant", "core"),
        ("adjacent_relevant", "adjacent"),
        ("role_bridge", "bridge"),
    ]:
        ft = tier_row(full, label)
        it = tier_row(integrated, label)
        rt = tier_row(rescued, label)
        parts.append(
            f"| {short} | {ft.get('works')} | {ft.get('median_total_degree')} | "
            f"{ft.get('weak_unlinked')} | {ft.get('no_graph')} | "
            f"**{it.get('works')}** | **{rt.get('works')}** |"
        )

    parts.append(
        """
### Citation roles (graph-matched, full view)

| Tier | hub | broker | only_out | only_in | isolate |
|---|---:|---:|---:|---:|---:|"""
    )
    for label, short in [
        ("core_relevant", "core"),
        ("adjacent_relevant", "adjacent"),
        ("role_bridge", "bridge"),
    ]:
        roles = tier_row(full, label).get("citation_roles", {})
        parts.append(
            f"| {short} | {roles.get('hub', 0)} | {roles.get('broker', 0)} | "
            f"{roles.get('only_out', 0)} | {roles.get('only_in', 0)} | {roles.get('isolate', 0)} |"
        )

    parts.append(
        """
Core concentrates brokers/hubs. Adjacent is only-out and weak_unlinked heavy. Bridge is often off-graph.
"""
    )
    parts.append(md_figure(f"{fig}/02_link_strength_by_tier.png", "Figure 2. Citation link strength by tier"))
    parts.append(md_figure(f"{fig}/03_citation_roles_by_tier.png", "Figure 3. Directed citation roles by tier"))

    parts.append(
        f"""
---

## 5. Authorship and communities

| | Full | Integrated | +rescue |
|---|---:|---:|---:|
| Coauthor nodes | {full['coauthorship']['nodes']} | {integrated['coauthorship']['nodes']} | {rescued['coauthorship']['nodes']} |
| Coauthor edges | {full['coauthorship']['edges']} | {integrated['coauthorship']['edges']} | {rescued['coauthorship']['edges']} |
| Communities | {full['coauthorship']['communities']} | {integrated['coauthorship']['communities']} | {rescued['coauthorship']['communities']} |
| Persons with first/last | {people['full']['persons_with_first_or_last']} | {ppl_integ.get('persons_with_first_or_last', '')} | {ppl_rescue.get('persons_with_first_or_last', '')} |
| Raw unique bylines | {people['full']['unique_persons_raw']} | {ppl_integ.get('unique_persons_raw', '')} | {ppl_rescue.get('unique_persons_raw', '')} |
| Excluded sole middle-only | {people['full']['excluded_single_middle_only']} | {ppl_integ.get('excluded_single_middle_only', '')} | {ppl_rescue.get('excluded_single_middle_only', '')} |
"""
    )

    parts.append("### Top communities (full)\n")
    parts.append("| Community | Works | Core | Adjacent | Ultra |\n|---|---:|---:|---:|---:|")
    for community in full["top_communities"][:8]:
        parts.append(
            f"| {community['community_label']} | {community['works']} | {community['core']} | "
            f"{community['adjacent']} | {community['ultra_core']} |"
        )

    parts.append("\n### Top communities (integrated+rescue)\n")
    parts.append("| Community | Works | Core | Adjacent | Ultra |\n|---|---:|---:|---:|---:|")
    for community in rescued["top_communities"][:8]:
        parts.append(
            f"| {community['community_label']} | {community['works']} | {community['core']} | "
            f"{community['adjacent']} | {community['ultra_core']} |"
        )

    parts.append(
        md_figure(
            f"{fig}/04_top_communities_integrated_plus_rescue.png",
            "Figure 4. Top coauthor communities (integrated+rescue)",
        )
    )
    parts.append(md_figure(f"{fig}/05_core_ultra_by_year.png", "Figure 5. Core vs ultra-core by year"))
    parts.append(md_figure(f"{fig}/06_core_in_out_degree.png", "Figure 6. Core citation in/out degree"))

    parts.append(
        f"""
---

## 6. Interpretation

**Full** is the high-recall field map: every inclusive paper, annotated with citation role and lab lineage, including thin attachments (`weak_unlinked`) and off-graph papers (`no_graph`).

**Integrated** is the true citation-integrated spine: drop both `no_graph` and `weak_unlinked`.

**Integrated+rescue** is the preferred checkpoint when coverage gaps matter: same as integrated, plus flagged high-value `no_graph` reinstatements (not claimed as graph-integrated).

**Legacy prime** drops only `weak_unlinked` and keeps all `no_graph` — useful as an audit continuity cut, not as the “integrated” claim.

Recommended use:

1. Checkpoint / curriculum spine → integrated+rescue core ∩ (moderate ∪ strong ∪ ultra ∪ rescued_no_graph).
2. Strict graph analyses → integrated only.
3. Human review → full ∩ (`weak_unlinked` ∪ unreescued `no_graph`), especially core.
4. Ultra-core list → all {full['ultra_core']} appear under full and integrated+rescue ({integrated['ultra_core']} remain on-graph in strict integrated).
5. Community maps → prefer integrated+rescue for nanoscale program lineages.

---

## 7. People counts

| Metric | Full | Integrated | +rescue |
|---|---:|---:|---:|
| Works | {people['full']['works']} | {ppl_integ.get('works', '')} | {ppl_rescue.get('works', '')} |
| Author mentions (raw) | {people['full']['author_mentions_raw']:,} | {ppl_integ.get('author_mentions_raw', 0):,} | {ppl_rescue.get('author_mentions_raw', 0):,} |
| Unique persons (raw) | {people['full']['unique_persons_raw']:,} | {ppl_integ.get('unique_persons_raw', 0):,} | {ppl_rescue.get('unique_persons_raw', 0):,} |
| **Persons after trim_middle** | **{people['full']['unique_persons_trim_middle']:,}** | **{ppl_integ.get('unique_persons_trim_middle', 0):,}** | **{ppl_rescue.get('unique_persons_trim_middle', 0):,}** |
| With first or last credit | {people['full']['persons_with_first_or_last']:,} | {ppl_integ.get('persons_with_first_or_last', 0):,} | {ppl_rescue.get('persons_with_first_or_last', 0):,} |
| Sole middle-only excluded | {people['full']['excluded_single_middle_only']:,} | {ppl_integ.get('excluded_single_middle_only', 0):,} | {ppl_rescue.get('excluded_single_middle_only', 0):,} |
| Top-100 floor (min works) | >={people['full']['top_100_min_works']} | >={ppl_integ.get('top_100_min_works', '')} | >={ppl_rescue.get('top_100_min_works', '')} |
| Top-100 median works | {people['full']['top_100_median_works']} | {ppl_integ.get('top_100_median_works', '')} | {ppl_rescue.get('top_100_median_works', '')} |

Ranking for top 100 by works: works desc, then last-author count, first/single, ultra_core works, core works. Eligible authors only under trim_middle.
"""
    )
    parts.append(md_figure(f"{fig}/08_top20_people_full.png", "Figure 7. Top 20 people (full)"))
    parts.append(
        md_figure(
            f"{fig}/09_top20_people_integrated_plus_rescue.png",
            "Figure 8. Top 20 people (integrated+rescue)",
        )
    )

    parts.append("\n---\n\n## 8. Top 100 people - full corpus (by works)\n\n")
    parts.append(
        md_table(
            full100,
            [
                "rank",
                "display_name",
                "works",
                "last",
                "first_or_single",
                "middle",
                "core_works",
                "adjacent_works",
                "ultra_core_works",
            ],
            ["#", "Name", "Works", "Last", "First", "Middle", "Core", "Adj", "Ultra"],
        )
    )
    parts.append("\n\n## 9. Top 100 people - integrated+rescue (by works)\n\n")
    parts.append(
        md_table(
            rescue100,
            [
                "rank",
                "display_name",
                "works",
                "last",
                "first_or_single",
                "middle",
                "core_works",
                "adjacent_works",
                "ultra_core_works",
            ],
            ["#", "Name", "Works", "Last", "First", "Middle", "Core", "Adj", "Ultra"],
        )
    )
    parts.append("\n\n## 10. Top 100 people - full corpus (by last-author count)\n\n")
    parts.append(
        md_table(
            full_last,
            ["rank", "display_name", "last", "works", "first_or_single", "core_works", "ultra_core_works"],
            ["#", "Name", "Last", "Works", "First", "Core", "Ultra"],
        )
    )
    parts.append("\n\n## 11. Top 100 people - integrated+rescue (by last-author count)\n\n")
    parts.append(
        md_table(
            rescue_last,
            ["rank", "display_name", "last", "works", "first_or_single", "core_works", "ultra_core_works"],
            ["#", "Name", "Last", "Works", "First", "Core", "Ultra"],
        )
    )

    # Ultra list
    if "rank" not in ultra.columns:
        ultra = (
            ultra.sort_values("citation_count_work", ascending=False)
            .reset_index(drop=True)
            .assign(rank=lambda frame: range(1, len(frame) + 1))
        )
    ultra_cols = ["rank", "title", "year", "last_author", "citation_count_work", "cites_per_year", "citation_link_strength", "primary_community_label"]
    ultra_cols = [c for c in ultra_cols if c in ultra.columns]
    ultra_headers = {
        "rank": "#",
        "title": "Title",
        "year": "Year",
        "last_author": "Last",
        "citation_count_work": "Cites",
        "cites_per_year": "Cites/yr",
        "citation_link_strength": "Link",
        "primary_community_label": "Community",
    }
    parts.append(f"\n\n## 12. Ultra-core papers (n={len(ultra)})\n\n")
    parts.append(
        f"All {full['ultra_core']} under full and integrated+rescue; "
        f"{integrated['ultra_core']} remain on-graph in strict integrated. "
        "Rule: core_relevant AND (cites >= 200 OR landmark AND cites >= 100). "
        "CSV: `label_ultra_core_ranked.csv`.\n\n"
    )
    parts.append(md_figure(f"{fig}/10_ultra_core_all_by_cites.png", "Figure 9. All ultra-core papers by citations"))
    parts.append(md_figure(f"{fig}/07_top25_core_by_cites.png", "Figure 10. Top 25 core papers by citations"))
    parts.append(
        md_table(ultra, ultra_cols, [ultra_headers[c] for c in ultra_cols])
    )

    # Full core list
    if core is not None:
        core_cols = [
            "rank",
            "title",
            "year",
            "last_author",
            "citation_count_work",
            "cites_per_year",
            "ultra_core",
            "citation_link_strength",
            "citation_role",
            "primary_community_label",
        ]
        core_cols = [c for c in core_cols if c in core.columns]
        core_headers = {
            "rank": "#",
            "title": "Title",
            "year": "Year",
            "last_author": "Last",
            "citation_count_work": "Cites",
            "cites_per_year": "Cites/yr",
            "ultra_core": "Ultra",
            "citation_link_strength": "Link",
            "citation_role": "Role",
            "primary_community_label": "Community",
        }
        parts.append(f"\n\n## 13. Core papers — full explicit list (n={len(core)})\n\n")
        parts.append(
            "All v3 `core_relevant` works, ranked by citations. Ultra flag marks the nested ultra-core set. "
            "CSV: `label_core_ranked.csv` (also `label_core_non_ultra_ranked.csv`).\n\n"
        )
        # Year as int where possible
        core_show = core.copy()
        if "year" in core_show.columns:
            core_show["year"] = core_show["year"].apply(
                lambda v: int(v) if pd.notna(v) and float(v) == int(float(v)) else v
            )
        if "ultra_core" in core_show.columns:
            core_show["ultra_core"] = core_show["ultra_core"].map(
                lambda v: "Y" if bool(v) else ""
            )
        parts.append(md_table(core_show, core_cols, [core_headers[c] for c in core_cols]))

    parts.append(
        """

---

## 14. Caveats

- Citation graph covers ~73% of inclusive works; `no_graph` is common for role_bridge.
- Prime does not drop `no_graph` - only explicit `weak_unlinked`.
- Coauthor / person reconciliation uses byline strings; not ORCID-complete.
- Consortium threshold = 20 authors.
- This document is an interpretation for offline review, not a preregistered endpoint.

## 15. Regenerability

```bash
python analysis/analyze_citation_roles.py
python analysis/compare_v2_v3_quick.py
python analysis/build_corpus_graph_views.py
python analysis/build_people_tables.py
python analysis/build_paper_lists_and_figures.py
python analysis/build_offline_review_pdf.py
```

Artifacts live under `postanalysis/llm_agent_v3/` (lists + `viz/figures/*.png`).
"""
    )

    md_path = out / "CORPUS_GRAPH_OFFLINE_REVIEW.md"
    md_path.write_text("\n".join(parts))
    return md_path


def fold_for_pdflatex(text: str) -> str:
    """ASCII-fold for pdflatex: keep content, drop accents / symbolic unicode."""
    import unicodedata

    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    for src, dst in {
        "\u2264": "<=",
        "\u2265": ">=",
        "\u2227": "AND",
        "\u2228": "OR",
        "\u2192": "->",
        "\u2193": "desc",
        "\u2013": "-",
        "\u2014": "-",
        "\u2229": "intersect",
        "\u222a": "union",
        "\u00d7": "x",
        "\u2026": "...",
        "\u0142": "l",
        "\u015b": "s",
        "\u0107": "c",
        "\u0161": "s",
    }.items():
        text = text.replace(src, dst)
    return text.encode("ascii", "ignore").decode("ascii")


def build_pdf(md_path: Path, pdf_path: Path) -> None:
    safe_md = md_path.with_suffix(".ascii.md")
    safe_md.write_text(fold_for_pdflatex(md_path.read_text()))
    header = md_path.with_suffix(".header.tex")
    header.write_text(
        r"""
\usepackage[margin=0.65in]{geometry}
\usepackage{longtable}
\usepackage{booktabs}
\usepackage{array}
\usepackage{graphicx}
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\lhead{Connectomics corpus graph review}
\rhead{\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\setlength{\parskip}{0.35em}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
"""
    )
    cmd = [
        "pandoc",
        str(safe_md),
        "-o",
        str(pdf_path),
        "--pdf-engine=pdflatex",
        "-V",
        "documentclass=article",
        "-V",
        "fontsize=9pt",
        "-H",
        str(header),
        "--toc",
        "--toc-depth=2",
        "--resource-path",
        str(md_path.parent),
        "-f",
        "markdown",
        "-t",
        "pdf",
    ]
    try:
        subprocess.run(cmd, check=True)
    finally:
        header.unlink(missing_ok=True)
        safe_md.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent_v3"))
    ap.add_argument("--pdf", action="store_true", default=True)
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()

    md_path = build_markdown(args.out)
    print(f"Wrote {md_path} ({md_path.stat().st_size:,} bytes)")
    if args.pdf and not args.no_pdf:
        pdf_path = args.out / "CORPUS_GRAPH_OFFLINE_REVIEW.pdf"
        build_pdf(md_path, pdf_path)
        print(f"Wrote {pdf_path} ({pdf_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
