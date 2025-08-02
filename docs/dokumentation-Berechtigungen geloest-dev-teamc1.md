🚀 GCP Cloud Build Trigger mit eigenem Service Account – Schritt-für-Schritt

1. Ziel

Automatisierte Builds in GCP mit einem eigenen, minimal berechtigten Service Account für maximale Sicherheit und Kontrolle.

2. Voraussetzungen

Du hast Zugriff auf das GCP-Projekt als „Inhaber“ oder mit passenden IAM-Rechten.

Cloud Build API & Artifact Registry sind aktiviert.

Dein Quell-Repo (z. B. GitHub) ist verbunden.

3. Schritte im Detail

A. Eigenen Service Account anlegen

Navigation:Google Cloud Console → IAM & Verwaltung → Dienstkonten

Neues Dienstkonto erstellen

Name: z. B. build-trigger

ID: z. B. build-trigger

Beschreibung: z. B. Service Account für Cloud Build Trigger

(Optional) Mitglieder als „Dienstkontonutzer“ eintragen

Trage dich selbst (und ggf. andere Teammitglieder) direkt beim Erstellen als Dienstkontonutzer ein.

Deine E-Mail (z. B. dein.name@gmail.com).

B. Benötigte Rollen zuweisen

Entweder direkt beim Anlegen des Service Accounts oder im Anschluss unter „IAM & Verwaltung > IAM“.

Dem neuen Service Account folgende Rollen geben:

roles/cloudbuild.builds.builder (Cloud-Build-Dienstkonto)

roles/artifactregistry.writer (Artifact Registry Writer)

roles/storage.objectViewer (Storage-Objekt-Betrachter)

roles/iam.serviceAccountUser (Dienstkontonutzer)(Wichtig: Dir selbst auf dieses Konto zuweisen!)

Je nach Bedarf:

roles/secretmanager.secretAccessor (falls Zugriff auf Secrets)

Repository-spezifische Rollen, z. B. roles/source.reader oder „Secure Source Manager Repository Reader“ für Zugriff auf dein GitHub-Repo

C. Build Trigger anlegen

Empfohlene Variante (empfohlen für Logs-Bucket & maximale Flexibilität):

1. cloudbuild.yaml im Repo anlegen (Beispiel: vollständige Pipeline mit Logs-Bucket!)

steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'us-central1-docker.pkg.dev/$PROJECT_ID/pear-images/email-processor:latest', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'us-central1-docker.pkg.dev/$PROJECT_ID/pear-images/email-processor:latest']
  - name: 'gcr.io/cloud-builders/gcloud'
    id: 'Deploy Cloud Run Service'
    args:
      - 'run'
      - 'deploy'
      - 'process-pear-emails'
      - '--image'
      - 'us-central1-docker.pkg.dev/$PROJECT_ID/pear-images/email-processor:latest'
      - '--platform'
      - 'managed'
      - '--region'
      - 'us-central1'
      - '--allow-unauthenticated'
      - '--set-env-vars'
      - 'FASTAPI_API_URL=http://34.46.6.30:8000'
      - '--no-cpu-throttling'
      - '--min-instances'
      - '0'
      - '--max-instances'
      - '1'
images:
  - 'us-central1-docker.pkg.dev/$PROJECT_ID/pear-images/email-processor:latest'
options:
  logging: CLOUD_LOGGING_ONLY
logsBucket: gs://build-team-storage

(Pfad, Tag, Cloud Run Name, und Umgebungsvariablen ggf. anpassen!)

2. Build Trigger im UI anlegen

Trigger-Typ: Cloud Build-Konfigurationsdatei (YAML oder JSON)

Datei: Pfad zu deiner cloudbuild.yaml

Dienstkonto: build-trigger@pear-dev-teamv1.iam.gserviceaccount.com

Jetzt erscheint das Feld fürs Logs-Bucket oder es wird über logsBucket: in der YAML gesetzt.

