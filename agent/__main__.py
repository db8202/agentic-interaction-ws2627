
"""Steuert den Kalender-Agenten und seinen Agent Loop."""

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
MAX_TOOL_CALLS_PER_STEP = 5


def elapsed_ms(start):
    """Berechnet die verstrichene Zeit in Millisekunden."""
    return round((time.perf_counter() - start) * 1000, 3)


def main():
    # Jeder Programmlauf bekommt eine eigene ID fuer seine Logdatei.
    run_id = str(uuid.uuid4())
    run_start = time.perf_counter()
    task = " ".join(sys.argv[1:]).strip()
    model = None

    try:
        write_log(
            run_id=run_id,
            event="user_task",
            args={"task": task},
            duration_ms=elapsed_ms(run_start)
        )

        # SCHUTZ 1: Leere Eingaben nicht an Groq senden.
        if not task:
            raise ValueError("Bitte eine Frage eingeben.")

        # Konfiguration aus dem Projektverzeichnis laden.
        project_dir = Path(__file__).resolve().parent.parent
        load_dotenv(project_dir / ".env", override=False)

        model = os.getenv("MODEL")
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        data_url = os.getenv("DATA_BASE_URL")

        # SCHUTZ 2: Fehlende Konfiguration vor dem ersten API-Aufruf erkennen.
        if not all([model, api_key, base_url, data_url]):
            raise ValueError("Konfiguration unvollstaendig.")

        # SCHUTZ 3: Das Schrittlimit verhindert unbegrenzte Modellaufrufe.
        # Auch ungueltige Werte (z. B. 'abc' oder 0) fuehren zu einem Fehler.
        max_steps = int(os.getenv("AGENT_MAX_STEPS", str(MAX_MODEL_STEPS)))
        if not 1 <= max_steps <= 20:
            raise ValueError("AGENT_MAX_STEPS muss zwischen 1 und 20 liegen.")

        # Ein Gespraechsverlauf fuer den gesamten Programmlauf.
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task}
        ]

        # SCHUTZ 4: Gleiche Kalenderdaten pro Lauf nicht mehrfach herunterladen.
        # Nur erfolgreich zurueckgegebene Resultate werden zwischengespeichert.
        calendar_cache = {}

        # Agent Loop: Ein Durchlauf entspricht einem Aufruf von request_model().
        for step in range(1, max_steps + 1):

            # Nachvollziehbarkeit: Welche Nachrichten geben wir an Groq weiter?
            # ACHTUNG: Dieser Eintrag entsteht VOR der API-Anfrage und
            # beweist noch keine erfolgreiche Uebermittlung.
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

            model_start = time.perf_counter()
            response = request_model(messages)
            model_duration = elapsed_ms(model_start)

            # SCHUTZ 5: Eine ungewoehnlich leere API-Antwort kontrolliert abfangen.
            if not response.choices:
                raise RuntimeError("Groq hat keine Antwortmoeglichkeit geliefert.")

            choice = response.choices[0]
            message = choice.message
            tool_calls = message.tool_calls or []

            # Die tatsaechliche Modellantwort separat vom Anfrageversuch loggen.
            write_log(
                run_id=run_id,
                event="model_response",
                args={
                    "step": step,
                    "finish_reason": choice.finish_reason,
                    "tool_count": len(tool_calls)
                },
                model=model,
                duration_ms=model_duration
            )

            # SCHUTZ 6: Abgeschnittene Generierungen nicht weiterverarbeiten.
            if choice.finish_reason == "length":
                raise RuntimeError("Modellantwort wurde wegen Laengenlimit abgeschnitten.")

            # Ohne Tool-Anforderung erwartet unser Agent eine finale Antwort.
            if not tool_calls:
                # SCHUTZ 7: Nur einen regulaeren Modellabschluss akzeptieren.
                if choice.finish_reason != "stop":
                    raise RuntimeError(
                        f"Modell nicht regulaer beendet: {choice.finish_reason}"
                    )

                answer = message.content

                # SCHUTZ 8: Kein leeres oder nur aus Leerzeichen bestehendes Ergebnis.
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

            # SCHUTZ 9: Letzten erlaubten Schritt nicht als Erfolg ausgeben,
            # wenn danach noch Tool-Ergebnisse ausgewertet werden muessten.
            if step == max_steps:
                raise RuntimeError(
                    f"Schrittlimit erreicht ({max_steps} Modellaufrufe): "
                    "Es werden noch Tools angefordert."
                )

            # SCHUTZ 10: Die Zahl der Tools PRO Modellantwort begrenzen.
            if len(tool_calls) > MAX_TOOL_CALLS_PER_STEP:
                raise RuntimeError(
                    f"Zu viele Tool-Aufrufe in Schritt {step}: "
                    f"{len(tool_calls)} statt maximal {MAX_TOOL_CALLS_PER_STEP}."
                )

            # SCHUTZ 11: Jede Tool-Antwort braucht eine gueltige Call-ID.
            # Ohne diese ID koennen Ergebnisse nicht zugeordnet werden.
            for call in tool_calls:
                if (
                    not isinstance(call.id, str)
                    or not call.id
                    or call.function is None
                ):
                    raise RuntimeError("Unvollstaendige Tool-Anforderung von Groq.")

            # Erst die Modellnachricht mit ALLEN Tool-Anforderungen speichern.
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

            # Innere Schleife: Die angeforderten Tools NACHEINANDER ausfuehren.
            for call in tool_calls:
                tool_name = call.function.name
                raw_args = call.function.arguments

                # SCHUTZ 12: Fehlerhaftes JSON darf nicht den Agenten beenden.
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
                    # SCHUTZ 13: Nur ausdruecklich erlaubte Tools ausfuehren.
                    if tool_name != "get_calendar_day":
                        raise ValueError(f"Unbekanntes Tool: {tool_name}")

                    # SCHUTZ 14: Argumente muessen ein JSON-Objekt sein.
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool-Argumente sind kein JSON-Objekt.")

                    # SCHUTZ 15: Das benoetigte Datum muss ein String sein.
                    if not isinstance(arguments.get("date"), str):
                        raise ValueError("Datum fehlt oder ist kein String.")

                    day = arguments["date"]

                    if day in calendar_cache:
                        result = calendar_cache[day]
                        source = "cache"
                    else:
                        # HIER wird das echte Python-Tool ausgefuehrt.
                        # calendar.py prueft zusaetzlich das ISO-Datumsformat.
                        result = get_calendar_day(day, data_url)
                        calendar_cache[day] = result
                        source = "api"

                    ok = True

                except Exception as error:
                    # SCHUTZ 16: Ein Tool-Fehler beendet nicht die anderen Tools.
                    # Groq erhaelt stattdessen eine strukturierte Fehlermeldung.
                    result = {
                        "status": "error",
                        "type": type(error).__name__,
                        "message": str(error)
                    }
                    ok = False
                    source = "error"

                write_log(
                    run_id=run_id,
                    event="tool_result",
                    tool=tool_name,
                    args={"result": result, "source": source},
                    ok=ok,
                    model=model,
                    duration_ms=elapsed_ms(tool_start)
                )

                # Die Call-ID verknuepft jedes Ergebnis mit seiner Anforderung.
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

            # Danach beginnt der naechste Modellschritt mit den neuen Nachrichten.

        # Zusaetzliche Absicherung, falls die Schleife unerwartet auslaeuft.
        raise RuntimeError("Schrittlimit ohne finale Antwort erreicht.")

    except Exception as error:
        # SCHUTZ 17: Endgueltige Fehler mit Exit-Code 1 beenden.
        # SCHUTZ 18: Auch bei defektem Logging die Fehlermeldung ausgeben.
        try:
            write_log(
                run_id=run_id,
                event="error",
                args={"type": type(error).__name__, "message": str(error)},
                ok=False,
                model=model,
                duration_ms=elapsed_ms(run_start)
            )
        except Exception as log_error:
            print(f"Auch Logging fehlgeschlagen: {log_error}", file=sys.stderr)

        print(f"Fehler: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
