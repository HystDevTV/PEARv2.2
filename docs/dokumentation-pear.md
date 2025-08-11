PEAR – Professionelle Einsatz-, Abrechnungs- und Ressourcenverwaltung Aktueller Projektdokumentation Stand: 11.08.2025 Autor: HystDevTV (Jan Philip Egerton Steinert) Gesamt-App Version (aktueller Stand): 0.1.1 Frontend Version: 0.1.1 (Versioniert über package.json) Backend Version: 0.1.2 (noch in Entwicklung/Initialisierung)

1. Einleitung und Projektüberblick
PEAR ist eine umfassende Webanwendung, die darauf abzielt, die administrativen Aufgaben von Alltagsbegleitern in der Seniorenpflege zu digitalisieren und zu automatisieren. Das Kernziel ist es, die tägliche Routine zu erleichtern, Zeit für die direkte Klientenbetreuung zu schaffen und die Datenverwaltung zu zentralisieren und abzusichern. Die Motivation hinter PEAR umfasst die Reduktion von administrativem Stress, Fehlervermeidung, Zeitersparnis, Verbesserung der Kommunikation sowie die Erhöhung der Datenqualität und -sicherheit. Die Anwendung ist darauf ausgelegt, Funktionen wie Terminlegung, Kundenverwaltung, Routenplanung, Stundenerfassung, Dokumentation und Buchhaltung inklusive Rechnungserstellung, Versand und Ablage zu automatisieren. Dabei hat die DSGVO-Konformität oberste Priorität.
2. Zielgruppe & Stakeholder
    • Primärnutzer: Alltagsbegleiter in der Seniorenpflege. 
    • Sekundärnutzer: Verwaltungspersonal (Büroleitung, Buchhaltung). 
    • Indirekte Stakeholder: Klienten und deren Angehörige, die von der besseren Organisation profitieren. 
    • Lieferanten/Partner: Vermittlungsstellen, die über eine E-Mail-Schnittstelle integriert werden sollen. 
3. Infrastruktur-Setup (Google Cloud Platform)
Das Ziel des Infrastruktur-Setups auf der Google Cloud Platform ist die Bereitstellung einer kosteneffizienten, stabilen und erreichbaren Hosting-Umgebung für PEAR.
    • Google Cloud Projekt: 
        ◦ Der Projektname wurde von "Projekt-Pear" zu "PEARv2" umbenannt, um eine klarere Projektidentifikation zu ermöglichen. Zuvor wurde es auch als "fleissige Birne" bezeichnet. 
        ◦ Es dient als Container für alle Cloud-Ressourcen des Projekts. 
        ◦ Ein dediziertes Google-Konto, als "geschäftliches" Konto registriert, wird für die Trennung von privaten und Projektaktivitäten verwendet. 
    • Virtuelle Maschine (VM): 
        ◦ Dienst: Google Compute Engine. 
        ◦ Instanz-ID: projekt-pear-vm. Diese wurde neu erstellt, nachdem es Probleme mit Vorgänger-VMs gab. Früher war die ID fleissige-birne-vm. 
        ◦ Maschinentyp: Derzeit wird der Typ e2-medium (2 vCPUs, 4 GB RAM) verwendet. Dies ist kostenpflichtig (~0,022 $/Stunde in us-central1), wobei die Kosten vom Startguthaben gedeckt werden, da eine höhere Leistung in der Entwicklungsphase benötigt wird. Zuvor wurde ein e2-micro Maschinentyp genutzt, der zwar dauerhaft kostenlos im "Always Free" Tier war, aber zu Ressourcenmangel führte. 
        ◦ Region: us-central1 (Iowa) wurde beibehalten. 
        ◦ Betriebssystem: Ubuntu 22.04 LTS (Minimal) Jammy, welches schlank und ressourcenschonend ist. 
        ◦ Boot-Laufwerk: Ein Balanced Persistent Disk mit 30 GB Speicherplatz, was dem maximalen Free Tier für Disks entspricht. 
        ◦ Verschlüsselung: Google-verwaltete Verschlüsselungsschlüssel werden standardmäßig verwendet. 
        ◦ Netzwerkschnittstelle: Subnetzwerk default-us-central1 mit interner IP 172.16.0.2. 
        ◦ Firewall-Regeln (Google Cloud): Wichtige Regeln sind eingerichtet, um den Zugriff auf HTTP (Port 80), HTTPS (Port 443), das FastAPI Backend (Port 8000) und die N8N Weboberfläche (Port 5678) zu ermöglichen. 
    • Datenbank: 
        ◦ System: Die Datenbank wurde von PostgreSQL auf MySQL umgestellt, aufgrund hartnäckiger Installationsprobleme mit PostgreSQL. 
        ◦ Hosting-Strategie: Die Datenbank ist manuell auf der projekt-pear-vm installiert, um Kosten zu sparen. 
        ◦ Datenbank-Name: pear_app_db (korrigiert von fleissige_birne_app_db). 
        ◦ Zugriff: Der Zugriff ist nur intern (localhost) von Diensten auf derselben VM möglich. 
        ◦ Schema-Import: Das schema.sql wurde für MySQL angepasst und erfolgreich importiert, inklusive Anpassungen wie SERIAL PRIMARY KEY zu INT AUTO_INCREMENT PRIMARY KEY und Erweiterung der tbl_begleiter um Adress- und Firmeninformationen. Das Schema umfasst Tabellen für Kunden, Begleiter, Termine, Dokumentationen, Rechnungen und Rechnungspositionen.

