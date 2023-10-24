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
import time

app = func.FunctionApp()

@app.schedule(schedule="0 0 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')
    start_time = time.perf_counter()

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
    blob_client_for_records = blob_service_client.get_blob_client("records2", "records.json")

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
        logging.error("Failed to get records from Strava")
        return
    new_records = json.loads(response.text)

    # Get existing records from blob storage
    raw_records_data = blob_client_for_records.download_blob().readall()
    existing_records = json.loads(raw_records_data.decode('utf-8'))

    # Add any new records that are not in existing records to existing records
    new_record_count = 0
    for new_record in new_records:
        is_new = check_if_new_record(new_record, existing_records)
        if (is_new):
            new_record_count += 1
            existing_records.insert(0, new_record)

    # Add timestamps to all records without a timestamp
    for record in existing_records:
        if "timestamp" not in record:
            record["timestamp"] = str(datetime.now())

    # Upload records to blob storage
    blob_client_for_records.upload_blob(json.dumps(existing_records), overwrite=True)

    # Log done message
    end_time = time.perf_counter()
    elapsed_time = int((end_time - start_time) * 1000) / 1000
    logging.info(f'Function execution done. Added {new_record_count} new records in {elapsed_time} seconds.')


# Checks if the record is in the record list
def check_if_new_record(record, record_list):
    is_new = True
    for r in record_list:
        if (record["athlete"] == r["athlete"] and record["distance"] == r["distance"] and record["moving_time"] == r["moving_time"] and record["elapsed_time"] == r["elapsed_time"] and record["total_elevation_gain"] == r["total_elevation_gain"] and record["type"] == r["type"] and record["sport_type"] == r["sport_type"]):
            is_new = False
    return is_new


'''
Example showing the expected format of a record

{
    "resource_state": 2,
    "athlete": {
        "resource_state": 2,
        "firstname": "Peter",
        "lastname": "A."
    },
    "name": "Evening Ride",
    "distance": 7159.6,
    "moving_time": 1856,
    "elapsed_time": 2098,
    "total_elevation_gain": 88.0,
    "type": "Ride",
    "sport_type": "Ride",
    "workout_type":None
}

'''
