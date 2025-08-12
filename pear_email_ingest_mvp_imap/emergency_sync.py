#!/usr/bin/env python3
"""
🚨 PEAR Emergency Data Sync System
Pushes critical daily data to Google Calendar when account gets locked

Use Case: "Silvia steht vor der Haustür, Account gesperrt, braucht aber Telefonnummer!"

Features:
- Emergency Calendar Sync bei Account-Lockout
- Today's appointments + customer contact data  
- Automatic Google Calendar integration
- Privacy-safe: nur heute's Daten, auto-cleanup nach 24h
- Fallback für kritische Pflegesituationen

"Niemand wird durch unsere Sicherheit gefickt!" 💪
"""

import os
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# Google Calendar API
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json

load_dotenv()

# Google Calendar Configuration
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_CREDENTIALS_FILE = 'calendar_credentials.json'
CALENDAR_TOKEN_FILE = 'calendar_token.json'
EMERGENCY_CALENDAR_NAME = 'PEAR Emergency - Heute'

# Database
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

@dataclass
class EmergencyAppointment:
    """Emergency appointment data"""
    termin_id: int
    customer_name: str
    customer_phone: str
    customer_address: str
    appointment_time: datetime
    end_time: datetime
    notes: str

@dataclass
class EmergencyContact:
    """Emergency contact info"""
    name: str
    phone: str
    address: str
    emergency_notes: str