### 3.1 Datenbankdetails und -struktur

Die PEAR-Anwendung nutzt eine MySQL-Datenbank zur persistenten Speicherung aller relevanten Daten. Die Datenbank ist auf der Google Compute Engine VM `projekt-pear-vm` installiert und konfiguriert, um den Zugriff auf `localhost` zu beschränken, was die Sicherheit erhöht.

**Findbarkeit und Analyse der Datenbankstruktur:**
Die Datenbankstruktur wird nicht direkt im Python-Code der Anwendung (z.B. in `modules/team.py`) durch `CREATE TABLE`-Anweisungen verwaltet. Stattdessen wird das Schema extern über ein `schema.sql`-Skript importiert, das manuell auf der VM ausgeführt wird. Die Analyse der Datenbankstruktur erfolgte durch direkte Verbindung zur MySQL-Instanz auf der VM mittels des `mysql`-Clients und Abfrage der Tabellendefinitionen.

**Datenbankname:** `pear_app_db`

**Übersicht der Tabellen:**

Die `pear_app_db` enthält die folgenden Haupttabellen, die die Kernfunktionalitäten der PEAR-Anwendung abbilden:

#### `tbl_kunden`
Speichert detaillierte Informationen über die Kunden, einschließlich persönlicher Daten, Adressen und Betreuungsinformationen.

| Feld                        | Typ           | Null | Key | Default           | Extra                                         |
|----------------------------|---------------|------|-----|-------------------|-----------------------------------------------|
| `kunden_id`                | `int`         | NO   | PRI | `NULL`            | `auto_increment`                              |
| `name_vollstaendig`        | `varchar(255)`| NO   | UNI | `NULL`            |                                               |
| `adresse_strasse`          | `varchar(255)`| NO   |     | `NULL`            |                                               |
| `adresse_hausnummer`       | `varchar(50)` | YES  |     | `NULL`            |                                               |
| `adresse_plz`              | `varchar(20)` | NO   | MUL | `NULL`            |                                               |
| `adresse_ort`              | `varchar(255)`| NO   |     | `NULL`            |                                               |
| `adresszusatz`             | `text`        | YES  |     | `NULL`            |                                               |
| `kontakt_telefon`          | `varchar(50)` | YES  |     | `NULL`            |                                               |
| `kontakt_email`            | `varchar(255)`| YES  |     | `NULL`            |                                               |
| `besondere_hinweise`       | `text`        | YES  |     | `NULL`            |                                               |
| `geplante_stunden_pro_woche`| `decimal(5,2)`| YES  |     | `NULL`            |                                               |
| `betreuungsbeginn`         | `date`        | YES  |     | `NULL`            |                                               |
| `ist_aktiv`                | `tinyint(1)`  | YES  |     | `1`               |                                               |
| `erstellt_am`              | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED`                           |
| `aktualisiert_am`          | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED on update CURRENT_TIMESTAMP`|

