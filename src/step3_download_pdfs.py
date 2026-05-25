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

def download_pdf_attachments(service, message_id, subject):
    """Download all PDF attachments from a message"""
    msg_data = service.users().messages().get(userId='me', id=message_id, format='full').execute()
    
    # Create inbox folder if doesn't exist
    os.makedirs('inbox_pdfs', exist_ok=True)
    
    downloaded_files = []
    
    def process_part(part, current_path=""):
        if part.get('filename') and part['filename'].lower().endswith('.pdf'):
            # Get attachment
            attachment_id = part['body'].get('attachmentId')
            if attachment_id:
                attachment = service.users().messages().attachments().get(
                    userId='me', 
                    messageId=message_id, 
                    id=attachment_id
                ).execute()
                
                import base64
                import binascii
                
                data = attachment['data']

                # Remove any whitespace first
                data = data.strip()

                # Fix padding
                missing_padding = len(data) % 4
                if missing_padding:
                    data += '=' * (4 - missing_padding)

                # Handle URL-safe base64 if needed
                try:
                    file_data = base64.b64decode(data)
                except binascii.Error:
                    # Try URL-safe decoding
                    file_data = base64.urlsafe_b64decode(data)
                
                # print("this is the attachment")
                # print(attachment)
                # print(type(attachment))
                # print(type(attachment['data']))
                # data = attachment['data']
                # print("before length is ")
                # print(len(data))
                # while len(data)%4 != 0:
                #     data = data[0:len(data)-1]

                # print("now length is ")
                # print(len(data))
                # # file_data = base64.b64decode(attachment['data'])
                # file_data = base64.b64decode(data) 
                # Clean filename for filesystem
                safe_filename = f"{message_id}_{part['filename']}"
                filepath = os.path.join('inbox_pdfs', safe_filename)
                
                with open(filepath, 'wb') as f:
                    f.write(file_data)
                
                downloaded_files.append(filepath)
                print(f"   💾 Downloaded: {safe_filename}")
        
        # Recursively check nested parts
        if 'parts' in part:
            for subpart in part['parts']:
                process_part(subpart)
    
    # Start processing from payload
    process_part(msg_data['payload'])
    
    return downloaded_files

def main():
    service = get_gmail_service()
    
    # Search for emails with PDF attachments (not yet processed)
    results = service.users().messages().list(
        userId='me', 
        q='has:attachment pdf is:unread',  # Only unread emails
        maxResults=10
    ).execute()
    
    messages = results.get('messages', [])
    print(f"📬 Found {len(messages)} emails with PDF attachments\n")
    
    for msg in messages:
        # Get message details to extract subject
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
        
        subject = "No subject"
        for header in msg_data['payload']['headers']:
            if header['name'] == 'Subject':
                subject = header['value']
                break
        
        print(f"📎 Processing: {subject}")
        
        # Download PDFs
        pdf_files = download_pdf_attachments(service, msg['id'], subject)
        
        if pdf_files:
            print(f"   ✅ Saved {len(pdf_files)} PDF(s)\n")
            # Mark as read so we don't process again
            service.users().messages().modify(
                userId='me', 
                id=msg['id'], 
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        else:
            print(f"   ⚠️ No PDF found\n")

if __name__ == "__main__":
    main()