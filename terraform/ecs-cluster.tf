# ============================================
# ECS CLUSTER
# ============================================

resource "aws_ecs_cluster" "image_cluster" {
  name = "image-cluster"

  tags = {
    Name        = "image-cluster"
    Environment = "dev"
  }
}


# ============================================
# ECS-OPTIMIZED AMAZON LINUX 2023 AMI
# ============================================

data "aws_ssm_parameter" "ecs_ami" {
  name = "/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id"
}


# ============================================
# EC2 LAUNCH TEMPLATE
# ============================================

resource "aws_launch_template" "ecs_worker" {
  name_prefix   = "ecs-worker-"
  image_id      = data.aws_ssm_parameter.ecs_ami.value
  instance_type = "t3.small"

  iam_instance_profile {
    name = aws_iam_instance_profile.ecs_ec2_instance_profile.name
  }

  vpc_security_group_ids = [
    aws_security_group.ecs_instance_sg.id
  ]

  user_data = base64encode(<<-EOF
    #!/bin/bash

    echo "ECS_CLUSTER=${aws_ecs_cluster.image_cluster.name}" >> /etc/ecs/ecs.config
  EOF
  )

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name        = "ecs-worker-instance"
      Environment = "dev"
    }
  }
}


# ============================================
# AUTO SCALING GROUP
# ============================================

resource "aws_autoscaling_group" "ecs_worker" {
  name = "ecs-worker-asg"

  min_size         = 1
  max_size         = 2
  desired_capacity = 1

  vpc_zone_identifier = [
    aws_subnet.private_1.id,
    aws_subnet.private_2.id
  ]

  launch_template {
    id      = aws_launch_template.ecs_worker.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "ecs-worker-instance"
    propagate_at_launch = true
  }
}


# ============================================
# ECS CAPACITY PROVIDER
# ============================================

resource "aws_ecs_capacity_provider" "ec2_worker" {
  name = "ec2-worker-capacity-provider"

  auto_scaling_group_provider {
    auto_scaling_group_arn = aws_autoscaling_group.ecs_worker.arn

    managed_scaling {
      status                    = "ENABLED"
      target_capacity           = 100
      minimum_scaling_step_size = 1
      maximum_scaling_step_size = 2
    }

    managed_termination_protection = "DISABLED"
  }
}


# ============================================
# ATTACH EC2 CAPACITY PROVIDER TO CLUSTER
# ============================================

resource "aws_ecs_cluster_capacity_providers" "image_cluster" {
  cluster_name = aws_ecs_cluster.image_cluster.name

  capacity_providers = [
    aws_ecs_capacity_provider.ec2_worker.name
  ]

  default_capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.ec2_worker.name
    weight            = 1
    base              = 1
  }
}
