import sys #infos zu systemspezifischen parametern
import uuid #erstellen von universal unique identifier

from agent.runlog import write_log

def main():
    #eindeutige ID fuer diesen Lauf erstellen
    run_id=str(uuid.uuid4())

    # Benutzerfrage aus der Kommandozeile lesen
    task = " ".join(sys.argv[1:]).strip()

    #Logging fuer die Benutzerfragen
    write_log(
        run_id=run_id,
        event="user_task",
        args={"task":task}
    )

    # Pruefen, ob eine Benutzerfrage vorhanden ist
    # Wenn Benutzeranfrage nicht da, dann Error ereignis
    if not task:
        message = "Fehler: Es fehlt die Frage für die KI"
        write_log(
            run_id=run_id,
            event="error",
            args={"message": message},
            ok=False
        )

        print(message)
        sys.exit(1)

    print("Benutzeranfrage:", task)

if __name__ == "__main__":
    main()
