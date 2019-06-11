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

special_authors = ["Nathan Michael"]


# returns true if the subject is for articles that cite me
def citesMe(s):
    return s == "New citations to my articles"

def isSpecial(s):
    for author in special_authors:
        if author in s:
            return True
    return False

# pull name for authors
def parseName(s):
    return s[0:s.rfind("-")-1]

# check whether the subject refers to an author citation (or article)
def isCitation(s):
    return "new citations" in s

# is an article
def isArticle(s):
    return "new articles" in s

# is new results
def isResults(s):
    return "new results" in s

# parse results
def parseResults(s):
    return parseName(s)

# abbreviate the subject string
def abbreviateSubject(s):
    if citesMe(s):
        return "me(c)"
    elif isResults(s):
        # results for general queries
        return parseResults(s)
    else:
        # results for authors
        name = parseName(s)
        if isCitation(s):
            return name + "(c)"
        else:
            # (is an article)
            return name + "(a)"

# Representation of a single paper alert and the related topics
class Paper:
    def __init__(self, body):
        self.body = body
        self.title = getTitle(body)
        self.subjects = []

    def addSubject(self, subject):
        self.subjects.append(subject)

    def subjectsString(self):
        return ', '.join(map(abbreviateSubject, self.subjects))

    def summarize(self):
        print("Title: " + self.title)
        print("Subjects: " + self.subjectsString())
        print()


# Pull an email label such as "UNREAD"
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
        #print(message['snippet'])

# Turn scholar updates into a map from titles to paper objects
def parseMessages(gmail, messages):
    papers = {}
    for a in messages:
        subject, raw_papers = parseMessage(gmail, a['id'])
        for raw_paper in raw_papers:
            title = getTitle(raw_paper)
            if not title in papers:
                papers[title] = Paper(raw_paper)
            papers[title].addSubject(subject)
    return papers

def parseMessage(gmail, message_id):
    message = readMessage(gmail, message_id)

    #print(message['snippet'])

    payload = message['payload']
    headers = payload.get('headers', [])
    #print()
    subject = getSubject(headers)
    #print(subject)
    #print()

    #print('mimeType:')
    #print(payload['mimeType'])

    #print('Body:')
    body = payload['body']['data']

    text = base64.urlsafe_b64decode(body)
    soup = BeautifulSoup(text, 'html.parser')
    papers = dunkForPapers(soup)

    #print("Papers:")
    #for paper in papers:
        #print("Paper ************************************")
        #for tag in paper:
            #print(tag.prettify())
        #print()

    return subject, papers

# pulls subject from the header
def getSubject(headers):
    for header in headers:
        if header['name'] == 'Subject':
            return header['value']

def dunkForPapers(soup):
    raw_papers = []
    contents = soup.body.div.contents
    for count, item in enumerate(contents):
        if item.name == entry_start:
            raw_papers.append(contents[count:count+entry_length])

    return raw_papers

# pulls title string from a raw paper
def getTitle(raw_paper):
    # title is in the first tag under 'a'
    return raw_paper[0].a.get_text()


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

    papers = parseMessages(gmail, messages)
    for paper in papers.values():
        paper.summarize()


if __name__ == '__main__':
    main()
