
import json
from agent.model import request_calendar_tool

# Benutzerfrage
task = "Welche Termine habe ich am 29.10.2026?"

# KI-Modell aufrufen
response = request_calendar_tool(task)

# Angeforderte Funktionen anzeigen
tool_calls = response.choices[0].message.tool_calls

if not tool_calls:
    print("Das Modell hat kein Werkzeug angefordert.")
else:
    for call in tool_calls:
        print("Werkzeug:", call.function.name)
        print("Argumente:", json.loads(call.function.arguments))
