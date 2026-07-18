# 🚀 ECS - Image Processing

**A production-grade, event-driven image processing pipeline built on AWS ECS, demonstrating scalability, cost optimization, and DevOps best practices.**

---

## 📐 System Architecture

```                                   🌐 Internet User
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 AWS VPC                                     │
│                                                                             │
│  ┌────────────────────────── Public Subnets ─────────────────────────────┐  │
│  │                                                                       │  │
│  │        ┌──────────────────────────────────────────────┐               │  │
│  │        │      Application Load Balancer (ALB)         │               │  │
│  │        └──────────────────────┬───────────────────────┘               │  │
│  └───────────────────────────────┼───────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│  ┌────────────────────────── Private Subnets ─────────────────────────────┐ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────┐      │ │
│  │  │             ECS Fargate Service (Frontend/API)               │      │ │
│  │  │                                                              │      │ │
│  │  │ • Serves Web Application                                     │      │ │
│  │  │ • Generates S3 Presigned Upload URLs                         │      │ │
│  │  │ • Generates Download URLs                                    │      │ │
│  │  └──────────────────────────────┬───────────────────────────────┘      │ │
│  │                                 │                                      │ │
│  │                                 ▼                                      │ │
│  │                    ┌──────────────────────────┐                        │ │
│  │                    │        Amazon S3         │                        │ │
│  │                    │ uploads/  processed/     │                        │ │
│  │                    └───────────┬──────────────┘                        │ │
│  │                                │                                       │ │
│  │                    S3 Object Created Event                             │ │
│  │                                ▼                                       │ │
│  │                    ┌──────────────────────────┐                        │ │
│  │                    │        Amazon SQS        │                        │ │
│  │                    └───────────┬──────────────┘                        │ │
│  │                                │                                       │ │
│  │                                ▼                                       │ │
│  │      ┌─────────────────────────────────────────────────────────┐       │ │
│  │      │          ECS EC2 Worker Service (Python + Pillow)       │       │ │
│  │      │                                                         │       │ │
│  │      │ • Poll SQS                                              │       │ │
│  │      │ • Download Original Image                               │       │ │
│  │      │ • Resize / Compress Image                               │       │ │
│  │      │ • Upload Thumbnail to S3                                │       │ │
│  │      └─────────────────────────────────────────────────────────┘       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                                 ▲
                                 │
                       Download Thumbnail
                                 │
                           🌐 Internet User
```

---

## 🎯 Producer-Consumer Architecture Pattern

This project implements a **classic asynchronous producer-consumer pattern** using AWS services:


### **Why Producer-Consumer Pattern?**

