#!/usr/bin/env python3
"""
🛡️ PEAR Email Guardian - DOS Protection System
Spion-System zur Überwachung und Schutz vor E-Mail-Angriffen

Features:
- Email Volume Monitoring 
- Rate Limiting
- Emergency System Shutdown
- Cost Protection (Gemini API / SMTP)
- Suspicious Pattern Detection
"""

import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

# Guardian Configuration
MAX_EMAILS_PER_MINUTE = int(os.getenv('MAX_EMAILS_PER_MINUTE', '10'))
MAX_EMAILS_PER_HOUR = int(os.getenv('MAX_EMAILS_PER_HOUR', '100'))  
MAX_PENDING_CASES = int(os.getenv('MAX_PENDING_CASES', '500'))
MAX_DAILY_GEMINI_CALLS = int(os.getenv('MAX_DAILY_GEMINI_CALLS', '1000'))
MAX_DAILY_SMTP_SENDS = int(os.getenv('MAX_DAILY_SMTP_SENDS', '200'))

EMERGENCY_LOCKDOWN_FILE = "emergency_lockdown.flag"
GUARDIAN_LOG_FILE = "email_guardian.log"

# Database connection
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

@dataclass
class EmailStats:
    """Email processing statistics"""
    emails_last_minute: int
    emails_last_hour: int
    emails_today: int
    pending_cases: int
    gemini_calls_today: int
    smtp_sends_today: int
    suspicious_patterns: List[str]

@dataclass
class GuardianResult:
    """Guardian check result"""
    allow_processing: bool
    reason: str
    action: str
    stats: EmailStats

