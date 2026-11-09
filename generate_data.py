"""Erzeugt synthetische Lieferabruf-Prognosen (2 Versionen). Keine echten Firmendaten!"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
parts_by_customer = {
    "VW": ["A-1001", "A-1002"],
    "BMW": ["B-2001", "B-2002"],
    "Stellantis": ["S-3001"],
    "Lear": ["L-4001"],
}
weeks = pd.date_range("2026-11-16", periods=12, freq="W-MON")

rows = []
for customer, parts in parts_by_customer.items():
    for part in parts:
        base = int(rng.integers(800, 3000))
        for w in weeks:
            rows.append((customer, part, w, int(base * rng.normal(1, 0.05))))
v1 = pd.DataFrame(rows, columns=["customer", "part_no", "week", "qty"])

# Version 2 = neue Prognose: leichtes Rauschen + bewusst eingebaute Ausreißer
v2 = v1.copy()
v2["qty"] = (v2["qty"] * rng.normal(1, 0.06, len(v2))).round().astype(int)

drop = (v2.part_no == "B-2001") & (v2.week >= weeks[4]) & (v2.week <= weeks[7])
v2.loc[drop, "qty"] = (v2.loc[drop, "qty"] * 0.45).astype(int)   # Nachfrageeinbruch
spike = (v2.part_no == "A-1002") & (v2.week >= weeks[2]) & (v2.week <= weeks[3])
v2.loc[spike, "qty"] = (v2.loc[spike, "qty"] * 1.8).astype(int)  # Nachfragespitze

v1.to_csv("data/forecast_v1.csv", index=False)
v2.to_csv("data/forecast_v2.csv", index=False)
print("OK: data/forecast_v1.csv, data/forecast_v2.csv")
