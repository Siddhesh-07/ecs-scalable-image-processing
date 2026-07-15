import os
import uuid
import json
import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv

# Load local environment variables
load_dotenv()

app = FastAPI(title="S3 Upload & Queue API")

# Initialize AWS clients
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
    config=Config(signature_version="s3v4")
)

sqs_client = boto3.client(
    "sqs",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
QUEUE_URL = os.getenv("SQS_QUEUE_URL")

@app.get("/generate-upload-url")
def generate_upload_url(filename: str = Query(..., description="The original filename")):
    """
    Generates a secure presigned URL and pushes a message to SQS.
    """
    try:
        file_extension = filename.split(".")[-1] if "." in filename else "bin"
        unique_key = f"uploads/{uuid.uuid4()}.{file_extension}"

        # 1. Generate presigned PUT URL
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": unique_key,
                "ContentType": f"image/{file_extension}"
            },
            ExpiresIn=300
        )

        # 2. Build the SQS payload
        message_body = {
            "bucket": BUCKET_NAME,
            "file_key": unique_key,
            "status": "pending_upload"
        }

        # 3. Send message to SQS
        sqs_client.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(message_body)
        )

        return {
            "upload_url": presigned_url,
            "file_key": unique_key,
            "msg": "Presigned URL generated and SQS job queued!"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))