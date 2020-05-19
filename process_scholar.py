from __future__ import print_function
import pickle
import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apiclient import errors
import yaml

from bs4 import BeautifulSoup
from bs4 import Tag
import base64

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

send_email = True
show_scholar_emails = False
show_template = False
mark_read = True

ID = 'me'
scholar_email = 'scholaralerts-noreply@google.com'
email_subject = "Google Scholar Summary!"
email = ''
file_dir = os.path.dirname(__file__)

# match email entries
entry_start = "h3"
entry_length = 5

special_authors = []

def loadConfigs():
    configuration_file = os.getenv("HOME") + "/.scholar.yaml"

    if not os.path.exists(configuration_file):
        print("Please update scholar.yaml and copy to ~/.scholar.yaml")
        return False

    configs = yaml.load(open(configuration_file, 'r'), Loader=yaml.Loader)

    global email, email_subject, special_authors, mark_read, send_email

    email = configs.get('email', email)
    email_subject = configs.get('email_subject', email_subject)
    special_authors = configs.get('special_authors', special_authors)

    mark_read = configs.get('mark_read', mark_read)
    send_email = configs.get('send_email', send_email)

    return True

def subjectPriority():
    return [citesMe, isSpecial, isArticle, isCitation, isRelated]

def paperPriority():
    # returns a function that returns true if a paper has a subject that matches
    # a condition
    has = lambda f : lambda paper : any(f(s) for s in paper.subjects)

    return [has(citesMe), has(isSpecial), lambda x : len(x.subjects),
            has(isArticle), has(isCitation), has(isRelated)]

# Sort objects by decreasing priority
# Input is a list of values and a list of priorities or transformations, highest
# priority first
# (greater values indicate greater priority)
def prioritySort(values, priorities):
    # start by flattening the list
    l = list(values)

    for f in reversed(priorities):
        l.sort(key=f)
    return reversed(l)

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
    return "new citations" in s.lower()

# is an article
def isArticle(s):
    return "new articles" in s.lower()

# is an article
def isRelated(s):
    return "new related research" in s.lower()

# is new results
def isResults(s):
    return "new results" in s.lower()

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
        elif isArticle(s):
            # (is an article)
            return name + "(a)"
        elif isRelated(s):
            # (is an article)
            return name + "(r)"
        else:
            # (is unknown)
            return name + "(u)"

# returns true if a soup tag has facebook and twitter links
def isFacebook(tag):
    return not tag.find(name='img') == None

# Representation of a single paper alert and the related topics
class Paper:
    def __init__(self, body):
        self.body = body
        self.title = getTitle(body)
        self.subjects = []

    def addSubject(self, subject):
        self.subjects.append(subject)

    def subjectsString(self):
        s = prioritySort(self.subjects, priorities = subjectPriority())
        return ', '.join(map(abbreviateSubject, s))

    def summarize(self):
        print("Title: " + self.title)
        print("Subjects: " + self.subjectsString())
        print()

    def subjectsTag(self):
        tag = Tag(name="div")
        bold = Tag(name='b')
        tag.append(bold)
        tag.b.string = self.subjectsString()
        return tag

    # returns list of soup objects for the paper entry
    def soup(self):
        old = self.body
        subjects = self.subjectsTag()
        linebreak = BeautifulSoup("<br/>", 'html.parser')

        # Sometimes a paper entry will omit the summary in which case the entry
        # will instead have the Facebook/Twitter image links
        parts = None
        if not isFacebook(old[2]):
            # name/link, authors, summary, subject, break
            parts = [old[0], old[1], old[2], subjects, linebreak]
        else:
            # there is no summary
            parts = [old[0], old[1], subjects, linebreak]

        return parts

# Simple object for use in maintaining statistics
class PaperStats:
    num_emails = 0
    num_entries = 0
    num_unique = 0

    def printStats(self):
        print(
        'Processed results for:\n' +
        '  ' + str(self.num_emails) + ' emails\n'
        '  ' + str(self.num_entries) + ' entries\n'
        '  ' + str(self.num_unique) + ' unique papers'
        )

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

# Mark email as being read (remove unread label)
def markRead(gmail, message_id):
    body = {'removeLabelIds' : ['UNREAD']}
    return gmail.users().messages().modify(id=message_id, userId=ID, body=body).execute()

# Writes snippets from messages
def summarizeMessages(gmail, messages):
    for a in messages:
        message = readMessage(gmail, a['id'], format='minimal')
        #print(message['snippet'])

