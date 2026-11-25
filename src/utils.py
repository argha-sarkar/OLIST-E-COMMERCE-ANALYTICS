"""Logging, IO and formatting helpers shared by every module."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from src import config


def get_logger(name: str = "olist") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


LOG = get_logger()


def save_table(df: pd.DataFrame, name: str) -> Path:
    """Persist a result table so the report is built from data, never retyped."""
    config.ensure_dirs()
    path = config.TABLES_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    LOG.info("table  -> %s (%d rows)", path.name, len(df))
    return path


def save_figure(fig, name: str) -> Path:
    config.ensure_dirs()
    path = config.FIGURES_DIR / f"{name}.png"
    fig.savefig(path, dpi=140, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    LOG.info("figure -> %s", path.name)
    return path


def md_table(df: pd.DataFrame, floatfmt: str = "{:,.2f}", max_rows: int = 40) -> str:
    """Markdown table without a tabulate dependency (keeps CI installs light)."""
    if df is None or len(df) == 0:
        return "_(no rows)_\n"
    d = df.head(max_rows).copy()
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in d.iterrows():
        cells = []
        for v in row:
            if isinstance(v, (int,)) and not isinstance(v, bool):
                cells.append(f"{v:,}")
            elif isinstance(v, float):
                cells.append("" if pd.isna(v) else floatfmt.format(v))
            elif v is None or (not isinstance(v, str) and pd.isna(v)):
                cells.append("")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    if len(df) > max_rows:
        lines.append(f"\n_(showing {max_rows} of {len(df)} rows)_")
    return "\n".join(lines) + "\n"


def brl(value: float) -> str:
    """Brazilian real, the dataset currency."""
    if value is None or pd.isna(value):
        return "n/a"
    return f"R$ {value:,.0f}"


def pct(value: float, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.{digits}f}%"


def month_ordinal(series: pd.Series) -> pd.Series:
    """'2017-03' -> 24207 (year*12 + month). Fast month arithmetic."""
    y = series.str.slice(0, 4).astype(int)
    m = series.str.slice(5, 7).astype(int)
    return y * 12 + m


def complete_months(fact: pd.DataFrame, tail_days: int = None) -> pd.DataFrame:
    """Flag months whose data stops well before month end (partial ingestion)."""
    tail_days = tail_days if tail_days is not None else config.INCOMPLETE_MONTH_TAIL_DAYS
    g = (
        fact.assign(purchase_date=pd.to_datetime(fact["purchase_date"]))
        .groupby("purchase_month")
        .agg(orders=("order_id", "nunique"), last_order_date=("purchase_date", "max"))
        .reset_index()
    )
    month_end = pd.to_datetime(g["purchase_month"] + "-01") + pd.offsets.MonthEnd(0)
    g["month_end"] = month_end
    g["is_complete"] = (month_end - g["last_order_date"]).dt.days <= tail_days
    return g