#### `tbl_dokumentationen`
Speichert die Inhalte von Dokumentationen, die mit spezifischen Terminen und Begleitern verknüpft sind.

| Feld                | Typ           | Null | Key | Default           | Extra                                         |
|--------------------|---------------|------|-----|-------------------|-----------------------------------------------|
| `dokumentation_id` | `int`         | NO   | PRI | `NULL`            | `auto_increment`                              |
| `termin_id`        | `int`         | NO   | MUL | `NULL`            |                                               |
| `begleiter_id`     | `int`         | NO   | MUL | `NULL`            |                                               |
| `inhalt_text`      | `text`        | NO   |     | `NULL`            |                                               |
| `status_dok`       | `varchar(50)` | NO   |     | `Entwurf`         |                                               |
| `erstellt_am`      | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED`                           |
| `aktualisiert_am`  | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED on update CURRENT_TIMESTAMP`|

#### `tbl_rechnungen`
Enthält Informationen zu erstellten Rechnungen, einschließlich Rechnungsnummer, Kundenzuordnung, Beträge und Zahlungsstatus.

| Feld                  | Typ           | Null | Key | Default           | Extra                                         |
|----------------------|---------------|------|-----|-------------------|-----------------------------------------------|
| `rechnung_id`        | `int`         | NO   | PRI | `NULL`            | `auto_increment`                              |
| `rechnungsnummer`    | `varchar(50)` | NO   | UNI | `NULL`            |                                               |
| `kunden_id`          | `int`         | NO   | MUL | `NULL`            |                                               |
| `rechnungsdatum`     | `date`        | NO   |     | `NULL`            |                                               |
| `faelligkeitsdatum`  | `date`        | NO   |     | `NULL`            |                                               |
| `gesamtbetrag_brutto`| `decimal(10,2)`| NO   |     | `NULL`            |                                               |
| `status_zahlung`     | `varchar(50)` | NO   |     | `Offen`           |                                               |
| `bezahlt_am`         | `date`        | YES  |     | `NULL`            |                                               |
| `rechnungs_pdf_pfad` | `text`        | YES  |     | `NULL`            |                                               |
| `versand_status`     | `varchar(50)` | YES  |     | `NULL`            |                                               |
| `erstellt_am`        | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED`                           |
| `aktualisiert_am`    | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED on update CURRENT_TIMESTAMP`|

#### `tbl_rechnungspositionen`
Detailliert die einzelnen Positionen, die zu einer Rechnung gehören, einschließlich Leistungsbeschreibung, Menge und Einzelpreis.

