import sys
import os
import json
import uuid
import time

from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

from agent.model import request_calendar_tool
from agent.calendar import get_calendar_day
from agent.runlog import write_log


def elapsed_ms(start):
    return round((time.perf_counter() - start) * 1000, 3)


def main():
    run_id = str(uuid.uuid4())

    # 1. Benutzerfrage lesen und protokollieren
    start = time.perf_counter()
    task = " ".join(sys.argv[1:]).strip()

    write_log(
        run_id=run_id,
        event="user_task",
        args={"task": task},
        duration_ms=elapsed_ms(start)
    )

    model = None
    start = time.perf_counter()

    try:
        if not task:
            raise ValueError("Bitte eine Kalenderfrage eingeben.")

        # 2. Konfiguration laden
        project_dir = Path(__file__).resolve().parent.parent
        load_dotenv(project_dir / ".env", override=False)

        model = os.getenv("MODEL")
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        data_url = os.getenv("DATA_BASE_URL")

        if not all([model, api_key, base_url, data_url]):
            raise ValueError("Konfiguration unvollstaendig.")

        # 3. Groq fordert das Kalender-Tool an
        start = time.perf_counter()
        response = request_calendar_tool(task)
        model_duration = elapsed_ms(start)

        tool_calls = response.choices[0].message.tool_calls or []

        if not tool_calls:
            raise RuntimeError("Das Modell hat kein Tool aufgerufen.")

        # 4. Gespraechsverlauf vorbereiten
        messages = [
            {
                "role": "system",
                "content": (
                    "Du bist ein Kalenderassistent. "
                    "Verwende das Kalender-Tool fuer Kalenderfragen. "
                    "Erfinde keine Termine."
                )
            },
            {"role": "user", "content": task},
            response.choices[0].message
        ]

        # 5. Alle angeforderten Kalender-Tools ausfuehren
        for call in tool_calls:

            if call.function.name != "get_calendar_day":
                raise ValueError("Unbekanntes Tool.")

            arguments = json.loads(call.function.arguments)

            if not isinstance(arguments, dict):
                raise ValueError("Ungueltige Tool-Argumente.")

            if not isinstance(arguments.get("date"), str):
                raise ValueError("Datum fehlt im Tool-Aufruf.")

            write_log(
                run_id=run_id,
                event="tool_call",
                tool=call.function.name,
                args=arguments,
                model=model,
                duration_ms=model_duration
            )

            start = time.perf_counter()

            result = get_calendar_day(
                arguments["date"],
                data_url
            )

            write_log(
                run_id=run_id,
                event="tool_result",
                tool=call.function.name,
                args={"result": result},
                model=model,
                duration_ms=elapsed_ms(start)
            )

            # Ergebnis fuer Groq bereitstellen
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

        # 6. Zweiter Modellaufruf mit den Kalenderdaten
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        start = time.perf_counter()

        final_response = client.chat.completions.create(
            model=model,
            messages=messages
        )

        answer = final_response.choices[0].message.content

        if not answer:
            raise RuntimeError("Keine Antwort vom Modell erhalten.")

        write_log(
            run_id=run_id,
            event="final",
            args={"answer": answer},
            model=model,
            duration_ms=elapsed_ms(start)
        )

        print(answer)
        return 0

    except Exception as error:
        write_log(
            run_id=run_id,
            event="error",
            args={
                "type": type(error).__name__,
                "message": str(error)
            },
            ok=False,
            model=model,
            duration_ms=elapsed_ms(start)
        )

        print(f"Fehler: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())