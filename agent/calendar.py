
import json
from datetime import date
from urllib.request import urlopen
from urllib.error import HTTPError


def get_calendar_day(day, data_base_url):
    # Datum pruefen ob es gueltig ist
    parsed_date = date.fromisoformat(day)

    if parsed_date.isoformat() != day:
        raise ValueError("Datum muss YYYY-MM-DD sein.")

    # URL der Kalenderdatei zusammenbauen
    url = f"{data_base_url.rstrip('/')}/calendar/{day}.json"

    try:
        # Kalenderdaten ueber HTTP abrufen
        with urlopen(url, timeout=15) as response:
            calendar = json.load(response)

        return {
            "status": "ok",
            "date": day,
            "calendar": calendar
        }

    except HTTPError as error:
        if error.code == 404:
            return {
                "status": "no_data",
                "date": day
            }

        raise