| Feld                    | Typ           | Null | Key | Default           | Extra             |
|------------------------|---------------|------|-----|-------------------|-------------------|
| `rechnungspos_id`      | `int`         | NO   | PRI | `NULL`            | `auto_increment`  |
| `rechnung_id`          | `int`         | NO   | MUL | `NULL`            |                   |
| `termin_id`            | `int`         | YES  | MUL | `NULL`            |                   |
| `leistungsbeschreibung`| `text`        | NO   |     | `NULL`            |                   |
| `menge`                | `decimal(7,2)`| NO   |     | `NULL`            |                   |
| `einheit`              | `varchar(50)` | NO   |     | `NULL`            |                   |
| `einzelpreis`          | `decimal(7,2)`| NO   |     | `NULL`            |                   |
| `position_betrag_brutto`| `decimal(10,2)`| NO   |     | `NULL`            |                   |
| `erstellt_am`          | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED`|

#### `tbl_termine`
Verwaltet alle geplanten und durchgeführten Termine, mit Verknüpfungen zu Kunden und Begleitern sowie Zeit- und Statusinformationen.

| Feld                      | Typ           | Null | Key | Default           | Extra                                         |
|--------------------------|---------------|------|-----|-------------------|-----------------------------------------------|
| `termin_id`              | `int`         | NO   | PRI | `NULL`            | `auto_increment`                              |
| `kunden_id`              | `int`         | NO   | MUL | `NULL`            |                                               |
| `begleiter_id`           | `int`         | YES  | MUL | `NULL`            |                                               |
| `datum_termin`           | `date`        | NO   |     | `NULL`            |                                               |
| `uhrzeit_geplant_start`  | `time`        | NO   |     | `NULL`            |                                               |
| `uhrzeit_geplant_ende`   | `time`        | NO   |     | `NULL`            |                                               |
| `zeit_ist_start`         | `datetime`    | YES  |     | `NULL`            |                                               |
| `zeit_ist_ende`          | `datetime`    | YES  |     | `NULL`            |                                               |
| `fahrtzeit_minuten`      | `int`         | YES  |     | `NULL`            |                                               |
| `status_termin`          | `varchar(50)` | NO   | MUL | `Geplant`         |                                               |
| `stunden_berechnet`      | `decimal(5,2)`| YES  |     | `NULL`            |                                               |
| `ist_abrechnungsrelevant`| `tinyint(1)`  | YES  |     | `1`               |                                               |
| `ist_final_abgerechnet`  | `tinyint(1)`  | YES  |     | `0`               |                                               |
| `notizen_intern`         | `text`        | YES  |     | `NULL`            |                                               |
| `erstellt_am`            | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED`                           |
| `aktualisiert_am`        | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED on update CURRENT_TIMESTAMP`|

#### `tbl_begleiter`
Enthält Informationen über die Alltagsbegleiter, einschließlich Kontaktdaten, Authentifizierungsinformationen und Adressdetails.

| Feld                | Typ           | Null | Key | Default           | Extra                                         |
|--------------------|---------------|------|-----|-------------------|-----------------------------------------------|
| `begleiter_id`     | `int`         | NO   | PRI | `NULL`            | `auto_increment`                              |
| `name_vollstaendig`| `varchar(255)`| NO   |     | `NULL`            |                                               |
| `kontakt_telefon`  | `varchar(50)` | YES  |     | `NULL`            |                                               |
| `kontakt_email`    | `varchar(255)`| NO   | UNI | `NULL`            |                                               |
| `passwort_hash`    | `varchar(255)`| NO   |     | `NULL`            |                                               |
| `rolle`            | `varchar(50)` | NO   |     | `Begleiter`       |                                               |
| `ist_aktiv`        | `tinyint(1)`  | YES  |     | `1`               |                                               |
| `erstellt_am`      | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED`                           |
| `aktualisiert_am`  | `datetime`    | YES  |     | `CURRENT_TIMESTAMP`| `DEFAULT_GENERATED on update CURRENT_TIMESTAMP`|
| `adresse_strasse`  | `text`        | YES  |     | `NULL`            |                                               |
| `adresse_hausnummer`| `text`        | YES  |     | `NULL`            |                                               |
| `adresse_plz`      | `text`        | YES  |     | `NULL`            |                                               |
| `adresse_ort`      | `text`        | YES  |     | `NULL`            |                                               |
| `firmenname`       | `text`        | YES  |     | `NULL`            |                                               |
| `steuernummer`     | `text`        | YES  |     | `NULL`            |                                               | 
4. Frontend- und Backend-Entwicklung
    • Frontend (Landing Page, Login, Registrierung): 
        ◦ Wird über den Nginx-Webserver bereitgestellt. 
        ◦ Ein modernes, klares und responsives Design mit Google Fonts (Montserrat und Poppins) wurde implementiert, inklusive Media Queries für mobile Geräte und einem Sticky Footer. Formularfelder auf der Registrierungsseite sind in zwei Spalten linksbündig angeordnet. 
        ◦ Das Deployment erfolgt über automatisierte Skripte (deploy_all.sh oder deploy_frontend.sh) von GitHub auf die VM. 
    • Backend-API (Benutzerregistrierung & KI-Extraktion): 
        ◦ Implementiert mit Python und FastAPI. 
        ◦ Bietet Endpunkte für die Benutzerregistrierung (POST /api/register) und die KI-gestützte Datenextraktion aus E-Mails (POST /api/process-email-for-client). 
        ◦ Die API nutzt Gemini-Integration zur Datenextraktion aus Freitext und implementiert Passwort-Hashing (bcrypt) sowie E-Mail-Eindeutigkeitsprüfung. 
        ◦ Der aktuelle Status der API ist positiv: Sie läuft und ist über Port 8000 erreichbar! 🎉. 
