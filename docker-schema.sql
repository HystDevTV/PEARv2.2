-- PEAR Development Database Schema
-- Basiert auf der Dokumentation aus dokumentation-pear.md

-- Tabelle für Kunden/Klienten
CREATE TABLE IF NOT EXISTS tbl_kunden (
    kunden_id INT AUTO_INCREMENT PRIMARY KEY,
    name_vollstaendig VARCHAR(255) NOT NULL UNIQUE,
    adresse_strasse VARCHAR(255) NOT NULL,
    adresse_hausnummer VARCHAR(50),
    adresse_plz VARCHAR(20) NOT NULL,
    adresse_ort VARCHAR(255) NOT NULL,
    adresszusatz TEXT,
    kontakt_telefon VARCHAR(50),
    kontakt_email VARCHAR(255),
    besondere_hinweise TEXT,
    source_subject TEXT,
    source_from_email VARCHAR(255),
    raw_json JSON,
    geplante_stunden_pro_woche DECIMAL(5,2),
    betreuungsbeginn DATE,
    ist_aktiv TINYINT(1) DEFAULT 1,
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_plz (adresse_plz)
);

-- Tabelle für Alltagsbegleiter
CREATE TABLE IF NOT EXISTS tbl_begleiter (
    begleiter_id INT AUTO_INCREMENT PRIMARY KEY,
    name_vollstaendig VARCHAR(255) NOT NULL,
    kontakt_telefon VARCHAR(50),
    kontakt_email VARCHAR(255) NOT NULL UNIQUE,
    passwort_hash VARCHAR(255) NOT NULL,
    rolle VARCHAR(50) NOT NULL DEFAULT 'Begleiter',
    ist_aktiv TINYINT(1) DEFAULT 1,
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    adresse_strasse TEXT,
    adresse_hausnummer TEXT,
    adresse_plz TEXT,
    adresse_ort TEXT,
    firmenname TEXT,
    steuernummer TEXT
);

-- Tabelle für Termine
CREATE TABLE IF NOT EXISTS tbl_termine (
    termin_id INT AUTO_INCREMENT PRIMARY KEY,
    kunden_id INT NOT NULL,
    begleiter_id INT,
    datum_termin DATE NOT NULL,
    uhrzeit_geplant_start TIME NOT NULL,
    uhrzeit_geplant_ende TIME NOT NULL,
    zeit_ist_start DATETIME,
    zeit_ist_ende DATETIME,
    fahrtzeit_minuten INT,
    status_termin VARCHAR(50) NOT NULL DEFAULT 'Geplant',
    stunden_berechnet DECIMAL(5,2),
    ist_abrechnungsrelevant TINYINT(1) DEFAULT 1,
    ist_final_abgerechnet TINYINT(1) DEFAULT 0,
    notizen_intern TEXT,
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (kunden_id) REFERENCES tbl_kunden(kunden_id),
    FOREIGN KEY (begleiter_id) REFERENCES tbl_begleiter(begleiter_id),
    INDEX idx_status (status_termin)
);

-- Tabelle für Dokumentationen
CREATE TABLE IF NOT EXISTS tbl_dokumentationen (
    dokumentation_id INT AUTO_INCREMENT PRIMARY KEY,
    termin_id INT NOT NULL,
    begleiter_id INT NOT NULL,
    inhalt_text TEXT NOT NULL,
    status_dok VARCHAR(50) NOT NULL DEFAULT 'Entwurf',
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (termin_id) REFERENCES tbl_termine(termin_id),
    FOREIGN KEY (begleiter_id) REFERENCES tbl_begleiter(begleiter_id)
);

-- Tabelle für Rechnungen
CREATE TABLE IF NOT EXISTS tbl_rechnungen (
    rechnung_id INT AUTO_INCREMENT PRIMARY KEY,
    rechnungsnummer VARCHAR(50) NOT NULL UNIQUE,
    kunden_id INT NOT NULL,
    rechnungsdatum DATE NOT NULL,
    faelligkeitsdatum DATE NOT NULL,
    gesamtbetrag_brutto DECIMAL(10,2) NOT NULL,
    status_zahlung VARCHAR(50) NOT NULL DEFAULT 'Offen',
    bezahlt_am DATE,
    rechnungs_pdf_pfad TEXT,
    versand_status VARCHAR(50),
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (kunden_id) REFERENCES tbl_kunden(kunden_id)
);

-- Tabelle für Rechnungspositionen
CREATE TABLE IF NOT EXISTS tbl_rechnungspositionen (
    rechnungspos_id INT AUTO_INCREMENT PRIMARY KEY,
    rechnung_id INT NOT NULL,
    termin_id INT,
    leistungsbeschreibung TEXT NOT NULL,
    menge DECIMAL(7,2) NOT NULL,
    einheit VARCHAR(50) NOT NULL,
    einzelpreis DECIMAL(7,2) NOT NULL,
    position_betrag_brutto DECIMAL(10,2) NOT NULL,
    erstellt_am DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rechnung_id) REFERENCES tbl_rechnungen(rechnung_id),
    FOREIGN KEY (termin_id) REFERENCES tbl_termine(termin_id)
);

-- Tabelle für E-Mail-Verarbeitung (für bucket_to_gemini.py)
CREATE TABLE IF NOT EXISTS tbl_email_processing (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_tag VARCHAR(50),
    email_hash VARCHAR(64) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',
    extracted_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL
);

-- Test-Daten einfügen
INSERT IGNORE INTO tbl_begleiter (name_vollstaendig, kontakt_email, passwort_hash, rolle) VALUES 
('Test Begleiter', 'test@pear-app.de', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewB.TGKNgTQBQQ3.', 'Begleiter');

INSERT IGNORE INTO tbl_kunden (name_vollstaendig, adresse_strasse, adresse_hausnummer, adresse_plz, adresse_ort, kontakt_telefon, kontakt_email) VALUES 
('Max Mustermann', 'Musterstraße', '123', '12345', 'Musterstadt', '+49 123 456789', 'max.mustermann@example.com');