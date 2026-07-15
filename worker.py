import os
import time
import json
import io
import boto3
from PIL import Image
from dotenv import load_dotenv

# Load local environment variables
load_dotenv()

# Initialize AWS clients
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

sqs_client = boto3.client(
    "sqs",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

QUEUE_URL = os.getenv("SQS_QUEUE_URL")

def process_image(bucket, file_key):
    """Downloads the image from S3, resizes it, and uploads it back (Supports PNG & JPEG)."""
    print(f" 📖 Reading raw image from S3: s3://{bucket}/{file_key}")
    
    # 1. Download image from S3 directly into memory
    s3_response = s3_client.get_object(Bucket=bucket, Key=file_key)
    image_data = s3_response['Body'].read()
    
    # 2. Open image with Pillow and create a thumbnail
    img = Image.open(io.BytesIO(image_data))
    img.thumbnail((150, 150)) # Resize to maximum 150x150px
    
    # 3. Handle formatting compatibility (Crucial for JPEG/JPG)
    img_format = img.format if img.format else 'PNG'
    if img_format.upper() == 'JPG':
        img_format = 'JPEG'
        
    # If a JPEG image has an alpha channel (RGBA), convert it to RGB 
    # because standard JPEG doesn't support transparency and will crash.
    if img.mode in ("RGBA", "P") and img_format == 'JPEG':
        img = img.convert("RGB")
    
    # 4. Save the processed image into an in-memory byte buffer
    output_buffer = io.BytesIO()
    img.save(output_buffer, format=img_format)
    output_buffer.seek(0)
    
    # 5. Generate new path and upload back to S3
    new_key = file_key.replace("uploads/", "processed/thumb_")
    print(f" 📤 Uploading processed thumbnail to S3: s3://{bucket}/{new_key}")
    
    s3_client.put_object(
        Bucket=bucket,
        Key=new_key,
        Body=output_buffer,
        ContentType=s3_response['ContentType'] # Keeps image/jpeg or image/png intact
    )
    print(" ✅ Processing complete!")

def start_worker():
    print("🚀 Worker service started. Polling SQS for jobs... (Press Ctrl+C to stop)")
    
    while True:
        try:
            # Long poll the SQS queue for new messages
            response = sqs_client.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=5  # Long polling reduces empty API calls
            )
            
            messages = response.get("Messages", [])
            if not messages:
                # No messages available, loop again
                continue
                
            for msg in messages:
                receipt_handle = msg["ReceiptHandle"]
                body = json.loads(msg["Body"])
                
                # Check if this is an S3 Test Notification message and skip it
                if "Event" in body and body.get("Event") == "s3:TestEvent":
                    print("Received S3 test event connection confirmation.")
                    sqs_client.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
                    continue

                # Parse the native S3 Event notification details
                s3_record = body.get("Records", [{}])[0].get("s3", {})
                bucket = s3_record.get("bucket", {}).get("name")
                file_key = s3_record.get("object", {}).get("key")
                
                if not bucket or not file_key:
                    continue
                    
                print(f"\n[ Job Received ] S3 Event confirmed upload for: {file_key}")
                
                # Run the image processing pipeline
                process_image(bucket, file_key)
                
                # Delete the message from the queue
                sqs_client.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
                print("[ Job Cleared ] Deleted message from SQS.")
                
            
        except Exception as e:
            print(f"❌ Error in worker cycle: {e}")
            time.sleep(2) # Prevent rapid fire crashing logs

if __name__ == "__main__":
    start_worker()


