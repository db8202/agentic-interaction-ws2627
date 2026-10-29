
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def request_calendar_tool(task):
    # Konfiguration laden
    project_dir = Path(__file__).resolve().parent.parent
    load_dotenv(project_dir / ".env", override=False)

    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("MODEL")

    if not all([base_url, api_key, model]):
        raise ValueError("Modellkonfiguration unvollstaendig.")

    # API-Client erstellen
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    # Kalenderfunktion fuer das Modell beschreiben
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
                "required": ["date"]
            }
        }
    }]

    # Modell aufrufen
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Du bist ein Kalenderassistent. "
                    "Verwende das Kalender-Tool fuer Kalenderfragen."
                )
            },
            {
                "role": "user",
                "content": task
            }
        ],
        tools=tools,
        tool_choice="required"
    )

    return response
