"""Wetter und Zugverbindungen aus der Mock-Datenquelle lesen."""

import json
from datetime import date
from urllib.error import HTTPError
from urllib.request import urlopen


def _check_date(day):
    """Prueft das Datum im Format YYYY-MM-DD."""
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("Datum muss YYYY-MM-DD sein.")
    return day


def _city_slug(city):
    """Wandelt einen Stadtnamen in ein sicheres URL-Kuerzel um."""
    if not isinstance(city, str):
        raise ValueError("Stadt muss ein String sein.")

    slug = city.strip().lower()
    if slug == "munich":
        slug = "muenchen"
    slug = (slug.replace("ä", "ae").replace("ö", "oe")
                .replace("ü", "ue").replace("ß", "ss"))

    if not slug or not slug.isascii() or not slug.isalpha():
        raise ValueError("Ungueltiger Stadtname.")
    return slug


def _fetch_json(path, data_base_url):
    """Laedt JSON; HTTP 404 bedeutet: keine Daten vorhanden."""
    url = f"{data_base_url.rstrip('/')}/{path}"
    try:
        with urlopen(url, timeout=15) as response:
            return {"status": "ok", "data": json.load(response)}
    except HTTPError as error:
        if error.code == 404:
            return {"status": "no_data"}
        raise


def get_weather(city, day, data_base_url):
    """Liest das Wetter fuer eine Stadt und einen Tag."""
    day = _check_date(day)
    city = _city_slug(city)
    result = _fetch_json(f"weather/{city}/{day}.json", data_base_url)
    return {"city": city, "date": day, **result}


def get_train_connections(from_city, to_city, day, data_base_url):
    """Liest Zugverbindungen, bei Bedarf mit Wohnort aus context.json."""
    day = _check_date(day)
    destination = _city_slug(to_city)

    if from_city is None:
        context = _fetch_json("context.json", data_base_url)
        if context["status"] != "ok" or not isinstance(context["data"], dict):
            return {"status": "no_data", "reason": "Startort nicht bestimmbar."}
        from_city = context["data"].get("home")
        if not from_city:
            return {"status": "no_data", "reason": "Wohnort fehlt im Kontext."}

    origin = _city_slug(from_city)
    result = _fetch_json(f"transit/{origin}/{destination}/{day}.json", data_base_url)
    return {"from": origin, "to": destination, "date": day, **result}
