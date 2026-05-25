import os
import pickle
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

def main():
    service = get_gmail_service()
    
    # Fetch 5 most recent emails
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    
    for msg in results.get('messages', []):
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        subject = None
        for header in msg_data['payload']['headers']:
            if header['name'] == 'Subject':
                subject = header['value']
                break
        print(f"📧 {subject}")

if __name__ == "__main__":
    main()