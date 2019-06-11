from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from bs4 import BeautifulSoup
import base64

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

ID = 'me'
scholar_email = 'scholaralerts-noreply@google.com'

# match email entries
entry_start = "h3"
entry_length = 5

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

# Takes a message id and reads the message using google api
def readMessage(gmail, message_id, format="full"):
    return gmail.users().messages().get(id=message_id, userId=ID, format=format).execute()

# Writes snippets from messages
def summarizeMessages(gmail, messages):
    for a in messages:
        message = readMessage(gmail, a['id'], format='minimal')
        print(message['snippet'])

def parseMessages(gmail, messages):
    for a in messages:
        parseMessage(gmail, a['id'])

def parseMessage(gmail, message_id):
    message = readMessage(gmail, message_id)

    print(message['snippet'])

    payload = message['payload']
    headers = payload.get('headers', [])
    print()
    subject = getSubject(headers)
    print(subject)
    print()

    print('mimeType:')
    print(payload['mimeType'])

    print('Body:')
    body = payload['body']['data']

    text = base64.urlsafe_b64decode(body)
    soup = BeautifulSoup(text, 'html.parser')
    papers = dunkForPapers(soup)

    print("Papers:")
    for paper in papers:
        print("Paper")
        for tag in paper:
            print(tag.prettify())

# pulls subject from the header
def getSubject(headers):
    for header in headers:
        print(header['name'])
    for header in headers:
        if header['name'] == 'Subject':
            return header['value']

def dunkForPapers(soup):
    raw_papers = []
    contents = soup.body.div.contents
    for count, item in enumerate(contents):
        print("Contents: " + str(count))
        if item.name == entry_start:
            print("found entry!")
            raw_papers.append(contents[count:count+entry_length])

    return raw_papers


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

    parseMessages(gmail, messages)


if __name__ == '__main__':
    main()