5. E-Mail-Verarbeitung für Kundenanlage – Strategiewechsel und Lösung des Berechtigungsproblems
Die E-Mail-Verarbeitung ist ein zentraler Aspekt für die automatisierte Kundenanlage, insbesondere die automatische Extraktion von Klientendaten aus E-Mails.
    • Herausforderungen und Strategiewechsel: 
        ◦ Die anfängliche Implementierung über N8N auf der VM stieß auf anhaltende und fundamentale Probleme, die die Stabilität des Systems gefährdeten. Hauptprobleme waren Ressourcenmangel und Instabilität von N8N (z.B. bei npm-Build-Prozessen), die Komplexität des N8N-Builds aus dem Monorepo, sowie Schwierigkeiten bei der OAuth-Client-Erstellung für E-Mail-Trigger, da die Google Cloud Console keine IP-Adressen als Weiterleitungs-URIs akzeptierte. 
        ◦ Aufgrund dieser Schwierigkeiten wurde ein Strategiewechsel zu einer serverlosen Architektur entschieden, um die E-Mail-Verarbeitung von der VM zu entkoppeln. 
    • Neuer Serverloser Ansatz mit Google Cloud Storage & Cloud Run: 
        ◦ Ziel: Automatisierte, stabile und kostengünstige E-Mail-Verarbeitung für neue Klienten ohne VM-spezifische Instabilität. 
        ◦ Implementierung: Eingehende E-Mails von Vermittlungsstellen sollen über einen externen E-Mail-Provider an einen Google Cloud Storage Bucket (pear-email-inbox-raw) weitergeleitet werden. Das Speichern einer neuen E-Mail im Bucket löst einen Google Cloud Run-Dienst aus. Dieser Dienst liest die E-Mail und ruft den bestehenden FastAPI-Endpunkt POST /api/process-email-for-client auf der VM zur KI-gestützten Datenextraktion auf. 
        ◦ Vorteile: Serverlos, wartungsfrei, hochgradig skalierbar und extrem kosteneffizient (nutzt Free-Tier-Kontingente für minimale Nutzung). 
    • Aktuelles Problem vor der Lösung: Obwohl das Docker-Image für die E-Mail-Verarbeitungsfunktion erfolgreich gebaut wurde, schlug der Push des Docker-Images zur Artifact Registry mit der Fehlermeldung "Permission 'artifactregistry.repositories.uploadArtifacts' denied" fehl. Dies deutete auf ein tieferliegendes Authentifizierungsproblem hin. 
    • Lösung der Berechtigungsprobleme (Dokument vom 24. Juli 2025): Das Dokument "Dokumentation der Lösung bei Berechtigungsproblemen auf der GCP" beschreibt die Implementierung einer automatisierten CI/CD-Pipeline mit Google Cloud Build, um genau dieses Problem zu beheben und Docker-Images zuverlässig zu bauen und zur Artifact Registry zu pushen. 
        ◦ Es wird ein Build-Trigger namens dev-team-trigger konfiguriert, der auf Pushes zum main-Branch im GitHub-Repository HystDevTV/PEARv2 reagiert. 
        ◦ Die cloudbuild.yaml-Konfiguration im Repository definiert den Build-Prozess, der Docker-Images baut und mit dem Commit-SHA und latest taggt, um sie anschließend in die Artifact Registry zu pushen. 
        ◦ Entscheidend zur Lösung der Berechtigungsprobleme ist die Verwendung eines dedizierten Service Accounts (z.B. build-trigger@pear-dev-teamv1.iam.gserviceaccount.com) mit präzise zugewiesenen Rollen. Zu diesen Rollen gehören: 
            ▪ Artifact Registry Writer (roles/artifactregistry.writer): Diese spezifische Rolle ermöglicht das Hochladen von Artefakten (uploadArtifacts), was zuvor fehlschlug. 
            ▪ Cloud-Build-Dienstkonto (roles/cloudbuild.builds.builder): Ermöglicht Cloud Build, Build-Operationen durchzuführen. 
            ▪ Logs Bucket Writer und Logs Writer (alternativ CLOUD_LOGGING_ONLY in der cloudbuild.yaml): Für das Schreiben von Build-Logs. 
            ▪ Storage Object Creator und Storage Object Viewer: Für den Umgang mit Objekten in Cloud Storage, z.B. für Logs. 
            ▪ Developer Connect Read Token Accessor und Secure Source Manager Repository Reader: Für den Zugriff auf das GitHub-Repository. 
            ▪ Zusätzlich sollte der Benutzer, der den Service Account verwaltet, die Rolle Dienstkontonutzer (roles/iam.serviceAccountUser) auf diesem Service Account haben. 
        ◦ Dieses Vorgehen bietet Vorteile in Bezug auf Sicherheit, Nachvollziehbarkeit und Skalierbarkeit, indem nur die explizit benötigten Rechte zugewiesen werden. 

    5.1 Modul „E-Mail-Ingest“ (IMAP → GCS Rohspeicher)
