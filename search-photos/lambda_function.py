import os
import json
import boto3
import requests
from requests.auth import HTTPBasicAuth

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
    # 1) Extract the raw query from API Gateway
    params = event.get('queryStringParameters') or {}
    q = params.get('q','').strip()
    if not q:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"    # if you need CORS
            },
            "body": json.dumps({"results":[]})
        }

    # 2) Send to Lex V2 to get slots
    lex_resp = lex_client.recognize_text(
        botId        = LEX_BOT_ID,
        botAliasId   = LEX_ALIAS_ID,
        localeId     = LEX_LOCALE,
        sessionId    = context.aws_request_id,
        text         = q
    )
    slots = lex_resp.get('sessionState',{}).get('intent',{}).get('slots',{})

    # 3) Build a list of search terms from query1 (required) and query2 (optional)
    terms = []

    # query1 is required, so we expect it to always be present
    q1_slot = slots.get('query1')
    if q1_slot and q1_slot.get('value') and q1_slot['value'].get('interpretedValue'):
        terms.append(q1_slot['value']['interpretedValue'])

    # query2 is optional—only append if the user provided it
    q2_slot = slots.get('query2')
    if q2_slot and q2_slot.get('value') and q2_slot['value'].get('interpretedValue'):
        terms.append(q2_slot['value']['interpretedValue'])

    # If somehow query1 is missing or empty, bail out:
    if not terms:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"    # if you need CORS
            },
            "body": json.dumps({"results":[]})
        }

    # 4) Build Elasticsearch bool/should query with fuzzy match on query1 (and query2 if present)
    should_clauses = []

    # always add the required query1
    should_clauses.append({
        "match": {
            "labels": {
                "query": terms[0],
                "fuzziness": "AUTO"
            }
        }
    })

    # if query2 was provided, add it too
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

    # 5) Call OpenSearch
    url = f"{ES_ENDPOINT}/{ES_INDEX}/_search"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(ES_USERNAME, ES_PASSWORD),
        headers={"Content-Type":"application/json"},
        data=json.dumps(es_body)
    )
    resp.raise_for_status()
    hits = resp.json().get('hits',{}).get('hits',[])

    # 6) Format results per your API spec
    results = []
    for h in hits:
        src = h.get('_source',{})
        # presuming your S3 bucket is public or via presigned URL
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