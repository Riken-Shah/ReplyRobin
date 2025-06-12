import pathlib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Gmail API Scopes (adjust if needed)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Folder to store user tokens
TOKEN_DIR = pathlib.Path("tokens")
TOKEN_DIR.mkdir(exist_ok=True)


def get_secret_file(user_email: str):
    """Returns the secret file for the authenticated user."""
    token_path = TOKEN_DIR / f"{user_email}.json"

    if token_path.exists():
        return str(token_path.as_posix())
    raise Exception("Secret file not found")


def save_secret_file(user_email: str, secret_file: str):
    """Saves the secret file for the authenticated user."""
    token_path = TOKEN_DIR / f"{user_email}.json"
    with open(token_path, "w") as f:
        f.write(secret_file)
