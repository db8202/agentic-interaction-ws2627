import json
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

from agent.calendar import get_calendar_day
from agent.model import SYSTEM_PROMPT, TOOLS, request_model
from agent.runlog import write_log


MAX_MODEL_STEPS = 6


def elapsed_ms(start):
    return round((time.perf_counter() - start) * 1000, 3)


def main():
    # 1. Benutzerfrage einlesen
    run_id = str(uuid.uuid4())
    run_start = time.perf_counter()
    task = " ".join(sys.argv[1:]).strip()

    write_log(
        run_id=run_id,
        event="user_task",
        args={"task": task},
        duration_ms=elapsed_ms(run_start)
    )

    model = None

    try:
        if not task:
            raise ValueError("Bitte eine Frage eingeben.")

        # 2. Konfiguration laden.
        project_dir = Path(__file__).resolve().parent.parent
        load_dotenv(project_dir / ".env", override=False)

        model = os.getenv("MODEL")
        data_url = os.getenv("DATA_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")

        if not all([model, data_url, api_key, base_url]):
            raise ValueError("Konfiguration unvollstaendig.")

        max_steps = int(os.getenv("AGENT_MAX_STEPS", str(MAX_MODEL_STEPS)))
        if not 1 <= max_steps <= 20:
            raise ValueError("AGENT_MAX_STEPS muss zwischen 1 und 20 liegen.")

        # 3. Ein gemeinsamer Gespraechsverlauf fuer alle Modellaufrufe.
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task}
        ]

        # 4. Ein Schleifendurchlauf entspricht genau einem Modellaufruf.
        for step in range(1, max_steps + 1):

            # Den tatsaechlich uebergebenen Nachrichtenverlauf protokollieren.
            write_log(
                run_id=run_id,
                event="model_request",
                args={
                    "step": step,
                    "messages": messages,
                    "tools": TOOLS,
                    "tool_choice": "auto"
                },
                model=model
            )

            start = time.perf_counter()
            response = request_model(messages)
            model_duration = elapsed_ms(start)

            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            # 5. Ohne weitere Tools ist die Modellantwort final.
            if not tool_calls:
                answer = message.content
                if not isinstance(answer, str) or not answer.strip():
                    raise RuntimeError("Keine finale Antwort vom Modell erhalten.")

                write_log(
                    run_id=run_id,
                    event="final",
                    args={"step": step, "answer": answer},
                    model=model,
                    duration_ms=model_duration
                )
                print(answer)
                return 0

            # Kein zusaetzlicher Modellaufruf mehr erlaubt.
            if step == max_steps:
                raise RuntimeError(
                    f"Schrittlimit erreicht ({max_steps} Modellaufrufe): "
                    "Das Modell fordert weiterhin Tools an."
                )

            # 6. Die Modellnachricht mitsamt Tool-Anforderungen speichern.
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments
                        }
                    }
                    for call in tool_calls
                ]
            })

            # 7. Alle angeforderten Werkzeuge einzeln ausfuehren.
            for call in tool_calls:
                tool_name = call.function.name
                raw_args = call.function.arguments

                try:
                    arguments = json.loads(raw_args)
                except (ValueError, TypeError):
                    arguments = None

                log_args = (
                    arguments if isinstance(arguments, dict)
                    else {"raw_arguments": raw_args}
                )

                write_log(
                    run_id=run_id,
                    event="tool_call",
                    tool=tool_name,
                    args=log_args,
                    model=model,
                    duration_ms=model_duration
                )

                tool_start = time.perf_counter()

                try:
                    if tool_name != "get_calendar_day":
                        raise ValueError(f"Unbekanntes Tool: {tool_name}")
                    if not isinstance(arguments, dict):
                        raise ValueError(
                            "Ungueltige Tool-Argumente (kein JSON-Objekt)."
                        )
                    if not isinstance(arguments.get("date"), str):
                        raise ValueError("Datum fehlt im Tool-Aufruf.")

                    result = get_calendar_day(arguments["date"], data_url)
                    ok = True

                except Exception as error:
                    # Ein Tool-Fehler wird ans Modell zurueckgemeldet.
                    result = {
                        "status": "error",
                        "type": type(error).__name__,
                        "message": str(error)
                    }
                    ok = False

                write_log(
                    run_id=run_id,
                    event="tool_result",
                    tool=tool_name,
                    args={"result": result},
                    ok=ok,
                    model=model,
                    duration_ms=elapsed_ms(tool_start)
                )

                # Die Tool-Antwort muss zur passenden call.id gehoeren.
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

            # Danach beginnt automatisch der naechste Schleifendurchlauf.

        raise RuntimeError("Schrittlimit ohne finale Antwort erreicht.")

    except Exception as error:
        # 8. Endgueltige Fehler mit Exit-Code 1 dokumentieren.
        write_log(
            run_id=run_id,
            event="error",
            args={"type": type(error).__name__, "message": str(error)},
            ok=False,
            model=model,
            duration_ms=elapsed_ms(run_start)
        )
        print(f"Fehler: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
