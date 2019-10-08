## Usage
Run `process_scholar.py` using Python 3.
This script does not take any arguments.

## Configuration
Copy `scholar.yaml` to `~/.scholar.yaml` and edit fields as appropriate.
This script uses the Gmail api which ask you to log in when you first run this
script.
Refer to [this](https://developers.google.com/gmail/api/quickstart/python) page
for configuration and installation of the Gmail API.

### Application credentials
We do not currently distributed credentials for this application so you will
have to create your own.
The [Gmail Python Quickstart](https://developers.google.com/gmail/api/quickstart/python)
will allow you to request a set of application credentials.
Download these credentials, and place `credentials.json` in the application
directory.
