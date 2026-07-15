import os
import uuid
import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Cloud Image Processor")

# Mount static folder for index.html and images
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
QUEUE_URL = os.getenv("SQS_QUEUE_URL")

# ====================== HEALTH CHECK  ======================
@app.get("/health")
def health_check():
    """Health check endpoint for ALB Target Group"""
    return {"status": "healthy", "service": "cloud-image-processor"}


# ====================== FRONTEND ======================
@app.get("/")
def read_index():
    """Serve the main HTML page"""
    return FileResponse("static/index.html")

# ====================== API ENDPOINTS ======================
@app.get("/generate-upload-url")
def generate_upload_url(filename: str = Query(..., description="The original filename")):
    try:
        # Extract extension lowercased
        file_extension = filename.split(".")[-1].lower() if "." in filename else "bin"
        
        # Correct Content-Type mapping
        if file_extension in ["jpg", "jpeg"]:
            content_type = "image/jpeg"
            s3_extension = "jpeg"
        elif file_extension == "png":
            content_type = "image/png"
            s3_extension = "png"
        else:
            content_type = f"image/{file_extension}"
            s3_extension = file_extension

        unique_key = f"uploads/{uuid.uuid4()}.{s3_extension}"

        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": unique_key,
                "ContentType": content_type
            },
            ExpiresIn=300
        )

        return {
            "upload_url": presigned_url,
            "file_key": unique_key,
            "msg": "Presigned URL generated successfully!"
        }

    except Exception as e:
        print(f"Error in generate-upload-url: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-download-url")
def get_download_url(file_key: str = Query(..., description="The original uploaded file key")):
    """
    Checks if the thumbnail exists in S3. If yes, returns a secure presigned download link.
    """
    processed_key = file_key.replace("uploads/", "processed/thumb_")
    
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=processed_key)
        
        download_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": processed_key
            },
            ExpiresIn=300
        )
        
        return {"download_url": download_url}
        
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            raise HTTPException(status_code=404, detail="Thumbnail not ready yet")
        raise HTTPException(status_code=500, detail=str(e))