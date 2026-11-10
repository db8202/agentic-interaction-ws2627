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
    """Rechnet die vergangene Zeit in Millisekunden um."""
    return round((time.perf_counter() - start) * 1000, 3)


def main():
    # 1. Benutzerfrage aus PowerShell lesen und einen Loglauf starten.
    run_id = str(uuid.uuid4())
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
            raise ValueError("Bitte eine Frage eingeben.")

        # 2. Konfiguration aus .env laden.
        project_dir = Path(__file__).resolve().parent.parent
        load_dotenv(project_dir / ".env", override=False)

        model = os.getenv("MODEL")
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        data_url = os.getenv("DATA_BASE_URL")

        if not all([model, api_key, base_url, data_url]):
            raise ValueError("Konfiguration unvollstaendig.")

        # 3. ERSTER Groq-Aufruf: entweder Textantwort oder Tool-Anforderung.
        start = time.perf_counter()
        response = request_calendar_tool(task)
        model_duration = elapsed_ms(start)
        tool_calls = response.choices[0].message.tool_calls or []

        # 4A. KEIN Tool: allgemeine Frage sofort beantworten.
        if not tool_calls:
            answer = response.choices[0].message.content
            if not answer:
                raise RuntimeError("Keine Antwort vom Modell erhalten.")

            write_log(
                run_id=run_id,
                event="final",
                args={"answer": answer},
                model=model,
                duration_ms=model_duration
            )
            print(answer)
            return 0

        # 4B. TOOL vorhanden: fuer die zweite Modellanfrage vorbereiten.
        messages = [
            {
                "role": "system",
                "content": (
                    "Du bist ein hilfreicher KI-Assistent. "
                    "Beantworte Fragen anhand der gegebenen Tool-Ergebnisse. "
                    "Erfinde keine Termine. "
                    "Bei status no_data liegen keine Kalenderdaten vor; "
                    "das bedeutet nicht, dass keine Termine existieren."
                )
            },
            {"role": "user", "content": task},
            response.choices[0].message
        ]

        # 5. Groq fordert ein Tool an, Python fuehrt es tatsaechlich aus.
        for call in tool_calls:
            if call.function.name != "get_calendar_day":
                raise ValueError("Unbekanntes Tool.")

            # 'loads': JSON-Text -> Python-Dictionary, z. B. {"date":"2026-10-29"}.
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
            result = get_calendar_day(arguments["date"], data_url)

            write_log(
                run_id=run_id,
                event="tool_result",
                tool=call.function.name,
                args={"result": result},
                model=model,
                duration_ms=elapsed_ms(start)
            )

            # 'dumps': Python-Dictionary -> JSON-Text fuer die Modellnachricht.
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

        # 6. ZWEITER Groq-Aufruf: Antwort aus den Kalenderdaten formulieren.
        client = OpenAI(api_key=api_key, base_url=base_url)
        start = time.perf_counter()
        final_response = client.chat.completions.create(
            model=model,
            messages=messages
        )

        answer = final_response.choices[0].message.content
        if not answer:
            raise RuntimeError("Keine Antwort vom Modell erhalten.")

        # 7. Fertige Antwort protokollieren und im Terminal ausgeben.
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
        # 8. Fehler protokollieren und den Lauf mit Exit-Code 1 beenden.
        write_log(
            run_id=run_id,
            event="error",
            args={"type": type(error).__name__, "message": str(error)},
            ok=False,
            model=model,
            duration_ms=elapsed_ms(start)
        )
        print(f"Fehler: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
