import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def request_calendar_tool(task):
    """Fragt Groq: direkte Antwort oder Kalender-Tool-Aufruf?"""

    # 1. Zugangsdaten und Modell aus der .env laden.
    project_dir = Path(__file__).resolve().parent.parent
    load_dotenv(project_dir / ".env", override=False)

    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("MODEL")

    if not all([base_url, api_key, model]):
        raise ValueError("Modellkonfiguration unvollstaendig.")

    # 2. Client fuer die OpenAI-kompatible Groq-Schnittstelle erstellen.
    client = OpenAI(api_key=api_key, base_url=base_url)

    # 3. Tool nur BESCHREIBEN. Ausgefuehrt wird es spaeter in __main__.py.
    tools = [{
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
                "required": ["date"]  # Wenn das Tool gerufen wird, braucht es ein Datum.
            }
        }
    }]

    # 4. Erste Modellanfrage: Groq entscheidet, ob es das Tool benoetigt.
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Du bist ein hilfreicher KI-Assistent. "
                    "Beantworte allgemeine Fragen direkt ohne Werkzeug. "
                    "Wenn eine Frage Kalenderinformationen benoetigt, verwende "
                    "das Tool get_calendar_day. Erfinde keine Termine. "
                    "Wenn fuer eine Kalenderfrage das Datum fehlt, frage danach."
                )
            },
            {"role": "user", "content": task}
        ],
        tools=tools,
        tool_choice="auto"  # WICHTIG: Tool nur bei Bedarf, nicht zwangsweise.
    )

    return response
