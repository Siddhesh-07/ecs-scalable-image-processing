# ============================================
# S3 BUCKET - IMAGE STORAGE
# ============================================

resource "aws_s3_bucket" "image_bucket" {
  bucket = "my-app-image-uploads-siddhesh-07"

  tags = {
    Name        = "image-processing-bucket"
    Environment = "dev"
  }
}

# ============================================
# SQS QUEUE - IMAGE PROCESSING
# ============================================

resource "aws_sqs_queue" "image_processing" {
  name = "image-processing-queue"

  visibility_timeout_seconds = 300

  message_retention_seconds = 86400

  tags = {
    Name        = "image-processing-queue"
    Environment = "dev"
  }
}