3. Trigger speichern und testen

Commit auf main (oder anderen Branch)

Build läuft, Logs landen im angegebenen GCS-Bucket

D. Build testen

Push in den konfigurierten Branch machen

Trigger sollte automatisch laufen, das Image wird gebaut und in die Artifact Registry gepusht.

4. Vorteile dieses Vorgehens

Sicherheit: Kein Overprovisioning – nur explizit zugewiesene Rechte

Nachvollziehbarkeit: Auditierbar, wer und was Aktionen im Build ausgeführt hat

Skalierbarkeit: Eigenes Konto für Builds – leichter zu rotieren, entfernen, automatisieren

5. Troubleshooting

Dienstkonto nicht auswählbar:→ Eigenes Konto erstellen (kein „Google managed“), dir selbst als Dienstkontonutzer eintragen, Seite ggf. neuladen.

Berechtigungsfehler beim Build:→ Fehlende Rolle beim Service Account nachtragen (z. B. Artifact Registry Writer, Secret Accessor).

Fehler bei Nutzung eines eigenen Service Accounts:→ Fehlermeldung: "if 'build.service_account' is specified, the build must either (a) specify 'build.logs_bucket', (b) use the REGIONAL_USER_OWNED_BUCKET build.options.default_logs_bucket_behavior option, or (c) use either CLOUD_LOGGING_ONLY / NONE logging options"

2. Alternativ: Eigenes GCS-Bucket für Logs anlegen

Eigenes Bucket erstellen:

Google Cloud Console → Cloud Storage → Buckets → "Bucket erstellen"

Einen aussagekräftigen Namen vergeben (z. B. build-logs-<projektname>)

Region passend zur Build-Region auswählen

Dem Service Account Berechtigung auf das Bucket geben:

Rolle: roles/storage.objectAdmin oder mindestens roles/storage.objectCreator für das Log-Bucket

Entweder via Console unter "Berechtigungen" oder per gcloud:

gcloud storage buckets add-iam-policy-binding gs://build-logs-<projektname> \
  --member="serviceAccount:build-trigger@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/storage.objectCreator"

Im Build-Trigger das Logs Bucket angeben:

Im Build-Trigger unter "Erweiterte Einstellungen" ("advanced options") das Feld logs bucket auf das neue Bucket setzen, z. B.: gs://build-logs-<projektname>

Trigger speichern und testen!

Optional: CLI-Snippet für Profis

gcloud iam service-accounts create build-trigger --display-name="Build Trigger Service Account"

gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:build-trigger@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"

gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:build-trigger@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:build-trigger@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

gcloud iam service-accounts add-iam-policy-binding build-trigger@<PROJECT_ID>.iam.gserviceaccount.com \
  --member="user:deine@email.de" \
  --role="roles/iam.serviceAccountUser"

Diese Anleitung kannst du direkt ins Wiki oder als PDF speichern. Melde dich, wenn du noch Textbausteine für die Team-Schulung brauchst oder noch weitere Automatisierungsschritte möchtest!

Da es weitere Probleme gab, hier die weitere Lösungsschritte:

1. Übersicht
Dieser Teil der Dokumentation beschreibt die Einrichtung einer automatisierten CI/CD-Pipeline für das PEAR-Projekt mit Google Cloud Build. Der Trigger baut automatisch Docker-Images, wenn Code in den main-Branch des GitHub-Repositories gepusht wird.

2. Repository-Struktur

PEARv2/├── pear-backend/        # Backend-Code und Dockerfile│   └── Dockerfile       # Docker-Build-Anweisungen├── cloudbuild.yaml      # Cloud Build Konfiguration└── ...
3. Cloud Build Konfiguration
Die cloudbuild.yaml im Repository-Root definiert den Build-Prozess:


