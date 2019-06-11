from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

ID = 'me'
scholar_email = 'scholaralerts-noreply@google.com'

def getLabel(gmail, label_name):
    return gmail.users().labels().get(id=label_name, userId=ID).execute()

# Returns matching message ids
def getMessages(gmail, label_name, query=""):
    json = gmail.users().messages().list(\
            userId=ID, labelIds=[label_name], q=query).execute()
    return json.get('messages', [])

# Returns ids of matching scholar messages
def getScholarMessages(gmail):
    return getMessages(gmail, "UNREAD", query="from:" + scholar_email)

def readMessage(gmail, message_id, format="full"):
    return gmail.users().messages().get(id=message_id, userId=ID, format=format).execute()

def summarizeMessages(gmail, messages):
    for a in messages:
        message = readMessage(gmail, a['id'], format='minimal')
        print(message)


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    gmail = build('gmail', 'v1', credentials=creds)

    messages = getScholarMessages(gmail)
    print("Messages")
    print(messages)

    summarizeMessages(gmail, messages)


if __name__ == '__main__':
    main()