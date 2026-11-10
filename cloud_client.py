"""Call the SME Energy Advisor Lambda Function URL with a signed (SigV4) request.

The identity comes from an AWS profile (default: sme-agent, which may only invoke this URL).
boto3 is imported inside the function so the rest of the app still runs if it is missing."""
import json
import os
import time
import urllib.error
import urllib.request

REGION = "ap-southeast-2"
DEFAULT_PROFILE = os.environ.get("SME_AWS_PROFILE", "sme-agent")


def call_lambda(url: str, event: dict, profile: str | None = None, timeout: int = 30):
    """POST `event` as JSON to the Function URL. Returns (http_status, parsed_body, milliseconds)."""
    import boto3
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    session = boto3.Session(profile_name=(profile if profile is not None else DEFAULT_PROFILE) or None, region_name=REGION)
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("No AWS credentials found for this profile. Run: aws configure --profile sme-agent")

    body = json.dumps(event).encode()
    signed = AWSRequest(method="POST", url=url, data=body, headers={"content-type": "application/json"})
    SigV4Auth(credentials.get_frozen_credentials(), "lambda", REGION).add_auth(signed)
    request = urllib.request.Request(url, data=body, headers=dict(signed.headers), method="POST")

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, text = response.status, response.read().decode()
    except urllib.error.HTTPError as err:
        status, text = err.code, err.read().decode()
    elapsed_ms = (time.perf_counter() - started) * 1000

    try:
        data = json.loads(text)
    except ValueError:
        data = {"raw": text}
    return status, data, elapsed_ms