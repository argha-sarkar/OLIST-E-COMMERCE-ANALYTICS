"""RFM logic: grain, direction of the recency score, and segment coverage."""
import pandas as pd


def test_rfm_grain_is_customer_unique_id(fact):
    from src.analysis import rfm
    table = rfm.build_rfm(fact)
    assert table["customer_unique_id"].is_unique
    assert len(table) == fact[fact["is_revenue_order"] == 1]["customer_unique_id"].nunique()


def test_recency_score_is_inverted(fact):
    """A recent buyer must score 5, a dormant one 1. Getting this backwards is
    the most common RFM bug."""
    from src.analysis import rfm
    table = rfm.build_rfm(fact)
    most_recent = table.sort_values("recency_days").iloc[0]
    most_dormant = table.sort_values("recency_days").iloc[-1]
    assert most_recent["r_score"] >= most_dormant["r_score"]


def test_scores_within_range(fact):
    from src.analysis import rfm
    table = rfm.build_rfm(fact)
    for col in ["r_score", "f_score", "m_score"]:
        assert table[col].between(1, 5).all()


def test_every_customer_has_a_segment(fact):
    from src.analysis import rfm
    table = rfm.build_rfm(fact)
    assert table["segment"].notna().all()
    assert table["segment"].str.match(r"^\d\d ").all()


def test_repeat_rate_differs_between_bases(fact):
    """customer_id is per order: using it makes retention look like zero."""
    from src.analysis import rfm
    table = rfm.repeat_rate(fact).set_index("basis")
    correct = table.loc["customer_unique_id (correct)", "repeat_rate_pct"]
    wrong = table.loc["customer_id (wrong on purpose)", "repeat_rate_pct"]
    assert correct == 25.0          # cu1 and cu3 repeat in the fixture
    assert wrong == 0.0
    assert correct != wrong


def test_segment_summary_shares_sum_to_100(fact):
    from src.analysis import rfm
    table = rfm.build_rfm(fact)
    summary = rfm.segment_summary(table)
    assert abs(summary["pct_of_customers"].sum() - 100) < 0.5
    assert abs(summary["pct_of_gmv"].sum() - 100) < 0.5
