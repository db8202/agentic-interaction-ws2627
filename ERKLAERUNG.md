# Kalender-Agent: Code in einem Durchgang verstehen

Es werden **nur** `agent/model.py` und `agent/__main__.py` ersetzt. `agent/calendar.py` und `agent/runlog.py` bleiben unverändert.

## 30-Sekunden-Erklärung

Die Benutzerfrage kommt über `sys.argv` in `__main__.py`. `request_calendar_tool(task)` fragt Groq über die OpenAI-kompatible API an. `model.py` beschreibt das Kalenderwerkzeug und nutzt `tool_choice="auto"`. Bei allgemeinen Fragen antwortet Groq direkt; `__main__.py` loggt und druckt die Antwort. Bei Kalenderfragen liefert Groq eine Tool-Anforderung. `__main__.py` liest die JSON-Argumente mit `json.loads`, validiert Datum und Tool-Namen und ruft `get_calendar_day()` in `calendar.py` tatsächlich auf. Das Ergebnis wird mit `json.dumps` an Groq übermittelt; der zweite Modellaufruf formuliert die Antwort. Jeder Lauf bekommt eine `run_id`, Zeitstempel und Zeitdauern in einer JSONL-Datei.

## Die wichtigsten Codezeilen

| Code | Bedeutung |
|---|---|
| `tool_choice="auto"` | Groq darf selbst entscheiden, ob ein Werkzeug nötig ist. |
| `"required": ["date"]` | Wenn das Kalenderwerkzeug aufgerufen wird, muss das Argument `date` vorhanden sein. **Nicht verwechseln** mit `tool_choice="required"`. |
| `tool_calls = ... or []` | Tool-Anforderungen aus der ersten Modellantwort lesen; sonst leere Liste. |
| `if not tool_calls:` | Normaler LLM-Antwortweg ohne weitere Modellanfrage. |
| `json.loads(...)` | Argumente von JSON-Text in Python-Daten umwandeln. |
| `get_calendar_day(...)` | Tatsächlicher HTTP-Kalenderabruf durch Python, nicht durch Groq. |
| `messages.append({"role": "tool", ...})` | Tool-Ergebnis der ursprünglichen Anforderung über `tool_call_id` zuordnen. |
| `json.dumps(result, ensure_ascii=False)` | Python-Ergebnis als JSON-Text an Groq senden. |
| `client.chat.completions.create(...)` (zweites Mal) | Endgültige Antwort aus den Kalenderdaten formulieren. |
| `write_log(...)` | Ereignisse und Laufzeiten in UTF-8/JSONL protokollieren. |

## Tests in PowerShell

```powershell
cd "$HOME\Desktop\Projekt_Chatbots\agentic-interaction-ws2627"
.\.venv\Scripts\python.exe -m agent "Wie geht es dir?"
.\.venv\Scripts\python.exe -m agent "Welche Termine habe ich am 29.10.2026?"
```

**Erwartete Log-Ereignisse:** allgemeine Frage: `user_task`, `final`; Kalenderfrage: `user_task`, `tool_call`, `tool_result`, `final`.

**Wichtig:** `auto` garantiert allein nicht, dass das Modell bei jeder Kalenderfrage tatsächlich das Tool verwendet. Der Tool-Aufruf muss durch Tests und die Logs überprüft werden. Live-Tests mit dem Groq-API-Key sind hier nicht durchgeführt worden.
