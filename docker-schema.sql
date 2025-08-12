-- PEAR Development Database Schema
-- Basiert auf der Dokumentation aus dokumentation-pear.md

-- Tabelle für Kunden/Klienten
CREATE TABLE IF NOT EXISTS tbl_kunden (
    kunden_id INT AUTO_INCREMENT PRIMARY KEY,
    name_vollstaendig VARCHAR(255) NOT NULL UNIQUE,
    adresse_strasse VARCHAR(255),
    adresse_hausnummer VARCHAR(50),
    adresse_plz VARCHAR(20),
    adresse_ort VARCHAR(255),
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

-- Tabelle für Pending Onboarding Data
CREATE TABLE IF NOT EXISTS tbl_onboarding_pending (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_id VARCHAR(36) NOT NULL UNIQUE,
    case_tag VARCHAR(8) NOT NULL,
    
    -- Kundendaten (werden sukzessive gefüllt)
    name_vollstaendig VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    kontakt_telefon VARCHAR(50),
    kontakt_email VARCHAR(255),
    adresse_strasse VARCHAR(255),
    adresse_hausnummer VARCHAR(50),
    adresse_plz VARCHAR(20),
    adresse_ort VARCHAR(255),
    
    -- Metadaten
    source_sender VARCHAR(255),
    source_subject TEXT,
    raw_data JSON,
    status VARCHAR(50) DEFAULT 'PENDING',
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    
    INDEX idx_case_tag (case_tag),
    INDEX idx_status (status),
    INDEX idx_sender (source_sender)
);

-- 🔐 Authentication System Tables
CREATE TABLE IF NOT EXISTS tbl_accounts (
    account_id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    subscription_tier ENUM('starter', 'professional', 'enterprise') DEFAULT 'starter',
    max_users INT DEFAULT 1,
    
    -- 2FA (Mandatory for all accounts)
    two_factor_enabled BOOLEAN DEFAULT TRUE,
    two_factor_secret VARCHAR(255),
    
    -- Security & Rate Limiting
    failed_login_attempts INT DEFAULT 0,
    locked_until DATETIME NULL,
    
    -- User Preferences
    session_timeout INT DEFAULT 7200, -- 2 hours
    remember_device BOOLEAN DEFAULT TRUE,
    
    -- Activity Tracking
    last_login DATETIME NULL,
    login_count INT DEFAULT 0,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_email (email),
    INDEX idx_subscription_tier (subscription_tier)
);

-- Multi-User Support for Enterprise
CREATE TABLE IF NOT EXISTS tbl_account_users (
    user_id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    begleiter_id INT,
    role ENUM('admin', 'user', 'readonly') DEFAULT 'user',
    permissions JSON,
    
    -- Activity
    last_login DATETIME NULL,
    login_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES tbl_accounts(account_id),
    FOREIGN KEY (begleiter_id) REFERENCES tbl_begleiter(begleiter_id),
    
    INDEX idx_account_id (account_id),
    INDEX idx_begleiter_id (begleiter_id)
);

-- Security Audit Logs
CREATE TABLE IF NOT EXISTS tbl_auth_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(36),
    action VARCHAR(100) NOT NULL, -- login, logout, password_change, 2fa_setup, etc.
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    details JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES tbl_accounts(account_id),
    
    INDEX idx_account_id (account_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
);

-- Device Trust Management
CREATE TABLE IF NOT EXISTS tbl_trusted_devices (
    device_id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    device_name VARCHAR(255),
    device_fingerprint VARCHAR(255) NOT NULL,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    trust_level ENUM('trusted', 'unknown', 'suspicious') DEFAULT 'unknown',
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES tbl_accounts(account_id),
    
    INDEX idx_account_id (account_id),
    INDEX idx_fingerprint (device_fingerprint)
);

-- Test-Daten einfügen
INSERT IGNORE INTO tbl_begleiter (name_vollstaendig, kontakt_email, passwort_hash, rolle) VALUES 
('Test Begleiter', 'test@pear-app.de', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewB.TGKNgTQBQQ3.', 'Begleiter');

INSERT IGNORE INTO tbl_kunden (name_vollstaendig, adresse_strasse, adresse_hausnummer, adresse_plz, adresse_ort, kontakt_telefon, kontakt_email) VALUES 
('Max Mustermann', 'Musterstraße', '123', '12345', 'Musterstadt', '+49 123 456789', 'max.mustermann@example.com');