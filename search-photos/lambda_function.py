import os
import json
import boto3
import requests
from requests.auth import HTTPBasicAuth

# Environment Variables
REGION = os.environ['REGION']
ES_ENDPOINT = os.environ['ES_ENDPOINT']
ES_USERNAME = os.environ['ES_USERNAME']
ES_PASSWORD = os.environ['ES_PASSWORD']
ES_INDEX = os.environ['ES_INDEX']
LEX_BOT_ID = os.environ['BOT_ID']
LEX_ALIAS_ID = os.environ['BOT_ALIAS_ID']
LEX_LOCALE = os.environ['LOCALE_ID']

# AWS clients
lex_client = boto3.client('lexv2-runtime', region_name=REGION)
s3_client = boto3.client('s3', region_name=REGION)

def lambda_handler(event, context):
    # Extract the user query. 
    params = event.get('queryStringParameters') or {}
    q = params.get('q','').strip()

    # If the user did not enter a query, return an empty list. 
    if not q:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"results":[]})
        }

    # Disambiguate the user query using the AWS Lex bot. 
    lex_resp = lex_client.recognize_text(
        botId        = LEX_BOT_ID,
        botAliasId   = LEX_ALIAS_ID,
        localeId     = LEX_LOCALE,
        sessionId    = context.aws_request_id,
        text         = q
    )
    slots = lex_resp.get('sessionState',{}).get('intent',{}).get('slots',{})

    # Extract the "query1" and "query2" slots from the Lex response. 
    terms = []

    # "query1" is a required slot. 
    q1_slot = slots.get('query1')
    if q1_slot and q1_slot.get('value') and q1_slot['value'].get('interpretedValue'):
        terms.append(q1_slot['value']['interpretedValue'])

    # "query2" is an optional slot. 
    q2_slot = slots.get('query2')
    if q2_slot and q2_slot.get('value') and q2_slot['value'].get('interpretedValue'):
        terms.append(q2_slot['value']['interpretedValue'])

    # If the user query is not a SearchIntent, return an empty list. 
    if not terms:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"results":[]})
        }

    # Construct the OpenSearch query. 
    should_clauses = []

    should_clauses.append({
        "match": {
            "labels": {
                "query": terms[0],
                "fuzziness": "AUTO"
            }
        }
    })

    if len(terms) > 1:
        should_clauses.append({
            "match": {
                "labels": {
                    "query": terms[1],
                    "fuzziness": "AUTO"
                }
            }
        })

    es_body = {
        "query": {
            "bool": {
                "should": should_clauses,
                "minimum_should_match": 1
            }
        }
    }

    # Search the "photos" OpenSearch index for results via the HTTP GET request. 
    url = f"{ES_ENDPOINT}/{ES_INDEX}/_search"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(ES_USERNAME, ES_PASSWORD),
        headers={"Content-Type":"application/json"},
        data=json.dumps(es_body)
    )
    resp.raise_for_status()
    hits = resp.json().get('hits',{}).get('hits',[])

    # Format the result based on the API spec. 
    results = []
    for h in hits:
        src = h.get('_source',{})
        # Construct the S3 Object URL for the image. 
        url = f"https://{src['bucket']}.s3.amazonaws.com/{src['objectKey']}"
        results.append({
            "url":    url,
            "labels": src.get('labels',[])
        })

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"    # if you need CORS
        },
        "body": json.dumps({"results": results})
    }
