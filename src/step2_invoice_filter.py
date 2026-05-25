import os
import pickle
import base64
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

def has_pdf_attachment(part):
    if part.get('filename') and part['filename'].lower().endswith('.pdf'):
        return True
    if 'parts' in part:
        for subpart in part['parts']:
            if has_pdf_attachment(subpart):
                return True
    return False

def main():
    service = get_gmail_service()
    
    # Search for emails with "invoice" in subject OR body
    results = service.users().messages().list(
        userId='me', 
        q='invoice OR "Purchase Order" OR "PO" has:attachment',
        maxResults=10
    ).execute()
    
    print(f"🔍 Found {len(results.get('messages', []))} potential invoice emails\n")
    
    for msg in results.get('messages', []):
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        
        # Get subject
        subject = "No subject"
        for header in msg_data['payload']['headers']:
            if header['name'] == 'Subject':
                subject = header['value']
                break
        
        # Check for PDF attachments
        has_pdf = has_pdf_attachment(msg_data['payload'])
        
        if has_pdf:
            print(f"✅ INVOICE CANDIDATE: {subject}")
            print(f"   Message ID: {msg['id']}")
            print(f"   Has PDF: Yes\n")
        else:
            print(f"⚠️  SKIP (no PDF): {subject}\n")

if __name__ == "__main__":
    main()