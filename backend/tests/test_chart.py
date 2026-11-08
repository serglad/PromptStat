from datetime import date

from app.chart import build_chart


def test_line_for_date_numeric():
    cols = ["week", "registrations"]
    rows = [["2026-08-03", 10], ["2026-08-10", 15]]
    types = ["timestamp", "int8"]
    ctype, spec = build_chart(cols, rows, types)
    assert ctype == "line"
    assert spec["x"] == "week" and spec["y"] == "registrations"


def test_bar_for_category_numeric():
    cols = ["platform", "signups"]
    rows = [["ios", 5], ["android", 8], ["web", 2]]
    types = ["text", "int8"]
    ctype, spec = build_chart(cols, rows, types)
    assert ctype == "pie"
    assert spec["x"] == "platform" and spec["y"] == "signups"


def test_bar_for_more_than_6_categories():
    cols = ["name", "value"]
    rows = [[f"c{i}", i] for i in range(10)]
    types = ["text", "int8"]
    ctype, _ = build_chart(cols, rows, types)
    assert ctype == "bar"


def test_table_when_no_numeric():
    cols = ["a", "b"]
    rows = [["x", "y"], ["z", "w"]]
    types = ["text", "text"]
    ctype, spec = build_chart(cols, rows, types)
    assert ctype == "table"
    assert spec is None


def test_table_when_empty():
    assert build_chart([], [], []) == ("table", None)


def test_line_when_date_guessed_from_strings():
    cols = ["day", "cnt"]
    rows = [["2026-01-01", 1], ["2026-01-02", 2]]
    ctype, spec = build_chart(cols, rows, None)
    assert ctype == "line"
