"""Run the analysis end to end.

    python -m src.pipeline --stage analyze
    python -m src.pipeline --stage all

Stages
    quality   run the data-quality gate (exit 1 on a critical failure)
    analyze   revenue -> rfm -> cohorts -> delivery -> satisfaction -> sellers
    report    build reports/results_pack.md from the tables written by analyze
    all       quality -> analyze -> report
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import pandas as pd

from src import config, transform
from src.analysis import cohorts, delivery, revenue, rfm, satisfaction, sellers
from src.utils import LOG


def stage_quality() -> bool:
    from src.quality import run_quality_checks
    _, ok = run_quality_checks.run()
    return ok


def stage_analyze() -> None:
    config.ensure_dirs()
    t0 = time.time()
    fact, items, distance = transform.load_all()
    LOG.info("loaded fact=%s items=%s distance=%s",
             f"{len(fact):,}", f"{len(items):,}",
             f"{len(distance):,}" if distance is not None else "n/a")

    results = {}
    results.update(revenue.run(fact))
    results.update(rfm.run(fact))
    results.update(cohorts.run(fact))
    results.update(delivery.run(fact, distance))
    results.update(satisfaction.run(fact, items))
    results.update(sellers.run(fact, items))

    manifest = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "data_source": config.DATA_SOURCE,
        "analysis_start_month": config.ANALYSIS_START_MONTH,
        "gross_margin_assumption": config.GROSS_MARGIN_ASSUMPTION,
        "rows": {
            "orders": int(len(fact)),
            "revenue_orders": int(fact["is_revenue_order"].sum()),
            "delivered_orders": int(fact["is_delivered"].sum()),
            "unique_customers": int(fact["customer_unique_id"].nunique()),
            "order_items": int(len(items)),
        },
        "tables_written": len(results),
        "runtime_seconds": round(time.time() - t0, 1),
    }
    (config.REPORTS_DIR / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LOG.info("analysis done in %.1fs -- %d tables, %d figures",
             time.time() - t0, len(results), len(list(config.FIGURES_DIR.glob("*.png"))))


def stage_report() -> None:
    from src.export import build_report_tables
    build_report_tables.build()


def main() -> int:
    p = argparse.ArgumentParser(description="Olist analytics pipeline")
    p.add_argument("--stage", default="all", choices=["quality", "analyze", "report", "all"])
    args = p.parse_args()

    if args.stage in ("quality", "all"):
        if not stage_quality() and args.stage == "all":
            LOG.error("quality gate failed -- stopping before analysis")
            return 1
    if args.stage in ("analyze", "all"):
        stage_analyze()
    if args.stage in ("report", "all"):
        stage_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
