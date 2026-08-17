# ============================================
# ECR REPOSITORY - FASTAPI API
# ============================================

resource "aws_ecr_repository" "fastapi_api" {
  name                 = "fastapi-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "fastapi-api"
    Environment = "dev"
  }
}


# ============================================
# ECR REPOSITORY - WORKER
# ============================================

resource "aws_ecr_repository" "image_worker" {
  name                 = "image-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "image-worker"
    Environment = "dev"
  }
}