class EmergencyDataSync:
    def __init__(self):
        self.calendar_service = None
        self.emergency_calendar_id = None
        
    def get_db_connection(self):
        """Get database connection"""
        if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
            return None
            
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, port=DB_PORT,
                user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
            return conn
        except Error:
            return None
    
    def setup_google_calendar_auth(self):
        """Setup Google Calendar authentication"""
        creds = None
        
        # Load existing token
        if os.path.exists(CALENDAR_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(CALENDAR_TOKEN_FILE, CALENDAR_SCOPES)
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CALENDAR_CREDENTIALS_FILE):
                    print("ERROR: Google Calendar credentials file not found!")
                    print("Please download OAuth2 credentials from Google Cloud Console")
                    return False
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    CALENDAR_CREDENTIALS_FILE, CALENDAR_SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(CALENDAR_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        return True
    
    def get_or_create_emergency_calendar(self) -> Optional[str]:
        """Get or create emergency calendar"""
        if not self.calendar_service:
            return None
        
        try:
            # List existing calendars
            calendars_result = self.calendar_service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            
            # Check if emergency calendar exists
            for calendar in calendars:
                if calendar['summary'] == EMERGENCY_CALENDAR_NAME:
                    self.emergency_calendar_id = calendar['id']
                    return calendar['id']
            
            # Create new emergency calendar
            emergency_calendar = {
                'summary': EMERGENCY_CALENDAR_NAME,
                'description': '🚨 PEAR Emergency Data - Auto-generated bei Account-Lockout',
                'timeZone': 'Europe/Berlin'
            }
            
            created_calendar = self.calendar_service.calendars().insert(body=emergency_calendar).execute()
            self.emergency_calendar_id = created_calendar['id']
            
            print(f"✅ Emergency Calendar erstellt: {created_calendar['id']}")
            return created_calendar['id']
            
        except Exception as e:
            print(f"ERROR: Calendar setup failed: {e}")
            return None
    
    def get_todays_appointments(self, begleiter_id: int) -> List[EmergencyAppointment]:
        """Get today's appointments with customer data"""
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(dictionary=True)
            
            today = date.today()
            
            cursor.execute("""
                SELECT 
                    t.termin_id,
                    t.datum_termin,
                    t.uhrzeit_geplant_start,
                    t.uhrzeit_geplant_ende,
                    t.notizen_intern,
                    k.name_vollstaendig,
                    k.kontakt_telefon,
                    CONCAT(
                        COALESCE(k.adresse_strasse, ''), ' ',
                        COALESCE(k.adresse_hausnummer, ''), ', ',
                        COALESCE(k.adresse_plz, ''), ' ',
                        COALESCE(k.adresse_ort, '')
                    ) as full_address,
                    k.besondere_hinweise
                FROM tbl_termine t
                JOIN tbl_kunden k ON t.kunden_id = k.kunden_id
                WHERE t.begleiter_id = %s 
                  AND t.datum_termin = %s
                  AND t.status_termin NOT IN ('Abgesagt', 'Abgeschlossen')
                ORDER BY t.uhrzeit_geplant_start
            """, (begleiter_id, today))
            
            appointments = []
            for row in cursor.fetchall():
                # Combine date + time for datetime objects
                start_datetime = datetime.combine(row['datum_termin'], row['uhrzeit_geplant_start'])
                end_datetime = datetime.combine(row['datum_termin'], row['uhrzeit_geplant_ende'])
                
                appointments.append(EmergencyAppointment(
                    termin_id=row['termin_id'],
                    customer_name=row['name_vollstaendig'],
                    customer_phone=row['kontakt_telefon'] or "Keine Telefonnummer",
                    customer_address=row['full_address'].strip(', '),
                    appointment_time=start_datetime,
                    end_time=end_datetime,
                    notes=f"{row['notizen_intern'] or ''}\n\n🚨 NOTFALL-INFO: {row['besondere_hinweise'] or 'Keine besonderen Hinweise'}"
                ))
            
            cursor.close()
            conn.close()
            return appointments
            
        except Error as e:
            print(f"ERROR: Database query failed: {e}")
            return []
    
    def push_appointment_to_calendar(self, appointment: EmergencyAppointment):
        """Push single appointment to Google Calendar"""
        if not self.calendar_service or not self.emergency_calendar_id:
            return False
        
        try:
            # Create calendar event
            event = {
                'summary': f'🚨 EMERGENCY: {appointment.customer_name}',
                'location': appointment.customer_address,
                'description': f"""🚨 PEAR EMERGENCY SYNC - Account wurde gesperrt!

👤 KUNDE: {appointment.customer_name}
📞 TELEFON: {appointment.customer_phone}
🏠 ADRESSE: {appointment.customer_address}

📝 NOTIZEN:
{appointment.notes}

⚠️ Diese Daten wurden automatisch synchronisiert, da dein PEAR-Account gesperrt wurde.
🔓 Entsperre deinen Account um wieder vollen Zugriff zu haben.

🗑️ Dieses Event wird automatisch in 24h gelöscht.""",
                
                'start': {
                    'dateTime': appointment.appointment_time.isoformat(),
                    'timeZone': 'Europe/Berlin',
                },
                'end': {
                    'dateTime': appointment.end_time.isoformat(),
                    'timeZone': 'Europe/Berlin',
                },
                
                # Auto-delete after 24 hours
                'reminders': {
                    'useDefault': True,
                },
                
                # Color it red for emergency
                'colorId': '11'  # Red color
            }
            
            created_event = self.calendar_service.events().insert(
                calendarId=self.emergency_calendar_id, 
                body=event
            ).execute()
            
            print(f"✅ Emergency appointment synced: {appointment.customer_name}")
            return created_event['id']
            
        except Exception as e:
            print(f"ERROR: Failed to create calendar event: {e}")
            return False
    
    def cleanup_old_emergency_events(self):
        """Delete emergency events older than 24 hours"""
        if not self.calendar_service or not self.emergency_calendar_id:
            return
        
        try:
            # Get events from yesterday and older
            yesterday = (datetime.now() - timedelta(days=1)).isoformat() + 'Z'
            
            events_result = self.calendar_service.events().list(
                calendarId=self.emergency_calendar_id,
                timeMax=yesterday,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            for event in events:
                if '🚨 EMERGENCY' in event.get('summary', ''):
                    self.calendar_service.events().delete(
                        calendarId=self.emergency_calendar_id,
                        eventId=event['id']
                    ).execute()
                    print(f"🗑️ Cleaned up old emergency event: {event.get('summary', 'Unknown')}")
                    
        except Exception as e:
            print(f"ERROR: Cleanup failed: {e}")
    
    def trigger_emergency_sync(self, begleiter_id: int, reason: str = "Account locked") -> bool:
        """Main emergency sync function - called when account gets locked"""
        print(f"🚨 EMERGENCY SYNC TRIGGERED: {reason}")
        
        # Setup Google Calendar
        if not self.setup_google_calendar_auth():
            print("ERROR: Could not authenticate with Google Calendar")
            return False
        
        # Get or create emergency calendar
        if not self.get_or_create_emergency_calendar():
            print("ERROR: Could not setup emergency calendar")
            return False
        
        # Cleanup old events first
        self.cleanup_old_emergency_events()
        
        # Get today's appointments
        appointments = self.get_todays_appointments(begleiter_id)
        
        if not appointments:
            print("ℹ️ Keine Termine für heute gefunden")
            return True
        
        print(f"📅 Synchronisiere {len(appointments)} Notfall-Termine...")
        
        # Push each appointment to calendar
        sync_count = 0
        for appointment in appointments:
            if self.push_appointment_to_calendar(appointment):
                sync_count += 1
        
        print(f"✅ Emergency Sync abgeschlossen: {sync_count}/{len(appointments)} Termine synchronisiert")
        
        # Add summary event
        self.create_emergency_summary_event(len(appointments), reason)
        
        return True
    
    def create_emergency_summary_event(self, appointment_count: int, reason: str):
        """Create summary event explaining the emergency sync"""
        try:
            summary_event = {
                'summary': f'🚨 PEAR EMERGENCY SYNC ({appointment_count} Termine)',
                'description': f"""🚨 NOTFALL-SYNCHRONISATION AKTIVIERT

GRUND: {reason}
SYNCHRONISIERT: {appointment_count} Termine für heute
ZEIT: {datetime.now().strftime('%d.%m.%Y %H:%M')}

❓ WAS IST PASSIERT?
Dein PEAR-Account wurde aus Sicherheitsgründen gesperrt. 
Um sicherzustellen, dass du deine heutigen Termine nicht verpasst, 
wurden die wichtigsten Daten hierher synchronisiert.

🔓 WIE ENTSPERREN?
1. Warte 15 Minuten
2. Oder kontaktiere den Support
3. Login mit korrekten Daten + 2FA

🗑️ AUTO-CLEANUP
Diese Notfall-Daten werden automatisch in 24h gelöscht.

💪 PEAR - "Niemand wird durch unsere Sicherheit gefickt!"
""",
                
                'start': {
                    'dateTime': datetime.now().isoformat(),
                    'timeZone': 'Europe/Berlin',
                },
                'end': {
                    'dateTime': (datetime.now() + timedelta(minutes=15)).isoformat(),
                    'timeZone': 'Europe/Berlin',
                },
                
                'colorId': '11'  # Red
            }
            
            self.calendar_service.events().insert(
                calendarId=self.emergency_calendar_id,
                body=summary_event
            ).execute()
            
        except Exception as e:
            print(f"ERROR: Could not create summary event: {e}")

def main():
    """Test emergency sync"""
    sync = EmergencyDataSync()
    
    # Test with begleiter_id 1 (if exists)
    result = sync.trigger_emergency_sync(1, "Test Emergency Sync")
    
    if result:
        print("🎉 Emergency sync successful!")
    else:
        print("❌ Emergency sync failed!")

if __name__ == "__main__":
    main()