import os
import json
import pathlib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from .manage_secret_file import get_secret_file, save_secret_file

# Gmail API Scopes (adjust if needed)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

# Folder to store user tokens
TOKEN_DIR = pathlib.Path("tokens")
TOKEN_DIR.mkdir(exist_ok=True)


def get_user_credentials_file(user_email: str):
    """Get stored credentials for a user, or initiate OAuth flow."""
    token_path = TOKEN_DIR / f"{user_email}.json"

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_secret_file(user_email, creds.to_json())
    elif not creds or not creds.valid:
        # Launch browser to get new credentials
        flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        creds = flow.run_local_server(
            port=3001, access_type="offline", prompt="consent"
        )

        # Get authenticated user's email
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        user_email = profile["emailAddress"]

        # Save credentials with user email
        save_secret_file(user_email, creds.to_json())

    return get_secret_file(user_email)