Stand: 11.08.2025

Ziel: Automatisierte Abholung eingehender E-Mails mit potenziellen Kundendaten und Speicherung als Rohdaten im Google Cloud Storage (GCS).
Eine Verarbeitung oder Extraktion erfolgt nicht in diesem Schritt, sondern später durch den Gemini-Parser.

Funktionsweise
Verbindung zum IMAP-Server

Host: server7.rainbow-web.com
Port: 993 (SSL)
Zugangsdaten aus .env geladen (IMAP_USER, IMAP_PASSWORD).
Filterung relevanter E-Mails
Es werden nur E-Mails verarbeitet, deren Betreff mindestens eines der folgenden Schlüsselwörter enthält:
„Kundendaten“
„Kunden“
„Klientendaten“
Groß-/Kleinschreibung wird ignoriert.

Alle anderen E-Mails werden übersprungen.

Abruf neuer Nachrichten

Nur ungelesene Nachrichten (UNSEEN) werden berücksichtigt.

Die vollständige MIME-Message wird als Rohstring im JSON-Format gespeichert.

Speicherung im GCS-Bucket

Bucket: pear-email-inbox-raw-pearv2

Pfad: raw/<uuid>.json

Inhalt: Original-MIME-Daten (inkl. Header, Body, Anhänge).

6. Versionsmanagement & Deployment
    • Versionskontrolle: Git. 
    • Remote Repository: GitHub (Public HystDevTV/PEARv2). Zuvor gab es auch ein separates privates/öffentliches pear-frontend Repository. 
    • Lokale Versionierung: package.json ("version": "0.1.1"). 
    • Automatisches Deployment-Skript auf VM (deploy_all.sh / deploy_frontend.sh): Holt Code von GitHub, kopiert Dateien nach /var/www/html/, setzt Berechtigungen und startet Nginx neu. 
