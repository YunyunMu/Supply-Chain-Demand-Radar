"""Evaluiert die KI-Ausgaben für alle Teile.
Benutzung:  python evaluate.py v1     oder     python evaluate.py v2
Ergebnis:   results_v1.csv / results_v2.csv  (in Excel/Numbers öffnen und von Hand bewerten)
"""
import os
import re
import sys
import time

import pandas as pd

import ai_explain
from analysis import compare, part_summary

# Deine "Musterlösung": Welches Risiko ist für jedes Teil richtig? (bitte selbst prüfen!)
EXPECTED = {
    "A-1001": "niedrig", "A-1002": "hoch", "B-2001": "hoch",
    "B-2002": "niedrig", "S-3001": "niedrig", "L-4001": "niedrig",
}
REQUIRED = {"risk_level", "summary", "likely_causes", "recommended_actions"}

ORIGINAL_PROMPT = ai_explain.build_prompt


def prompt_v1(row, weekly):
    return ORIGINAL_PROMPT(row, weekly)


def prompt_v2(row, weekly):
    return ORIGINAL_PROMPT(row, weekly) + """

Zusätzliche Regeln:
- Nenne ausschließlich Zahlen, die wörtlich in den Daten vorkommen.
- Formuliere Ursachen immer als Hypothese ("möglicherweise ...") und erfinde keine konkreten Ereignisse oder Kundennamen.
- risk_level "hoch" nur bei mindestens 3 auffälligen Wochen oder einer Abweichung von mindestens 50 %; "mittel" bei 1-2 auffälligen Wochen; sonst "niedrig".
- Maßnahmen müssen konkret und von einem Planer innerhalb einer Woche umsetzbar sein."""


PROMPTS = {"v1": prompt_v1, "v2": prompt_v2}


def numbers_in(text: str) -> list[float]:
    text = re.sub(r"(?<=\d)[.\u202f ](?=\d{3}\b)", "", str(text))  # Tausendertrenner entfernen
    return [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", text)]


def allowed_numbers(row: dict, weekly: list[dict]) -> set[float]:
    src = [row["total_old"], row["total_new"], row["flagged_weeks"], len(weekly),
           round(abs(row["total_delta_pct"]) * 100), round(row["max_dev"] * 100),
           round(row["volatility"] * 100)]
    for w in weekly:
        src += [w["week"], w["qty_old"], w["qty_new"], round(abs(w["delta_pct"]) * 100)]
    out = set()
    for s in src:
        out.update(numbers_in(s))
    return out


def ungrounded(text: str, allowed: set[float]) -> list[float]:
    """Zahlen im KI-Text, die nicht in den Daten vorkommen (Hinweis, kein Beweis!)."""
    text = re.sub(r"\b[A-Z]-\d{4}\b", "", text)  # Teilenummern wie B-2001 ignorieren
    bad = []
    for n in numbers_in(text):
        tol = 1 if n <= 100 else 0  # bei Prozentwerten ±1 erlaubt
        if not any(abs(n - a) <= tol for a in allowed):
            bad.append(n)
    return bad


def main(version: str):
    ai_explain.build_prompt = PROMPTS[version]
    old = pd.read_csv("data/forecast_v1.csv", parse_dates=["week"])
    new = pd.read_csv("data/forecast_v2.csv", parse_dates=["week"])
    m = compare(old, new, 0.25)
    summary = part_summary(m)
    has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

    rows = []
    for _, r in summary.iterrows():
        row = r.to_dict()
        detail = m[m.part_no == row["part_no"]].sort_values("week")
        weekly = detail[["week", "qty_old", "qty_new", "delta_pct"]].assign(
            delta_pct=detail["delta_pct"].round(2)).to_dict("records")
        res = ai_explain.explain(row, weekly)

        causes = res.get("likely_causes", [])
        ai_ok = REQUIRED <= set(res) and not str(causes[:1]).startswith("['(")
        text = " ".join([str(res.get("summary", "")), *map(str, causes),
                         *map(str, res.get("recommended_actions", []))])
        bad = ungrounded(text, allowed_numbers(row, weekly))
        rows.append({
            "version": version, "part_no": row["part_no"],
            "expected_risk": EXPECTED.get(row["part_no"], "?"),
            "ai_risk": res.get("risk_level"),
            "risk_correct": res.get("risk_level") == EXPECTED.get(row["part_no"]),
            "ai_ok": ai_ok,
            "ungrounded_numbers": ", ".join(map(str, bad)),
            "summary": res.get("summary"),
            "causes": " | ".join(map(str, causes)),
            "actions": " | ".join(map(str, res.get("recommended_actions", []))),
            "actionable_1_5": "", "german_1_5": "", "comment": "",  # von Hand ausfüllen
        })
        print(f"{row['part_no']}: risk={res.get('risk_level')} ai_ok={ai_ok} ungrounded={bad}")
        if has_key:
            time.sleep(6)  # Rate Limit der kostenlosen API schonen

    df = pd.DataFrame(rows)
    df.to_csv(f"results_{version}.csv", index=False, encoding="utf-8-sig")
    print(f"\nGespeichert: results_{version}.csv")
    print(f"Risiko korrekt: {df.risk_correct.sum()}/{len(df)} | "
          f"Antworten ohne Fehler: {df.ai_ok.sum()}/{len(df)} | "
          f"Teile mit unbelegten Zahlen: {(df.ungrounded_numbers != '').sum()}/{len(df)}")
    if not df.ai_ok.all():
        print("WARNUNG: Nicht alle Antworten stammen von der KI (kein Key oder API-Fehler).")


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "v1"
    if v not in PROMPTS:
        sys.exit(f"Unbekannte Version. Erlaubt: {', '.join(PROMPTS)}")
    main(v)
