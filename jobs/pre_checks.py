import os
from local_auth.auth import get_user_credentials_file


def self_checks():
    secret_file_path = os.getenv("GOOGLE_APP_CLIENT_SECRET", "client_secret.json")

    print("full path: ", os.path.join(os.getcwd(), secret_file_path))

    if not os.path.exists(os.path.join(os.getcwd(), secret_file_path)):
        raise FileNotFoundError(
            f"You must generate client secret and add it's path to {secret_file_path}.\nSee README.md for more information about the setup."
        )

    email = os.getenv("EMAIL_INBOX", None)

    if not email:
        raise ValueError(f"Please set `EMAIL_INBOX` in your .env")

    # Step 0: Access to GMAIL
    # Get the user's credentials file (stored as [email].json in our storage), this file is generated once
    # user authorizes as access to there gmail account.
    creds_file = get_user_credentials_file(email)

    if not creds_file:
        raise ValueError(f"Credential for {email} is empty")

    return creds_file