# Turn scholar updates into a map from titles to paper objects
def parseMessagePapers(gmail, messages, paper_stats = PaperStats()):
    papers = {}
    for a in messages:
        subject, raw_papers = parseMessage(gmail, a['id'])

        paper_stats.num_entries += len(raw_papers)

        for raw_paper in raw_papers:
            title = getTitle(raw_paper)
            if not title in papers:
                papers[title] = Paper(raw_paper)
            papers[title].addSubject(subject)

    paper_stats.num_emails = len(messages)
    paper_stats.num_unique = len(papers)

    return papers.values()

def parseMessage(gmail, message_id):
    message = readMessage(gmail, message_id)

    #print(message['snippet'])

    payload = message['payload']
    headers = payload.get('headers', [])
    subject = getSubject(headers)

    soup = getMessageSoup(message)

    if show_scholar_emails:
        print(soup.prettify())

    papers = dunkForPapers(soup)

    #print("Papers:")
    #for paper in papers:
        #print("Paper ************************************")
        #for tag in paper:
            #print(tag.prettify())
        #print()

    return subject, papers

# Sometimes the body is hidden or there are multiple bodies
# We have to go through this because Google now sends a multi-part message using
# amp
def getHtmlBody(payload):
    bodies = []

    def doBody(obj):
        if 'body' in obj and obj['mimeType'] == 'text/html':
            body = obj["body"]
            print(body.keys())
            bodies.append(body)

    doBody(payload)

    if 'parts' in payload:
        for part in payload['parts']:
            doBody(part)

    if len(bodies) == 0:
        print("Could not find a suitable (html) message body")
        return
    elif len(bodies) > 1:
        print("Found multiple html bodies")

    return bodies[0]

# soup the message. Used in turning the original message into a template
def getMessageSoup(message):
    payload = message['payload']
    body = getHtmlBody(payload)
    text = base64.urlsafe_b64decode(body['data'])
    return BeautifulSoup(text, 'html.parser')

# pulls subject from the header
def getSubject(headers):
    for header in headers:
        if header['name'] == 'Subject':
            return header['value']

# Pull tags that constitute paper entries
def dunkForPapers(soup):
    raw_papers = []
    contents = soup.body.div.contents
    for count, item in enumerate(contents):
        if item.name == entry_start:
            raw_papers.append(contents[count:count+entry_length])

    return raw_papers

# Delete body from an email so that it can be refilled
def constructSoupTemplate(gmail, message_description):
    message = readMessage(gmail, message_description['id'])
    soup = getMessageSoup(message)

    soup.body.div.clear()

    if show_template:
        print("Email template (contents go under <div>):")
        print(soup.prettify())

    return soup


# pulls title string from a raw paper
def getTitle(raw_paper):
    # title is in the first tag under 'a'
    return raw_paper[0].a.get_text()

# construct the output email
# see: https://medium.com/lyfepedia/sending-emails-with-gmail-api-and-python-49474e32c81f
def constructEmail(html = None):
    message = MIMEMultipart()
    message['To'] = email
    message['From'] = email
    message['Subject'] = email_subject
    message.attach(MIMEText(html, 'html'))

    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

# Takes template and paper objects and outputs digest email soup
# papers: list of paper objects
# template: soup to use as a template (contents go under div)
def constructDigestSoup(papers, template):
    soup = template

    # sort papers according to specified priorities
    papers = prioritySort(papers, priorities=paperPriority())

    for paper in papers:
        soup.body.div.extend(paper.soup())

    return soup


# see: https://medium.com/lyfepedia/sending-emails-with-gmail-api-and-python-49474e32c81f
def sendMessage(gmail, message):
  """Send an email message.
  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.
  Returns:
    Sent Message.
  """
  try:
    message = (gmail.users().messages().send(userId=ID, body=message)
               .execute())
    # print('Message Id: %s' % message['id'])
    return message
  except errors.HttpError as error:
    print('An error occurred: %s' % error)

def main():
    if not loadConfigs():
        return False

    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_file = file_dir + '/token.pickle'
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_file = file_dir + '/credentials.json'
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    gmail = build('gmail', 'v1', credentials=creds)

    messages = getScholarMessages(gmail)

    if len(messages) == 0:
        print('There are no scholar emails to process.')
    else:

        template = constructSoupTemplate(gmail, messages[0])

        paper_stats = PaperStats()
        papers = parseMessagePapers(gmail, messages, paper_stats)

        for paper in papers:
            paper.summarize()

        paper_stats.printStats()

        if send_email == True:
            print('Sending email')

            message_soup = constructDigestSoup(papers=papers, template=template)
            message = constructEmail(str(message_soup))
            sendMessage(gmail, message)

        if mark_read == True:
            print('Marking messages as "read"')

            for message in messages:
                markRead(gmail, message['id'])

if __name__ == '__main__':
    main()
