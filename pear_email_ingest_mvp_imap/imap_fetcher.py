import os
import imaplib
import email
import requests
from dotenv import load_dotenv

load_dotenv()

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
USE_SSL = os.getenv("IMAP_USE_SSL", "true").lower() == "true"
INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8080/ingest")
SUBJECT_KEYWORDS = [s.strip().lower() for s in os.getenv("SUBJECT_KEYWORDS","").split(",") if s.strip()]

def subject_matches(subject: str) -> bool:
    if not SUBJECT_KEYWORDS:
        return True
    if not subject:
        return False
    s = subject.lower()
    return any(k in s for k in SUBJECT_KEYWORDS)

def connect_imap():
    if USE_SSL:
        M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    else:
        M = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
    M.login(IMAP_USER, IMAP_PASSWORD)
    return M

def main():
    M = connect_imap()
    M.select("INBOX")
    typ, data = M.search(None, '(UNSEEN)')
    if typ != 'OK':
        print("IMAP search failed", typ, data)
        return
    ids = data[0].split()
    print(f"Found {len(ids)} unseen messages.")
    for num in ids:
        typ, msg_data = M.fetch(num, '(RFC822)')
        if typ != 'OK':
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        subject = msg.get('Subject', '')
        from_email = email.utils.parseaddr(msg.get('From'))[1]
        to_email = email.utils.parseaddr(msg.get('To'))[1]

        if not subject_matches(subject):
            print(f"Skip (subject): {subject}")
            continue

        # Extract plain text body
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    charset = part.get_content_charset() or 'utf-8'
                    body_text += part.get_payload(decode=True).decode(charset, errors='ignore')
        else:
            charset = msg.get_content_charset() or 'utf-8'
            body_text = msg.get_payload(decode=True).decode(charset, errors='ignore')

        payload = {
            "subject": subject,
            "from_email": from_email,
            "to_email": to_email,
            "body": body_text
        }
        try:
            resp = requests.post(INGEST_URL, json=payload, timeout=15)
            print("POST /ingest:", resp.status_code, resp.text[:300])
        except Exception as e:
            print("Error posting to ingest:", e)

    M.close()
    M.logout()

if __name__ == "__main__":
    main()
