
"""Groq-Anbindung und zentrale Anweisungen für unseren Kalender-Agenten."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

SYSTEM_PROMPT = (
    "Du bist ein hilfreicher KI-Assistent. "
    "Beantworte allgemeine Fragen direkt ohne Werkzeug. "
    "Fuer Wetterfragen verwende get_weather, fuer Zugfragen get_train_connections. "
    "Wenn eine Frage beides braucht, verwende beide Werkzeuge. "
    "Nutze die Kuerzel ulm und muenchen (auch fuer Munich/Muenchen). "
    "Fehlt der Startort, lasse from_city weg: Das Tool liest context.json. "
    "Nenne den angenommenen Startort in der Antwort. "
    "Erfinde keine Temperaturen, Zuege oder Abfahrtszeiten. "
    "status no_data bedeutet: keine Daten verfuegbar, nicht: es gibt keine Zuege. "
    "Für Fragen zu Kalenderterminen verwende das Tool get_calendar_day. "
    "Wenn mehrere Tage gefragt sind, rufe das Tool für jeden benötigten Tag auf. "
    "Erfinde keine Termine und verwende keine ausgedachten Kalenderdaten. "
    "Falls das Datum einer Kalenderfrage unklar ist, frage danach. "
    "Bei status no_data liegen keine Kalenderdaten vor; das bedeutet nicht, "
    "dass an diesem Tag sicher keine Termine existieren. "
    "Wenn ein Tool fehlschlägt, berücksichtige die Fehlermeldung, "
    "arbeite wenn möglich weiter und benenne fehlende Informationen. "
    "Wenn alle nötigen Informationen vorliegen oder kein Tool erforderlich ist, "
    "gib eine abschließende Antwort."
)


#    Werkzeugbeschreibung: Groq kennt den Namen und das Datumsargument.
#    Die tatsächliche Python-Funktion wird erst in __main__.py ausgeführt.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_calendar_day",
            "description": "Liest die Kalendertermine eines Tages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Datum im Format YYYY-MM-DD"
                    }
                },
                "required": ["date"]
            }
        }
    }
]


# Zwei neue Tool-Beschreibungen fuer Uebung 4.
TOOLS.extend([
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Liest Wetterdaten fuer einen Ort und Tag (z.B. ulm, muenchen).",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Stadt, z.B. muenchen"},
                    "date": {"type": "string", "description": "Datum YYYY-MM-DD"}
                },
                "required": ["city", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_train_connections",
            "description": (
                "Liest Zugverbindungen zwischen Staedten. "
                "Ohne Startort from_city weglassen: Kontext liefert den Wohnort."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "from_city": {"type": "string", "description": "Optionaler Startort"},
                    "to_city": {"type": "string", "description": "Zielort, z.B. muenchen"},
                    "date": {"type": "string", "description": "Datum YYYY-MM-DD"}
                },
                "required": ["to_city", "date"]
            }
        }
    }
])


def request_model(messages):
    """Sendet den bisherigen Nachrichtenverlauf an Groq und gibt die Antwort zurück."""

    # Zugangsdaten laden. Bereits gesetzte Umgebungsvariablen haben Vorrang.
    project_dir = Path(__file__).resolve().parent.parent
    load_dotenv(project_dir / ".env", override=False)

    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("MODEL")
    if not all([base_url, api_key, model]):
        raise ValueError("Modellkonfiguration unvollständig.")


    #Ein Modellschritt: Groq antwortet direkt ODER fordert Tools an.
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=25.0, max_retries=1)
    return client.chat.completions.create(
        model=model,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )
