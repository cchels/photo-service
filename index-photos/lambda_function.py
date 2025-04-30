import os
import json
import boto3
import datetime
import requests
from requests.auth import HTTPBasicAuth

REGION = os.environ['REGION']
ES_ENDPOINT = os.environ['ES_ENDPOINT']
ES_USERNAME = os.environ['ES_USERNAME']
ES_PASSWORD = os.environ['ES_PASSWORD']
ES_INDEX = os.environ['ES_INDEX']

# AWS clients
rek = boto3.client('rekognition', region_name=REGION)
s3  = boto3.client('s3', region_name=REGION)

def lambda_handler(event, context):
    # 1) Parse the S3 PUT event
    rec = event['Records'][0]['s3']
    bucket = rec['bucket']['name']
    key = rec['object']['key']

    # 2) Call Rekognition.detect_labels
    rek_resp = rek.detect_labels(
        Image={'S3Object':{'Bucket':bucket,'Name':key}},
    )
    detected = [lbl['Name'] for lbl in rek_resp['Labels']]

    # 3) Call S3.head_object to get any custom labels
    head = s3.head_object(Bucket=bucket, Key=key)
    meta = head.get('Metadata', {})
    custom = meta.get('customlabels', '')
    custom_labels = [c.strip() for c in custom.split(',') if c.strip()]

    # 4) Merge & dedupe
    labels = list({*custom_labels, *detected})

    # 5) Build the JSON document
    doc = {
        "objectKey":        key,
        "bucket":           bucket,
        "createdTimestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "labels":           labels
    }

    # 6) Send to OpenSearch via HTTP POST + Basic auth
    url = f"{ES_ENDPOINT}/{ES_INDEX}/_doc"
    headers = {"Content-Type": "application/json"}
    auth = HTTPBasicAuth(ES_USERNAME, ES_PASSWORD)

    resp = requests.post(url, auth=auth, headers=headers, data=json.dumps(doc))
    if resp.status_code not in (200, 201):
        # Log and raise so Lambda shows an error
        print(f"Elasticsearch error [{resp.status_code}]: {resp.text}")
        raise Exception(f"Indexing failed: {resp.status_code}")

    print(f"Indexed {key}: {labels}")
    return {
        "statusCode": resp.status_code,
        "body":       json.dumps({"indexed": key})
    }