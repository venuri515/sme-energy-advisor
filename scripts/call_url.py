"""Call a Lambda Function URL that uses AWS_IAM auth by signing the request (SigV4).
    python scripts/call_url.py <function-url> <event.json> [profile]
The profile decides WHO you are. The URL only accepts callers whose IAM permissions allow it."""
import json
import sys
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = "ap-southeast-2"

if len(sys.argv) < 3:
    sys.exit(__doc__)

url, event_path = sys.argv[1], sys.argv[2]
profile = (sys.argv[3] if len(sys.argv) > 3 else "default") or None
creds = boto3.Session(profile_name=profile, region_name=REGION).get_credentials().get_frozen_credentials()

body = open(event_path, "rb").read()
signed = AWSRequest(method="POST", url=url, data=body, headers={"content-type": "application/json"})
SigV4Auth(creds, "lambda", REGION).add_auth(signed)   # adds the Authorization and X-Amz-Date headers

request = urllib.request.Request(url, data=body, headers=dict(signed.headers), method="POST")
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        status, text = response.status, response.read().decode()
except urllib.error.HTTPError as err:
    status, text = err.code, err.read().decode()

print(status)
try:
    print(json.dumps(json.loads(text), indent=2))
except ValueError:
    print(text)