import pandas as pd


def test_month_ordinal_arithmetic():
    from src.utils import month_ordinal
    s = pd.Series(["2017-01", "2017-02", "2018-01"])
    out = month_ordinal(s)
    assert list(out) == [2017 * 12 + 1, 2017 * 12 + 2, 2018 * 12 + 1]
    assert out.iloc[2] - out.iloc[0] == 12


def test_md_table_renders_numbers_and_blanks():
    from src.utils import md_table
    df = pd.DataFrame({"a": [1, 2], "b": [1.5, None], "c": ["x", "y"]})
    out = md_table(df)
    assert "| a | b | c |" in out
    assert "1,000" not in out
    assert out.count("\n") >= 4


def test_complete_months_flags_partial_month(fact):
    from src.utils import complete_months
    table = complete_months(fact)
    assert "is_complete" in table.columns
    assert table["is_complete"].dtype == bool
