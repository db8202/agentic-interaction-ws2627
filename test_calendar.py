import os
import json
from dotenv import load_dotenv
from agent.calendar import get_calendar_day

# 1. Konfiguration laden
load_dotenv(".env")

# 2. Kalender-URL aus der Konfiguration lesen
data_base_url = os.environ["DATA_BASE_URL"]

# 3. Kalenderfunktion aufrufen
result = get_calendar_day(
    "2026-10-29",
    data_base_url
)

# 4. Ergebnis lesbar ausgeben
print(json.dumps(result, indent=2, ensure_ascii=False))