| Benefit | How It Helps |
|---------|-------------|
| **Decoupling** | Producer & consumer are independent; changes to one don't affect the other |
| **Scalability** | Producer handles 1000 uploads/sec; consumers scale 1-6 tasks as needed |
| **Load Leveling** | Queue acts as buffer; prevents consumer overload if upload spike occurs |
| **Reliability** | If consumer crashes, message stays in queue; auto-replaced task continues |
| **Cost Optimization** | Scale workers up/down based on queue depth (pay only for what's needed) |
| **Latency Decoupling** | User gets fast response (presigned URL) without waiting for processing |

### **Real-World Example Flow**

```
Timeline:

T+0s   User clicks "Upload" with 50MB image
       └─ Producer generates presigned URL (instant)
       └─ User browser directly uploads to S3 (5 seconds)

T+5s   User sees "Uploaded! Processing..."
       └─ S3 object created event → SQS message
       └─ User doesn't wait; can close browser

T+10s  Consumer #1 receives SQS message (long polling)
       └─ Downloads 50MB image from S3
       └─ Resizes to 150x150px (< 1MB)
       └─ Uploads back to S3

T+12s  Frontend polls /get-download-url
       └─ Finds thumbnail in S3
       └─ Returns presigned download URL
       └─ User downloads processed image

Result: User got response in 5 seconds
        Processing happened in background (asynchronously)
        No blocking between upload and download
``` 

---

## 🏗️ ECS Implementation

### **Architecture Decisions**

Consolidate frontend (Fargate) and worker (EC2) workloads into a single `image-cluster` using a heterogeneous capacity provider strategy. This eliminates cluster management overhead while maintaining workload isolation through service-level capacity provider configuration.

### **ECS Cluster Specs**

#### **Cluster: image-cluster**

| Component | Specification |
|-----------|---|
| **Name** | `image-cluster` |
| **Type** | Hybrid (Fargate + EC2) |
| **Network Mode** | `awsvpc` (Fargate tasks), `bridge` (EC2 tasks) |
| **Region** | us-east-1 |

---

### **Capacity Providers**

#### **Capacity Provider 1: Fargate On-Demand**

| Component | Specification |
|-----------|---|
| **Name** | `fargate-cp` |
| **Launch Type** | FARGATE |
| **Network Mode** | `awsvpc` |
| **Use Case** | Baseline frontend API (always available) |
| **Cost Model** | Pay-per-second (on-demand) |
| **Best For** | Reliable, stateless workloads |

---

#### **Capacity Provider 2: Fargate Spot**

| Component | Specification |
|-----------|---|
| **Name** | `fargate-spot-cp` |
| **Launch Type** | FARGATE_SPOT |
| **Network Mode** | `awsvpc` |
| **Use Case** | Auto-scale frontend API (burst traffic) |
| **Cost Savings** | ~70% vs on-demand Fargate |
| **Best For** | Fault-tolerant, scalable workloads |
| **Task Weight Ratio** | FARGATE:FARGATE_SPOT = 1:2 |

---

#### **Capacity Provider 3: EC2 On-demand (spot is not for free tier)**

| Component | Specification |
|-----------|---|
| **Name** | `ec2-spot-cp` |
| **Launch Type** | EC2 |
| **Network Mode** | `bridge` (default for EC2) |
| **Instance Type** | t3.small |
| **AMI** | Amazon Linux 2023 |
| **ASG Config** | Min: 1 → Desired: 2 → Max: 2 |
| **Best For** | Long-running batch jobs, image processing |
| **Auto-Scaling** | CPU > 50%, scale-up: 60s, scale-down: 300s |

---


### **Task Definition Specs**

#### **Frontend Task Definition**

```yaml
Family: frontend-task-def
Network Mode: awsvpc (Fargate requirement)
Launch Type: Fargate
CPU: 512 (0.5 vCPU)
Memory: 1024 MB

Container: api-container
  Image: 317990169591.dkr.ecr.us-east-1.amazonaws.com/fastapi-api:latest
  Port: 8000 (TCP)
  
Execution Role: ecsTaskExecutionRole
  - Permissions: Pull from ECR, Push logs to CloudWatch
  
Environment Variables:
  PORT: 8000
  ENV: production
  SQS_QUEUE_URL: https://sqs.us-east-1.amazonaws.com/317990169591/image-processing-queue
  S3_BUCKET_NAME: my-app-image-uploads-siddhesh-07
  AWS_REGION: us-east-1
  AWS_ACCESS_KEY_ID: (from .env)
  AWS_SECRET_ACCESS_KEY: (from .env)
  
Log Configuration: CloudWatch
  Log Group: /ecs/frontend-task-def
  Stream Prefix: ecs
  Region: us-east-1
```

#### **Worker Task Definition**

```yaml
Family: worker-task-def
Network Mode: bridge (EC2 requirement)
Launch Type: EC2
CPU: 512 (0.5 vCPU)
Memory: 1024 MB

Container: worker-container
  Image: 317990169591.dkr.ecr.us-east-1.amazonaws.com/image-processor:latest
  
Execution Role: ecsTaskExecutionRole
  - Permissions: Pull from ECR, Push logs to CloudWatch
  
Task Role: ecsWorkerTaskRole
  - Permissions: SQS (ReceiveMessage, DeleteMessage), S3 (GetObject, PutObject)
  
Environment Variables:
  SQS_QUEUE_URL: https://sqs.us-east-1.amazonaws.com/317990169591/image-processing-queue
  S3_BUCKET_NAME: my-app-image-uploads-siddhesh-07
  AWS_REGION: us-east-1
  AWS_ACCESS_KEY_ID: (from .env)
  AWS_SECRET_ACCESS_KEY: (from .env)
  
Log Configuration: CloudWatch
  Log Group: /ecs/worker-task-def
  Stream Prefix: ecs
  Region: us-east-1
```

---


#### **Frontend (Fargate + Spot Hybrid)**

```
┌─────────────────────────────────────────┐
│   Frontend Service (Capacity Providers) │
├─────────────────────────────────────────┤
│ FARGATE (Weight: 1, Base: 1)            │
│  └─ Always 1 task running (stable)      │
│                                         │
│ FARGATE_SPOT (Weight: 2, Base: 0)       │
│  └─ Scales 0-3 additional tasks (burst) │
│                                         │
│ Total: 1-4 tasks                        │
│ Cost Savings: ~70% on burst capacity    │
│ Auto Scaling: Triggers at CPU > 70%     │
└─────────────────────────────────────────┘
```

#### **Worker (EC2 Spot ASG)**

```
┌─────────────────────────────────────────┐
│   Worker Service (EC2 Spot)             │
├─────────────────────────────────────────┤
│ EC2 Spot Auto Scaling Group             │
│  ├─ Min: 1 task                         │
│  ├─ Desired: 1 task                     │
│  ├─ Max: 6 tasks                        │
│  └─ Scale Metric: CPU > 50%             │
│                                         │
│ Instance Type: t3.micro / t3.small      │
│ Cost vs On-Demand: 90% cheaper          │
│ Interruption Tolerance: Good            │
│  (ECS auto-replaces interrupted tasks)  │
└─────────────────────────────────────────┘
```

### **IAM Roles & Policies**

#### **ecsTaskExecutionRole**

Allows ECS agent to:
- Pull Docker images from ECR
- Push container logs to CloudWatch
- Retrieve secrets from Secrets Manager (if used)

**Policy:** `AmazonECSTaskExecutionRolePolicy` (AWS managed)

#### **ecsWorkerTaskRole**

Allows worker containers to:
- Read/write to S3 bucket
- Receive/delete messages from SQS queue

**Policies:**
- `AmazonS3FullAccess`
- `AmazonSQSFullAccess`

#### **ecsInstanceRole** (for EC2 instances)

Allows EC2 instances to:
- Register with ECS cluster
- Pull images from ECR

**Policy:** `AmazonEC2ContainerServiceforEC2Role` (AWS managed)

---

## 🐛 Troubleshooting & Solutions

### **Issue 1: ECS Agent Missing on Amazon Linux 2023**

**Problem:**
- Container instance never registered with ECS cluster
- Logs showed: "ECS agent not found"

**Root Cause:**
- Amazon Linux 2023 doesn't automatically include ECS agent image

**Solution:**
```bash
# SSH into EC2 instance
docker pull public.ecr.aws/ecs/amazon-ecs-agent:latest
docker tag public.ecr.aws/ecs/amazon-ecs-agent:latest amazon/amazon-ecs-agent:latest
sudo systemctl restart ecs
```

**Result:** Container instance became ACTIVE ✅

---

### **Issue 2: Target Group Health Check Failing**

**Problem:**
- ALB showed targets as "Unhealthy"
- Requests to `/health` endpoint timing out

**Root Cause:**
- Frontend security group allowed TCP 8000, but from wrong source
- ALB SG wasn't in the inbound rules

**Solution:**
```bash
# Modified frontend SG inbound rule:
# Allow TCP 8000 from: ALB Security Group (instead of 0.0.0.0/0)
```

**Result:** Health checks passed, targets became Healthy ✅

---

### **Issue 3: Container Instance Not Registering**

**Problem:**
- EC2 instance launched but showed 0 registered container instances
- Worker tasks couldn't be scheduled

**Root Cause:**
- ECS Agent wasn't running on the instance
- User data script failed to start ECS agent

**Solution:**
- Fixed user data script to properly install & start ECS agent
- Verified agent logs: `/var/log/ecs/ecs-agent.log`

**Result:** Instance registered as active container instance ✅

---

### **Issue 4: Frontend JavaScript Calling Localhost**

**Problem:**
- JavaScript was calling `http://127.0.0.1:8000/generate-upload-url`
- Failed with CORS errors when accessing via ALB DNS

**Root Cause:**
- HTML hardcoded localhost instead of relative paths
- ALB DNS ≠ localhost

**Solution:**
```javascript
// Changed from:
fetch("http://127.0.0.1:8000/generate-upload-url")

// To:
fetch("/generate-upload-url")
```

**Result:** Frontend correctly routes through ALB ✅

---

### **Issue 5: Image Updates Required Full Redeployment**

**Problem:**
- Wanted to update code and test it
- Running `docker build` locally didn't auto-update ECS service

**Root Cause:**
- ECS caches task definition; must create new revision

**Solution:**
```bash
# Standard deployment pipeline:
1. docker build -f Dockerfile.api -t fastapi-api:latest .
2. docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/fastapi-api:latest
3. Register new task definition revision (points to latest image)
4. Update ECS service to use new task definition
5. ECS performs rolling deployment (new tasks replace old ones)
```

**Learning:** Automated CI/CD pipeline makes this seamless ✅

---

## 🎓 Key Learnings

### **ECS Concepts Mastered**

📌 **Heterogeneous Capacity Providers**
- Mixed on-demand (FARGATE) + spot (FARGATE_SPOT) for cost optimization
- Weight-based task distribution (can prioritize stability vs cost)
- Perfect for unpredictable workloads

📌 **Network Modes**
- `awsvpc` (Fargate): Each task gets own ENI + private IP, better isolation
- `bridge` (EC2): Tasks share instance IP, simpler networking but less isolation

📌 **Task Definitions vs Services**
- Task Definition = Template (CPU, memory, image, env vars, port mappings)
- Service = Running instance (desired count, scaling, load balancing)

📌 **ALB Target Groups**
- **Target Type Matters:** IP-based for Fargate (awsvpc), Instance-based for EC2
- **Health Checks:** Must point to container port, not ALB port
- **Auto-registration:** Fargate tasks auto-register IPs; EC2 tasks need manual/auto tagging

📌 **ECS Agent Responsibilities**
- Pulls Docker images from ECR
- Starts/stops containers
- Registers tasks with service
- Sends logs to CloudWatch
- Heartbeats to cluster



---

## 🎯 Interview Talking Points

✅ Explain heterogeneous capacity provider strategy and cost savings  
✅ Discuss awsvpc vs bridge network modes and when to use each  
✅ Describe how ALB target groups work with Fargate  
✅ Walk through asynchronous processing with SQS  
✅ Discuss ECS agent role and container registration  
✅ Explain auto-scaling decision: CPU for frontend, SQS queue depth for worker  
✅ Troubleshooting: ECS agent missing, health check failures, security groups  
✅ Cost optimization: Spot instances, right-sizing, auto-scaling  

---

## 📄 Files in This Project

```
ECS-project/
├── app.py                    # FastAPI frontend app
├── worker.py                 # Python image processor
├── Dockerfile.api            # Frontend container
├── Dockerfile.worker         # Worker container
├── requirements.txt          # Python dependencies
├── static/
│   └── index.html           # HTML UI
├── docker-compose.yml        # Local dev setup
├── .env                      # AWS credentials & config
├── frontend-task-def.json    # Frontend task definition
├── worker-task-def.json      # Worker task definition
└── README.md                 # This file
```

---

## 🔗 AWS Resources

- **Clusters:** `frontend-cluster`, `image-processor-cluster`
- **Services:** `frontend-service`, `worker-service`
- **Task Definitions:** `frontend-task-def`, `worker-task-def`
- **ECR Repositories:** `fastapi-api`, `image-processor`
- **S3 Bucket:** `my-app-image-uploads-siddhesh-07`
- **SQS Queue:** `image-processing-queue`
- **ALB:** Registered in ECS cluster VPC
- **IAM Roles:** `ecsTaskExecutionRole`, `ecsWorkerTaskRole`, `ecsInstanceRole`

---
