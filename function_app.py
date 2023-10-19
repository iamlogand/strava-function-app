import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
import json
import requests
from datetime import datetime
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os
from dotenv import load_dotenv

app = func.FunctionApp()

@app.schedule(schedule="0 0 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    # Get blob connection string
    load_dotenv()
    if "CONNECTION_STRING" in os.environ:
        connection_string = os.environ["CONNECTION_STRING"]
    else:
        credential = DefaultAzureCredential()
        key_vault_url = "https://stravafunctionapp-vault.vault.azure.net"
        key_vault_client = SecretClient(vault_url=key_vault_url, credential=credential)
        connection_string = key_vault_client.get_secret("BlobConnectionString").value

    # Create blob clients
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client_for_tokens = blob_service_client.get_blob_client("secrets", "secrets.json")
    blob_client_for_records = blob_service_client.get_blob_client("records", "records.json")

    # Get secrets from blob storage
    raw_token_data = blob_client_for_tokens.download_blob().readall()
    token_data = json.loads(raw_token_data.decode('utf-8'))
    client_id = token_data["client_id"]
    client_secret = token_data["client_secret"]
    refresh_token = token_data["refresh"]

    # Get access token from Strava
    url = "https://www.strava.com/oauth/token"
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    response = requests.post(url, params=params)
    if response.status_code != 200:
        logging.error("Failed to get access token from Strava")
        return
    secrets_data = json.loads(response.text)
    access_token = secrets_data["access_token"]

    # Get records from Strava
    url = "https://www.strava.com/api/v3/clubs/1142418/activities"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logging.error("Failed to get data from Strava")
        return
    records_data = json.loads(response.text)

    # Upload club data to blob storage
    timestamp = {"timestamp": str(datetime.now())}
    records_data.insert(0, timestamp)
    blob_client_for_records.upload_blob(json.dumps(records_data), overwrite=True)

    logging.info('Python timer trigger function executed.')