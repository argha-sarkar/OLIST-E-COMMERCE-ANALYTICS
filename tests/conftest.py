import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "raw"


@pytest.fixture(scope="session")
def raw():
    """The 9 tables, read from the committed fixture CSVs (no Kaggle, no MySQL)."""
    from src import transform
    return transform.read_raw(FIXTURE_DIR)


@pytest.fixture(scope="session")
def fact(raw):
    from src import transform
    return transform.build_order_fact(raw)


@pytest.fixture(scope="session")
def items(raw, fact):
    from src import transform
    return transform.build_items_enriched(raw, fact)