steps:  - name: 'gcr.io/cloud-builders/docker'    args: ['build', '-t', 'gcr.io/pear-dev-teamv1/dev-team-pear-agenten:$COMMIT_SHA', '-t', 'gcr.io/pear-dev-teamv1/dev-team-pear-agenten:latest', './pear-backend']images:  - 'gcr.io/pear-dev-teamv1/dev-team-pear-agenten:$COMMIT_SHA'  - 'gcr.io/pear-dev-teamv1/dev-team-pear-agenten:latest'options:  logging: CLOUD_LOGGING_ONLY  default_logs_bucket_behavior: REGIONAL_USER_OWNED_BUCKET
Konfigurationsdetails:
Build-Schritt: Führt Docker Build für das Backend-Verzeichnis aus
Tags: Erstellt zwei Tags für jedes Image (Commit-SHA und 'latest')
Logging: Verwendet Cloud Logging mit regionalem Bucket
4. Voraussetzungen
Service Account-Berechtigungen
Der Service Account build-trigger@pear-dev-teamv1.iam.gserviceaccount.com benötigt folgende Rollen:

Artifact Registry Writer
Cloud-Build-Dienstkonto
Logs Bucket Writer
Logs Writer
Storage Object Creator
Developer Connect Read Token Accessor
Secure Source Manager Repository Reader
GitHub-Integration
Repository muss mit Google Cloud Build verbunden sein
Verbindung über "GitHub (Cloud Build-GitHub-Anwendung)" herstellen
OAuth-Authentifizierung durchführen
5. Build-Trigger-Konfiguration
Der Trigger dev-team-trigger ist wie folgt konfiguriert:

Event: Push zum Branch main
Repository: HystDevTV/PEARv2
Build-Konfiguration: cloudbuild.yaml
Service Account: build-trigger@pear-dev-teamv1.iam.gserviceaccount.com
Region: us-central1
6. Automatisierter Workflow
Code-Änderungen werden in den main-Branch gepusht
Build-Trigger wird automatisch ausgelöst
Cloud Build erstellt Docker-Image nach den Anweisungen in der cloudbuild.yaml
Fertiges Image wird in die Artifact Registry gepusht (mit beiden Tags)
Build-Status und Logs sind in der Cloud Console verfügbar
7. Fehlerbehebung
Häufige Probleme:

Fehlende Service Account-Berechtigungen für Logging
Ungültige Logging-Konfiguration bei Verwendung eines benutzerdefinierten Service Accounts
Repository-Verbindungsprobleme zwischen GitHub und Cloud Build
Bei Verbindungsproblemen muss die GitHub-Integration möglicherweise neu autorisiert werden.

Letzte Aktualisierung: 24. Juli 2025

Erweiterte Dokumentation: PEAR-Projekt
1. Systemübersicht
Das PEAR-Projekt besteht aus zwei Hauptkomponenten:

CI/CD-Pipeline mit Google Cloud Build für automatisierte Docker-Image-Erstellung
Agentensystem zur automatisierten Aufgabenverwaltung und -bearbeitung
Diese Dokumentation beschreibt die Einrichtung und Funktionsweise beider Komponenten.

2. Repository-Struktur

PEARv2/├── cloudbuild.yaml            # Cloud Build Konfiguration├── team.py                    # Agenten-System zur Aufgabenverwaltung├── pear-backend/              # Backend-Code und Dockerfile│   └── Dockerfile             # Docker-Build-Anweisungen└── docs/                      # Projektdokumentation    └── dokumentation-pear.md  # Ausführliche Dokumentation
3. CI/CD-Pipeline
3.1 Cloud Build Konfiguration
Die cloudbuild.yaml definiert den automatisierten Build-Prozess:


steps:  - name: 'gcr.io/cloud-builders/docker'    args: ['build', '-t', 'gcr.io/pear-dev-teamv1/dev-team-pear-agenten:$COMMIT_SHA',            '-t', 'gcr.io/pear-dev-teamv1/dev-team-pear-agenten:latest', './pear-backend']images:  - 'gcr.io/pear-dev-teamv1/dev-team-pear-agenten:$COMMIT_SHA'  - 'gcr.io/pear-dev-teamv1/dev-team-pear-agenten:latest'options:  logging: CLOUD_LOGGING_ONLY  default_logs_bucket_behavior: REGIONAL_USER_OWNED_BUCKET
3.2 Service Account Berechtigungen
Der Service Account build-trigger@pear-dev-teamv1.iam.gserviceaccount.com benötigt folgende Rollen:

Artifact Registry Writer
Cloud-Build-Dienstkonto
Logs Bucket Writer
Logs Writer
Storage Object Creator
Developer Connect Read Token Accessor
Secure Source Manager Repository Reader
3.3 Trigger-Konfiguration
Event: Push zum Branch main
Repository: HystDevTV/PEARv2
Build-Konfiguration: cloudbuild.yaml
Service Account: build-trigger@pear-dev-teamv1.iam.gserviceaccount.com
Region: us-central1
4. Agentensystem (team.py)
4.1 Architektur
Das Agentensystem besteht aus zwei Hauptklassen:

Agent: Repräsentiert einen KI-Agenten mit spezifischer Rolle
TaskManager: Verwaltet Aufgaben und deren Zuweisung an Agenten
4.2 Agentenrollen
Das System verwendet vier Agententypen:

Infrastructure Agent: Bearbeitet CI/CD- und Infrastrukturaufgaben (Kategorie A)
Feature Agent: Implementiert Features und Automatisierungen (Kategorie B)
Workflow Agent: Optimiert Entwicklungsprozesse und Dokumentation (Kategorie C)
Onboarding Agent: Erstellt Anleitungen und Wissensdokumente (Kategorie D)
4.3 Aufgabenkategorisierung
Tasks werden automatisch kategorisiert basierend auf:

GitHub Issue-Labels
Schlüsselwörtern in der Beschreibung
Prioritätsmarkierungen im Titel
4.4 GitHub-Integration
Automatisches Abrufen offener Issues als Aufgaben
Kategorisierung der Issues nach A, B, C, D
Erstellung von Kommentaren bei Aufgabenabschluss
Hinzufügen des Labels "completed-by-agent"
5. Voraussetzungen und Konfiguration
5.1 Benötigte Python-Pakete

pip install PyGithub google-cloud-storage
5.2 Umgebungsvariablen
GITHUB_TOKEN: Persönliches Zugriffstoken für die GitHub API
5.3 Google Cloud Konfiguration
Google Cloud-Projekt: pear-dev-teamv1
Artifact Registry: gcr.io/pear-dev-teamv1/dev-team-pear-agenten
6. Betriebsablauf
6.1 CI/CD-Pipeline
Code-Änderungen werden in den main-Branch gepusht
Cloud Build-Trigger wird automatisch ausgelöst
Docker-Image wird gebaut und in die Artifact Registry gepusht
6.2 Agentensystem
Ausführung von team.py
Agenten werden initialisiert und registriert
Offene Issues werden aus GitHub abgerufen
Aufgaben werden nach Kategorie und Priorität an Agenten zugewiesen
Agenten bearbeiten Aufgaben und aktualisieren Issues
7. Weiterentwicklung
7.1 Erweiterung der Agent-Funktionalitäten
Implementierung spezifischer Logik in den _process_*_task Methoden
Integration von KI-Modellen für komplexe Aufgaben
7.2 Container-Integration
Erweiterung der from_container-Methode für echte Container-Nutzung
Spezifische Container-Images für verschiedene Agentenrollen
7.3 Parallelverarbeitung
Mehrere Agenten pro Rolle für gleichzeitige Aufgabenbearbeitung
Load-Balancing zwischen Agenten
7.4 Reporting
Erstellung von Fortschrittsberichten
Visualisierung des Team-Fortschritts
Letzte Aktualisierung: 24. Juli 2025