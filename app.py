import os
import uuid
import json
import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load local environment variables
load_dotenv()

app = FastAPI(title="S3 Upload & Queue API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows your index.html file to call the API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    try:
        # Extract extension lowercased
        file_extension = filename.split(".")[-1].lower() if "." in filename else "bin"
        
        # 1. Correct the Content-Type mapping for JPEG files
        if file_extension in ["jpg", "jpeg"]:
            content_type = "image/jpeg"
            s3_extension = "jpeg"
        elif file_extension == "png":
            content_type = "image/png"
            s3_extension = "png"
        else:
            content_type = f"image/{file_extension}"
            s3_extension = file_extension

        # Create the unique key with the clean extension mapping
        unique_key = f"uploads/{uuid.uuid4()}.{s3_extension}"

        # 2. Generate presigned URL using the exact content_type
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": unique_key,
                "ContentType": content_type  # This will now perfectly match the browser header
            },
            ExpiresIn=300
        )

        return {
            "upload_url": presigned_url,
            "file_key": unique_key,
            "msg": "Presigned URL generated successfully!"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/get-download-url")
def get_download_url(file_key: str = Query(..., description="The original uploaded file key")):
    """
    Checks if the thumbnail exists in S3. If yes, returns a secure presigned download link.
    """
    # Map the upload key to its expected processed thumbnail path
    processed_key = file_key.replace("uploads/", "processed/thumb_")
    
    try:
        # 1. Verify if the worker has actually created the file in S3 yet
        s3_client.head_object(Bucket=BUCKET_NAME, Key=processed_key)
        
        # 2. If it exists, generate a temporary GET presigned URL
        download_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": processed_key
            },
            ExpiresIn=300 # Link stays valid for 5 minutes
        )
        
        return {"download_url": download_url}
        
    except s3_client.exceptions.ClientError as e:
        # If head_object returns a 404, it means the worker isn't done yet
        if e.response['Error']['Code'] == '404':
            raise HTTPException(status_code=404, detail="Thumbnail not ready yet")
        raise HTTPException(status_code=500, detail=str(e))