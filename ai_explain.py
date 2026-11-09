import json
import os

SYSTEM = (
    "Du bist ein erfahrener Supply-Chain-Analyst in der Automobilzulieferindustrie. "
    "Antworte ausschließlich mit gültigem JSON, ohne Markdown, auf Deutsch."
)


def fallback(row: dict, note: str = "(Kein API-Key: keine KI-Analyse)") -> dict:
    """Regelbasierte Erklärung, falls kein API-Key vorhanden ist."""
    direction = "Rückgang" if row["total_delta_pct"] < 0 else "Anstieg"
    return {
        "risk_level": row["risk"],
        "summary": f"{row['part_no']} ({row['customer']}): {direction} der Gesamtmenge um "
                   f"{row['total_delta_pct']:+.0%}, {int(row['flagged_weeks'])} auffällige Wochen.",
        "likely_causes": [note],
        "recommended_actions": ["Rücksprache mit dem Kunden", "Bestände und Kapazität prüfen"],
    }


def build_prompt(row: dict, weekly: list[dict]) -> str:
    return f"""Analysiere die Änderung einer Lieferabruf-Prognose.

KPIs: {json.dumps(row, default=str, ensure_ascii=False)}
Wochendaten (alt vs. neu): {json.dumps(weekly, default=str, ensure_ascii=False)}

Gib JSON zurück mit den Feldern:
- risk_level: "niedrig" | "mittel" | "hoch"
- summary: max. 2 Sätze
- likely_causes: Liste mit max. 3 plausiblen Ursachen (als Hypothesen formuliert)
- recommended_actions: Liste mit max. 3 konkreten nächsten Schritten
Erfinde keine Zahlen, die nicht in den Daten stehen."""


def _call_gemini(prompt: str) -> str:
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    # Modellname in Google AI Studio prüfen: ein Flash-Modell mit kostenlosem Kontingent
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    resp = client.models.generate_content(
        model=model,
        contents=SYSTEM + "\n\n" + prompt,
    )
    return resp.text


def _call_claude(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"),
        max_tokens=800,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def explain(row: dict, weekly: list[dict]) -> dict:
    prompt = build_prompt(row, weekly)
    try:
        if os.getenv("GEMINI_API_KEY"):
            text = _call_gemini(prompt)
        elif os.getenv("ANTHROPIC_API_KEY"):
            text = _call_claude(prompt)
        else:
            return fallback(row)
    except Exception as e:  # z. B. Rate Limit (429) oder falscher Modellname
        return fallback(row, note=f"(API-Fehler: {str(e)[:200]})")

    text = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {**fallback(row), "summary": text[:300]}
