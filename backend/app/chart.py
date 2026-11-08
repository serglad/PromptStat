from datetime import date, datetime, time

DATE_TYPES = {"date", "timestamp", "timestamptz", "timestamp with time zone",
              "timestamp without time zone", "time", "timetz"}
NUMERIC_TYPES = {"int2", "int4", "int8", "smallint", "integer", "bigint", "decimal",
                 "numeric", "real", "double precision", "float4", "float8", "money",
                 "smallserial", "serial", "bigserial"}


def _type_family(pg_type: str) -> str:
    t = pg_type.lower()
    if t in DATE_TYPES or t.startswith("timestamp"):
        return "date"
    if t in NUMERIC_TYPES or t.startswith("numeric") or t.startswith("int"):
        return "numeric"
    return "other"


def _distinct_count(values: list) -> int:
    seen = set()
    for v in values:
        seen.add(str(v))
        if len(seen) > 20:
            return len(seen)
    return len(seen)


def build_chart(columns: list[str], rows: list[list], pg_types: list[str] | None) -> tuple[str, dict | None]:
    """Return (chart_type, chart_spec). Decision is made only here, never in frontend."""
    if not columns or not rows:
        return "table", None

    if pg_types is None or len(pg_types) != len(columns):
        pg_types = [_guess_type(rows, i) for i in range(len(columns))]

    families = [_type_family(t) for t in pg_types]
    numeric_idx = [i for i, f in enumerate(families) if f == "numeric"]
    date_idx = [i for i, f in enumerate(families) if f == "date"]

    if not numeric_idx:
        return "table", None

    # prefer x = earliest date column, y = first numeric column after x
    if date_idx:
        x = date_idx[0]
        ys = [i for i in numeric_idx if i != x]
        if ys:
            y = ys[0]
            spec = {"type": "line", "x": columns[x], "y": columns[y], "series": [columns[y]], "title": None}
            return "line", spec

    # categorical candidates: non-numeric, non-date
    for x, f in enumerate(families):
        if f != "other":
            continue
        col_values = [row[x] for row in rows if x < len(row)]
        distinct = _distinct_count(col_values)
        ys = [i for i in numeric_idx if i != x]
        if not ys:
            continue
        y = ys[0]
        if distinct <= 6 and len(rows) <= 20:
            spec = {"type": "pie", "x": columns[x], "y": columns[y], "series": [columns[y]], "title": None}
            return "pie", spec
        if distinct <= 20:
            spec = {"type": "bar", "x": columns[x], "y": columns[y], "series": [columns[y]], "title": None}
            return "bar", spec

    return "table", None


def _guess_type(rows: list[list], col: int) -> str:
    for row in rows:
        if col >= len(row):
            continue
        v = row[col]
        if v is None:
            continue
        if isinstance(v, bool):
            return "text"
        if isinstance(v, (int, float)):
            return "int8"
        if isinstance(v, str) and _looks_like_date(v):
            return "timestamp"
        return "text"
    return "text"


def _looks_like_date(v: str) -> bool:
    s = v.strip()
    if len(s) < 8:
        return False
    for parser in (date.fromisoformat, datetime.fromisoformat):
        try:
            parser(s)
            return True
        except ValueError:
            continue
    return False