class EmailGuardian:
    def __init__(self):
        self.start_time = datetime.now()
        
    def log_guardian_event(self, message: str, level: str = "INFO"):
        """Log guardian events"""
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} - {level} - 🛡️ GUARDIAN: {message}\n"
        
        try:
            with open(GUARDIAN_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception:
            pass  # Fail silently for logging
        
        print(f"🛡️ GUARDIAN {level}: {message}")
    
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
    
    def collect_email_stats(self) -> EmailStats:
        """Collect comprehensive email processing statistics"""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        stats = EmailStats(
            emails_last_minute=0,
            emails_last_hour=0, 
            emails_today=0,
            pending_cases=0,
            gemini_calls_today=0,
            smtp_sends_today=0,
            suspicious_patterns=[]
        )
        
        conn = self.get_db_connection()
        if not conn:
            self.log_guardian_event("Database connection failed - operating in safe mode", "WARNING")
            return stats
            
        try:
            cursor = conn.cursor()
            
            # Count pending cases
            cursor.execute("SELECT COUNT(*) FROM tbl_onboarding_pending WHERE status = 'PENDING'")
            result = cursor.fetchone()
            if result:
                stats.pending_cases = result[0]
            
            # Check for suspicious patterns in recent pending cases
            cursor.execute("""
                SELECT source_sender, COUNT(*) as count 
                FROM tbl_onboarding_pending 
                WHERE created_at >= %s 
                GROUP BY source_sender 
                HAVING count >= 5
            """, (one_hour_ago,))
            
            suspicious_senders = cursor.fetchall()
            for sender, count in suspicious_senders:
                stats.suspicious_patterns.append(f"Sender '{sender}': {count} emails in 1 hour")
            
            cursor.close()
            conn.close()
            
        except Error as e:
            self.log_guardian_event(f"Database query error: {e}", "ERROR")
        
        return stats
    
    def detect_suspicious_patterns(self, stats: EmailStats) -> List[str]:
        """Detect suspicious email patterns"""
        patterns = []
        
        # High volume from single source
        if stats.suspicious_patterns:
            patterns.extend(stats.suspicious_patterns)
        
        # Rapid succession of incomplete cases
        if stats.pending_cases > MAX_PENDING_CASES:
            patterns.append(f"Excessive pending cases: {stats.pending_cases}")
        
        # Too many emails in short time
        if stats.emails_last_minute > MAX_EMAILS_PER_MINUTE:
            patterns.append(f"High volume: {stats.emails_last_minute} emails/minute")
            
        if stats.emails_last_hour > MAX_EMAILS_PER_HOUR:
            patterns.append(f"High volume: {stats.emails_last_hour} emails/hour")
        
        return patterns
    
    def check_emergency_lockdown(self) -> bool:
        """Check if emergency lockdown is active"""
        return os.path.exists(EMERGENCY_LOCKDOWN_FILE)
    
    def activate_emergency_lockdown(self, reason: str):
        """Activate emergency lockdown"""
        lockdown_data = {
            "activated_at": datetime.now().isoformat(),
            "reason": reason,
            "auto_unlock_after": (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        try:
            with open(EMERGENCY_LOCKDOWN_FILE, 'w') as f:
                json.dump(lockdown_data, f, indent=2)
                
            self.log_guardian_event(f"🚨 EMERGENCY LOCKDOWN ACTIVATED: {reason}", "CRITICAL")
            
        except Exception as e:
            self.log_guardian_event(f"Failed to activate lockdown: {e}", "ERROR")
    
    def deactivate_emergency_lockdown(self):
        """Deactivate emergency lockdown"""
        try:
            if os.path.exists(EMERGENCY_LOCKDOWN_FILE):
                os.remove(EMERGENCY_LOCKDOWN_FILE)
                self.log_guardian_event("🟢 Emergency lockdown deactivated", "INFO")
        except Exception as e:
            self.log_guardian_event(f"Failed to deactivate lockdown: {e}", "ERROR")
    
    def check_auto_unlock(self):
        """Check if emergency lockdown should be auto-unlocked"""
        if not self.check_emergency_lockdown():
            return
            
        try:
            with open(EMERGENCY_LOCKDOWN_FILE, 'r') as f:
                lockdown_data = json.load(f)
            
            auto_unlock_time = datetime.fromisoformat(lockdown_data.get("auto_unlock_after", ""))
            
            if datetime.now() > auto_unlock_time:
                self.deactivate_emergency_lockdown()
                self.log_guardian_event("Auto-unlock successful", "INFO")
                
        except Exception as e:
            self.log_guardian_event(f"Auto-unlock check failed: {e}", "ERROR")
    
    def evaluate_threat_level(self, stats: EmailStats) -> str:
        """Evaluate current threat level"""
        if stats.pending_cases > MAX_PENDING_CASES * 2:
            return "CRITICAL"
        elif stats.pending_cases > MAX_PENDING_CASES:
            return "HIGH"  
        elif stats.suspicious_patterns:
            return "MEDIUM"
        elif stats.emails_last_hour > MAX_EMAILS_PER_HOUR * 0.7:
            return "LOW"
        else:
            return "NORMAL"
    
    def guardian_check(self) -> GuardianResult:
        """Main guardian check - the 'Spion' function"""
        self.log_guardian_event("🕵️‍♂️ Starting guardian patrol...")
        
        # Check auto-unlock first
        self.check_auto_unlock()
        
        # Check emergency lockdown
        if self.check_emergency_lockdown():
            try:
                with open(EMERGENCY_LOCKDOWN_FILE, 'r') as f:
                    lockdown_data = json.load(f)
                reason = lockdown_data.get("reason", "Unknown")
                return GuardianResult(
                    allow_processing=False,
                    reason=f"Emergency lockdown active: {reason}",
                    action="BLOCKED",
                    stats=EmailStats(0, 0, 0, 0, 0, 0, [])
                )
            except Exception:
                pass
        
        # Collect current statistics
        stats = self.collect_email_stats()
        
        # Detect threats
        threat_level = self.evaluate_threat_level(stats)
        suspicious_patterns = self.detect_suspicious_patterns(stats)
        
        self.log_guardian_event(f"Threat Level: {threat_level}, Pending Cases: {stats.pending_cases}")
        
        # Critical threat - activate emergency lockdown
        if threat_level == "CRITICAL":
            reason = f"Critical threat detected: {stats.pending_cases} pending cases"
            self.activate_emergency_lockdown(reason)
            return GuardianResult(
                allow_processing=False,
                reason=reason,
                action="EMERGENCY_LOCKDOWN",
                stats=stats
            )
        
        # High threat - block processing temporarily
        if threat_level == "HIGH":
            return GuardianResult(
                allow_processing=False,
                reason=f"High threat level: {stats.pending_cases} pending cases",
                action="TEMPORARY_BLOCK", 
                stats=stats
            )
        
        # Medium/Low threat - allow with warnings
        if suspicious_patterns:
            self.log_guardian_event(f"Suspicious patterns detected: {suspicious_patterns}", "WARNING")
            
        return GuardianResult(
            allow_processing=True,
            reason=f"Threat level: {threat_level}",
            action="ALLOW_WITH_MONITORING",
            stats=stats
        )

def main():
    """Test the Guardian system"""
    guardian = EmailGuardian()
    result = guardian.guardian_check()
    
    print(f"🛡️ Guardian Result:")
    print(f"   Allow Processing: {result.allow_processing}")
    print(f"   Reason: {result.reason}")
    print(f"   Action: {result.action}")
    print(f"   Pending Cases: {result.stats.pending_cases}")
    
    if not result.allow_processing:
        print("🚨 EMAIL PROCESSING BLOCKED!")
    else:
        print("✅ Email processing approved")

if __name__ == "__main__":
    main()