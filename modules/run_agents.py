import logging
import sys
import threading
from pathlib import Path

# Fügt das Elternverzeichnis zum Python-Pfad hinzu, damit 'team.py' gefunden wird
sys.path.append(str(Path(__file__).resolve().parent))

# Importiert die notwendigen Klassen und Funktionen aus dem team-Modul
from team import TaskManager, build_team

# Konfiguriert das Logging für dieses Skript
logger = logging.getLogger("PEAR-Orchestrator")


def agent_worker(agent):
    """
    Diese Worker-Funktion wird in einem separaten Thread für jeden Agenten ausgeführt.
    Sie delegiert die gesamte Aufgabenlogik direkt an den Agenten.
    """
    try:
        # Der Agent weiß selbst, wie er seine Aufgaben ausführen muss
        agent.execute_all_tasks()
    except Exception as e:
        # Fängt Fehler ab, die während der Ausführung eines Agenten auftreten
        logger.error(f"Ein Fehler ist im Thread von '{agent.name}' aufgetreten: {e}", exc_info=True)


def run_team_orchestration():
    """
    Die Hauptfunktion, die den gesamten Prozess der Agenten-Orchestrierung steuert.
    """
    logger.info("🚀 Starte PEAR Agenten-System...")
    threads = []

    try:
        # 1. Team und TaskManager initialisieren
        # Die Datenbankverbindung wird hier nicht direkt benötigt, da sie in team.py gekapselt ist.
        team = build_team()
        manager = TaskManager(team)

        # 2. Aufgaben aus GitHub holen und an die Agenten verteilen
        manager.fetch_github_issues()
        manager.assign_tasks()
        
        # 3. Initialen Status ausgeben, bevor die Arbeit beginnt
        manager.print_status(final=False)

        # 4. Agenten-Threads erstellen und starten
        logger.info(f"👥 Starte {len(team)} Agenten in parallelen Threads...")
        for agent in team:
            # Für jeden Agenten wird ein eigener Thread gestartet
            thread = threading.Thread(target=agent_worker, args=(agent,))
            threads.append(thread)
            thread.start()

        # 5. Auf den Abschluss aller Threads warten
        logger.info("⏳ Warte auf den Abschluss aller Agenten-Aufgaben...")
        for thread in threads:
            thread.join()

        # 6. Finalen Statusbericht ausgeben
        logger.info("✨ Alle Agenten haben ihre Arbeit abgeschlossen!")
        manager.print_status(final=True)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Prozess wurde durch den Benutzer (Strg+C) unterbrochen.")
    except Exception as e:
        logger.critical(f"\n❌ Ein kritischer Fehler ist im Hauptprozess aufgetreten: {e}", exc_info=True)


if __name__ == "__main__":
    run_team_orchestration()