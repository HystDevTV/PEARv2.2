# PEAR Docker Development Setup

## 🐳 Container-Umgebung starten

Die Container laufen **parallel** zur bestehenden VM-Infrastruktur auf anderen Ports.

### Starten:
```bash
docker-compose -f docker-compose.dev.yml --env-file .env.docker up -d
```

### Services verfügbar unter:
- **MySQL**: `localhost:3307` (phpMyAdmin: `localhost:8080`)
- **FastAPI Backend**: `http://localhost:8001`
- **VM bleibt erreichbar**: `http://35.206.123.242:8000` (Port 3306 für MySQL)

## 📊 Services

| Service | Container Port | Host Port | Beschreibung |
|---------|---------------|-----------|--------------|
| mysql-dev | 3306 | 3307 | MySQL Development DB |
| backend-dev | 8000 | 8001 | FastAPI API Server |
| email-ingest-dev | - | - | E-Mail Processing |
| phpmyadmin | 80 | 8080 | Database Admin UI |

## 🔧 Lokale Entwicklung mit Containern

### bucket_to_gemini.py mit Container-DB:
```bash
# .env anpassen:
DB_HOST=127.0.0.1
DB_PORT=3307

# Dann ausführen:
python bucket_to_gemini.py
```

## 🗄️ Database Management

- **phpMyAdmin**: http://localhost:8080
  - Server: `mysql-dev`
  - User: `app_user` 
  - Password: `TempPass123!`

## 🔄 Container Management

```bash
# Status prüfen
docker-compose -f docker-compose.dev.yml ps

# Logs anzeigen
docker-compose -f docker-compose.dev.yml logs -f

# Stoppen
docker-compose -f docker-compose.dev.yml down

# Mit Volumes löschen (DB-Reset)
docker-compose -f docker-compose.dev.yml down -v
```

## 🚀 Vorteile der Container-Lösung

✅ **Lokale DB-Verbindung** ohne SSH-Tunnel oder Firewall-Konfiguration  
✅ **Isolierte Entwicklung** - VM bleibt unberührt  
✅ **Schnelle Reset-Möglichkeit** mit `docker-compose down -v`  
✅ **Identische Umgebung** für alle Entwickler  
✅ **phpMyAdmin** für einfache DB-Verwaltung  

Die VM kann parallel weiterlaufen und wird erst ersetzt, wenn die Container-Lösung vollständig funktioniert.