import json
from datetime import datetime
from pathlib import Path


def write_log(run_id, event, tool=None, args=None, ok=True, model=None, duration_ms=0):

    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.now()astimezone().isoformat(),
        "run_id": run_id,
        "event": event,
        "tool": tool, 
        "args": args if args is not None else {}, #sollte es kein argument geben wird leere Library ausgegeben(eventuell noch keine Werkzeugargumente)
        "ok": ok,
        "model": model,
        "duration_ms": duration_ms
    }

    log_file = log_dir / f"{run_id}.jsonl"

    with log_file.open("a", encoding="utf-8") as file:  #with schliesst datei nach dem block, a Neue eintraege anhaengen, encoding fuer umlaute
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")    #dumps wandelt Python-dictionary in json-string um