7. Nicht-Funktionale Anforderungen
PEAR berücksichtigt umfassende nicht-funktionale Anforderungen.
    • Sicherheit (NF-SI-001): 
        ◦ Authentifizierung & Autorisierung: Alle Zugriffe auf das System und die Daten müssen authentifiziert (Login) und autorisiert (Rollen/Rechte) sein. Passwörter müssen gehasht und gesalzen gespeichert werden. Sichere Kommunikation über HTTPS/SSL für alle Web- und API-Verbindungen. 
        ◦ Datensicherheit: Sensible Klientendaten müssen Ende-zu-Ende verschlüsselt sein (Datenübertragung und ruhende Daten). Regelmäßige, automatisierte und verschlüsselte Backups der Datenbank und abgelegten Dateien (MySQL Backups, Cloud Storage) sind vorgesehen. Zugriff auf die VM und Datenbank nur über SSH-Schlüssel/interne IPs, keine direkten Root-Logins über Passwort. Firewall-Regeln sind restriktiv konfiguriert. 
        ◦ Optionale VPN-Konfiguration für anonymen Internetzugang über die VM. 
    • Datenschutz (DSGVO-Konformität) (NF-DL-001): Das System muss von Grund auf DSGVO-konform entwickelt werden. Dies umfasst die Sicherstellung der Klienten-Einwilligung, das Vorhandensein von Auftragsverarbeitungsvereinbarungen (AVVs) mit allen Cloud-Dienstleistern (Google Cloud, Gemini API, externe E-Mail-Provider) sowie die Umsetzung der Betroffenenrechte (Auskunft, Berichtigung, Löschung), Datenminimierung und Zweckbindung. 
    • Verfügbarkeit (NF-VE-001): Das System muss 24/7 erreichbar sein (Webserver, API, Datenbank) mit mindestens 99,5% Verfügbarkeit. Automatische Neustarts bei Fehlern (systemd für Dienste) sind vorgesehen. 
    • Skalierbarkeit (NF-SC-001): Das System muss bis zu 1000 Klienten und 50 Alltagsbegleitern unterstützen können. Serverlose Komponenten (Cloud Functions/Run) sollen automatisch skalieren, und kurzfristige Hochskalierung der VM für rechenintensive Aufgaben ist möglich. 
    • Performance (NF-PF-001): Ladezeiten der Webseiten unter 3 Sekunden und API-Antwortzeiten unter 1 Sekunde für Standardabfragen werden angestrebt. Automatisierte Prozesse sollen effizient und zeitnah ablaufen. 
    • Benutzerfreundlichkeit (NF-BE-001): Eine intuitive, leicht bedienbare und responsive Oberfläche mit klaren Fehlermeldungen und Rückmeldungen an den Benutzer ist gefordert. 
    • Wartbarkeit & Erweiterbarkeit (NF-WF-001): Ein modulares Design (Backend-API, Frontend, serverlose Services), Clean Code, gute Dokumentation und automatisierte Deployment-Prozesse (Git-basiert) sind grundlegend. 
    • Kostenkontrolle (NF-KO-001): Nutzung von Free-Tier-Kontingenten wo immer möglich, kostenbewusstes Design der Infrastruktur (z.B. Pay-per-Use für Spitzenlasten, serverlos für Ereignis-basierte Aufgaben) und transparentes Kosten-Monitoring sind wichtig. 

Das PEAR-Projekt wird weiterhin aktiv entwickelt. Der Strategiewechsel bei der E-Mail-Verarbeitung hin zu einer serverlosen Architektur und insbesondere die Etablierung einer automatisierten CI/CD-Pipeline mittels Google Cloud Build zur Behebung der Berechtigungsprobleme sind wesentliche Fortschritte, die auf einen klaren Plan zur Überwindung technischer Herausforderungen und zur Sicherstellung der zukünftigen Stabilität und Wartbarkeit hindeuten. Das Projekt ist auf einem guten Weg, seine ambitionierten Ziele der Digitalisierung der Pflegeverwaltung zu erreichen.

