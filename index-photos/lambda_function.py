import os
import json
import boto3
import datetime
import requests
from requests.auth import HTTPBasicAuth

# Environment Variables
REGION = os.environ['REGION']
ES_ENDPOINT = os.environ['ES_ENDPOINT']
ES_USERNAME = os.environ['ES_USERNAME']
ES_PASSWORD = os.environ['ES_PASSWORD']
ES_INDEX = os.environ['ES_INDEX']

# AWS clients
rek = boto3.client('rekognition', region_name=REGION)
s3  = boto3.client('s3', region_name=REGION)

def lambda_handler(event, context):
    # Parse out the S3 Bucket name and Image name. 
    rec = event['Records'][0]['s3']
    bucket = rec['bucket']['name']
    key = rec['object']['key']

    # Detect labels in the image, using AWS Rekognition ("detect_labels" method). 
    rek_resp = rek.detect_labels(
        Image={'S3Object':{'Bucket':bucket,'Name':key}},
    )
    detected = [lbl['Name'] for lbl in rek_resp['Labels']]

    # Use the S3 SDK's "head_object" method to retrieve the "x-amz-meta-customLabels" metadata field, if applicable. 
    head = s3.head_object(Bucket=bucket, Key=key)
    meta = head.get('Metadata', {})
    custom = meta.get('customlabels', '')
    custom_labels = [c.strip() for c in custom.split(',') if c.strip()]

    # Merge the labels detected by Rekognition with the custom labels provided by the user. 
    labels = list({*custom_labels, *detected})

    # Build the JSON document to be stored in an OpenSearch index ("photos"). 
    doc = {
        "objectKey":        key,
        "bucket":           bucket,
        "createdTimestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "labels":           labels
    }

    # Store the JSON document to OpenSearch Index via HTTP POST request
    url = f"{ES_ENDPOINT}/{ES_INDEX}/_doc"
    headers = {"Content-Type": "application/json"}
    auth = HTTPBasicAuth(ES_USERNAME, ES_PASSWORD)
    resp = requests.post(url, auth=auth, headers=headers, data=json.dumps(doc))
    if resp.status_code not in (200, 201):
        print(f"Elasticsearch error [{resp.status_code}]: {resp.text}")
        raise Exception(f"Indexing failed: {resp.status_code}")

    print(f"Indexed {key}: {labels}")
    return {
        "statusCode": resp.status_code,
        "body":       json.dumps({"indexed": key})
    }
