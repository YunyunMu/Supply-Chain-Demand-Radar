import pandas as pd
import streamlit as st

from ai_explain import explain
from analysis import compare, part_summary

st.set_page_config(page_title="Abruf-Radar", layout="wide")
st.title("📡 Abruf-Radar")
st.caption("Frühwarnsystem für Änderungen in Kunden-Lieferabrufen (EDI-Prognosen)")

# --- Schritt 1: Daten laden ---
with st.sidebar:
    st.header("1 · Daten")
    use_sample = st.toggle("Beispieldaten verwenden", value=True)
    if use_sample:
        old = pd.read_csv("data/forecast_v1.csv", parse_dates=["week"])
        new = pd.read_csv("data/forecast_v2.csv", parse_dates=["week"])
    else:
        f1 = st.file_uploader("Alte Prognose (CSV)", type="csv")
        f2 = st.file_uploader("Neue Prognose (CSV)", type="csv")
        if not (f1 and f2):
            st.info("Bitte beide Dateien hochladen.")
            st.stop()
        old = pd.read_csv(f1, parse_dates=["week"])
        new = pd.read_csv(f2, parse_dates=["week"])
    st.header("2 · Empfindlichkeit")
    threshold = st.slider("Abweichung ab (%)", 10, 60, 25) / 100

m = compare(old, new, threshold)
summary = part_summary(m)

# --- Schritt 2: Überblick (KPIs) ---
c1, c2, c3 = st.columns(3)
c1.metric("Teile mit hohem Risiko", int((summary.risk == "hoch").sum()))
c2.metric("Auffällige Wochen", int(m.flag.sum()))
c3.metric("Ø Prognoseänderung", f"{m.delta_pct.abs().mean():.1%}")

st.subheader("Übersicht nach Teilenummer")
st.dataframe(
    summary.style.format({"total_delta_pct": "{:+.0%}", "volatility": "{:.0%}", "max_dev": "{:.0%}"}),
    use_container_width=True, hide_index=True,
)

# --- Schritt 3: Drill-down + KI ---
st.subheader("Detailansicht")
part = st.selectbox("Teilenummer", summary.part_no)
detail = m[m.part_no == part].sort_values("week")
st.line_chart(detail.set_index("week")[["qty_old", "qty_new"]])

if st.button("🤖 KI-Analyse erstellen"):
    row = summary[summary.part_no == part].iloc[0].to_dict()
    weekly = detail[["week", "qty_old", "qty_new", "delta_pct"]].round(2).to_dict("records")
    with st.spinner("Analysiere ..."):
        res = explain(row, weekly)
    st.markdown(f"**Risiko:** {res.get('risk_level')}")
    st.write(res.get("summary"))
    st.markdown("**Mögliche Ursachen**")
    for x in res.get("likely_causes", []):
        st.markdown(f"- {x}")
    st.markdown("**Empfohlene Maßnahmen**")
    for x in res.get("recommended_actions", []):
        st.markdown(f"- {x}")
