from google_auth_oauthlib.flow import InstalledAppFlow
import structlog
log = structlog.get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]

flow = InstalledAppFlow.from_client_secrets_file(
    'client_secrets.json',
    scopes=SCOPES
)
creds = flow.run_local_server(port=0)
log.info("refresh_token_generated", refresh_token=creds.refresh_token)