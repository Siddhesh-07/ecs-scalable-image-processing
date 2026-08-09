# ============================================
# ALB SECURITY GROUP
# ============================================

resource "aws_security_group" "alb_sg" {
  name        = "ecs-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.ecs_vpc.id

  # Allow HTTP traffic from the internet
  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound traffic
  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ecs-alb-sg"
  }
}


# ============================================
# FARGATE/API SECURITY GROUP
# ============================================

resource "aws_security_group" "fargate_sg" {
  name        = "ecs-fargate-sg"
  description = "Security group for Fargate API tasks"
  vpc_id      = aws_vpc.ecs_vpc.id

  # Only ALB can access the API on port 8000
  ingress {
    description     = "API traffic from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  # Allow outbound access to AWS services
  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ecs-fargate-sg"
  }
}


# ============================================
# ECS EC2 WORKER SECURITY GROUP
# ============================================

resource "aws_security_group" "worker_sg" {
  name        = "ecs-worker-sg"
  description = "Security group for ECS EC2 worker instances"
  vpc_id      = aws_vpc.ecs_vpc.id

  # SSH access - useful for your learning/debugging
  ingress {
    description = "SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow outbound access to AWS services
  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ecs-worker-sg"
  }
}
