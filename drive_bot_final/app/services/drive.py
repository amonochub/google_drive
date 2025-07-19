from googleapiclient.discovery import build
from google.oauth2 import service_account
from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_file(
    settings.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
)
drive = build("drive", "v3", credentials=creds)

async def list_folders():
    res = drive.files().list(q=f"'{settings.ROOT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder'", fields="files(name, id, size)").execute()
    return [(f["name"], f.get("size", "?")) for f in res.get("files", [])]

async def upload_file(bytestream, name):
    media = {"name": name, "parents": [settings.ROOT_FOLDER_ID]}
    drive.files().create(body=media, media_body=bytestream, fields="id").execute()
