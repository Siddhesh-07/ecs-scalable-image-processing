# ============================================
# IAM TRUST POLICY
# ============================================

data "aws_iam_policy_document" "ecs_tasks_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}


# ============================================
# ECS TASK EXECUTION ROLE
# Used by ECS to:
# - Pull images from ECR
# - Send container logs to CloudWatch
# ============================================

resource "aws_iam_role" "ecs_task_execution_role" {
  name = "ecsTaskExecutionRole"

  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json

  tags = {
    Name = "ecs-task-execution-role"
  }
}


resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role = aws_iam_role.ecs_task_execution_role.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


# ============================================
# API TASK ROLE
# FastAPI needs:
# - S3 access
# - SQS SendMessage
# ============================================

resource "aws_iam_role" "api_task_role" {
  name = "image-processor-api-task-role"

  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json

  tags = {
    Name = "image-processor-api-task-role"
  }
}


resource "aws_iam_role_policy" "api_task_policy" {
  name = "image-processor-api-policy"
  role = aws_iam_role.api_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [

      # S3 permissions for generating presigned
      # upload/download URLs and checking objects
      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:HeadObject"
        ]

        Resource = "${aws_s3_bucket.image_bucket.arn}/*"
      },

      # Send image-processing jobs to SQS
      {
        Effect = "Allow"

        Action = [
          "sqs:SendMessage"
        ]

        Resource = aws_sqs_queue.image_processing.arn
      }
    ]
  })
}


# ============================================
# WORKER TASK ROLE
# Worker needs:
# - Read messages from SQS
# - Delete processed messages
# - Read images from S3
# - Upload processed images to S3
# ============================================

resource "aws_iam_role" "worker_task_role" {
  name = "image-processor-worker-task-role"

  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json

  tags = {
    Name = "image-processor-worker-task-role"
  }
}


resource "aws_iam_role_policy" "worker_task_policy" {
  name = "image-processor-worker-policy"
  role = aws_iam_role.worker_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [

      # Receive and delete messages from SQS
      {
        Effect = "Allow"

        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]

        Resource = aws_sqs_queue.image_processing.arn
      },

      # Worker downloads original images
      # and uploads processed images
      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]

        Resource = "${aws_s3_bucket.image_bucket.arn}/*"
      }
    ]
  })
}


# ============================================
# ECS EC2 INSTANCE ROLE
# Used by the ECS agent running on EC2
# ============================================

data "aws_iam_policy_document" "ecs_ec2_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}


resource "aws_iam_role" "ecs_ec2_instance_role" {
  name = "ecsInstanceRole"

  assume_role_policy = data.aws_iam_policy_document.ecs_ec2_assume_role.json

  tags = {
    Name = "ecs-instance-role"
  }
}


resource "aws_iam_role_policy_attachment" "ecs_ec2_instance_policy" {
  role = aws_iam_role.ecs_ec2_instance_role.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}


# ============================================
# EC2 INSTANCE PROFILE
# Required to attach IAM role to EC2
# ============================================

resource "aws_iam_instance_profile" "ecs_ec2_instance_profile" {
  name = "ecsInstanceProfile"
  role = aws_iam_role.ecs_ec2_instance_role.name

  tags = {
    Name = "ecs-instance-profile"
  }
}
