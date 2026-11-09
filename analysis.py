import pandas as pd


def compare(old: pd.DataFrame, new: pd.DataFrame, threshold: float = 0.25) -> pd.DataFrame:
    """Vergleicht zwei Prognoseversionen auf Wochenebene."""
    m = old.merge(new, on=["customer", "part_no", "week"], suffixes=("_old", "_new"))
    m["delta"] = m["qty_new"] - m["qty_old"]
    m["delta_pct"] = m["delta"] / m["qty_old"]
    m["flag"] = m["delta_pct"].abs() >= threshold
    return m


def part_summary(m: pd.DataFrame) -> pd.DataFrame:
    """KPIs pro Teil: Gesamtänderung, Volatilität (MAPE zwischen Versionen), Risiko."""
    m = m.assign(abs_pct=m["delta_pct"].abs())
    g = m.groupby(["customer", "part_no"]).agg(
        total_old=("qty_old", "sum"),
        total_new=("qty_new", "sum"),
        volatility=("abs_pct", "mean"),
        max_dev=("abs_pct", "max"),
        flagged_weeks=("flag", "sum"),
    ).reset_index()
    g["total_delta_pct"] = g["total_new"] / g["total_old"] - 1

    def risk(r):
        if r.flagged_weeks >= 3 or r.max_dev >= 0.5:
            return "hoch"
        if r.flagged_weeks >= 1:
            return "mittel"
        return "niedrig"

    g["risk"] = g.apply(risk, axis=1)
    return g.sort_values(["flagged_weeks", "volatility"], ascending=False)
