# ------------------------------------------------------------------------------
# General
# ------------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project name used in resource naming."
  type        = string
  default     = "agent-waf"
}

variable "environment" {
  description = "Deployment environment label (for example dev, staging, production)."
  type        = string
  default     = "dev"
}

# ------------------------------------------------------------------------------
# Networking
# ------------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to use. Leave empty to auto-select the first two available AZs."
  type        = list(string)
  default     = []
}

variable "allowed_ingress_cidrs" {
  description = "CIDR blocks permitted to reach the public ALB on ports 80 and 443. Do not use 0.0.0.0/0 unless intentionally public. Must be set before apply."
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the ALB HTTPS listener. Leave empty to deploy HTTP only until a certificate is available."
  type        = string
  default     = ""
}

# ------------------------------------------------------------------------------
# Container images
# ------------------------------------------------------------------------------

variable "frontend_image_tag" {
  description = "Tag of the frontend image pushed to ECR."
  type        = string
  default     = "latest"
}

variable "backend_image_tag" {
  description = "Tag of the backend image pushed to ECR."
  type        = string
  default     = "latest"
}

# ------------------------------------------------------------------------------
# ECS sizing and scaling
# ------------------------------------------------------------------------------

variable "frontend_cpu" {
  description = "Frontend Fargate task CPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Frontend Fargate task memory in MiB."
  type        = number
  default     = 512
}

variable "backend_cpu" {
  description = "Backend Fargate task CPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 256
}

variable "backend_memory" {
  description = "Backend Fargate task memory in MiB."
  type        = number
  default     = 512
}

variable "frontend_desired_count" {
  description = "Desired number of frontend ECS tasks."
  type        = number
  default     = 1
}

variable "backend_desired_count" {
  description = "Desired number of backend ECS tasks."
  type        = number
  default     = 1
}

variable "ecs_enable_container_insights" {
  description = "Enable ECS Container Insights (adds CloudWatch cost)."
  type        = bool
  default     = false
}

variable "ecs_assign_public_ip" {
  description = "Assign public IPs to ECS tasks. Keep false so tasks stay private."
  type        = bool
  default     = false
}

# ------------------------------------------------------------------------------
# RDS
# ------------------------------------------------------------------------------

variable "db_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "agent_waf"
}

variable "db_username" {
  description = "PostgreSQL master username."
  type        = string
  default     = "agent_waf"
}

variable "db_engine_version" {
  description = "PostgreSQL engine version for RDS."
  type        = string
  default     = "16.14"
}

variable "db_instance_class" {
  description = "RDS instance class. db.t4g.micro is the smallest Graviton option."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  description = "Initial allocated storage for RDS in GiB."
  type        = number
  default     = 20
}

variable "db_max_allocated_storage_gb" {
  description = "Maximum storage for RDS autoscaling. Set equal to allocated storage to disable growth."
  type        = number
  default     = 20
}

variable "db_multi_az" {
  description = "Enable RDS Multi-AZ. Disabled by default for cost savings."
  type        = bool
  default     = false
}

variable "db_backup_retention_days" {
  description = "Number of days to retain automated RDS backups."
  type        = number
  default     = 1
}

variable "db_deletion_protection" {
  description = "Prevent accidental RDS deletion."
  type        = bool
  default     = false
}

variable "db_skip_final_snapshot" {
  description = "Skip a final snapshot when destroying the RDS instance."
  type        = bool
  default     = true
}

variable "db_apply_immediately" {
  description = "Apply RDS modifications immediately instead of during the maintenance window."
  type        = bool
  default     = true
}

# ------------------------------------------------------------------------------
# Redis (ElastiCache)
# ------------------------------------------------------------------------------

variable "redis_engine_version" {
  description = "Redis engine version for ElastiCache."
  type        = string
  default     = "7.1"
}

variable "redis_node_type" {
  description = "ElastiCache node type. cache.t4g.micro is the smallest Graviton option."
  type        = string
  default     = "cache.t4g.micro"
}

variable "redis_replica_count" {
  description = "Number of read replicas. 0 keeps a single node with no failover."
  type        = number
  default     = 0
}

variable "redis_failover_enabled" {
  description = "Enable automatic failover. Requires at least one replica."
  type        = bool
  default     = false
}

variable "redis_multi_az_enabled" {
  description = "Enable Multi-AZ for Redis. Requires replicas and adds cost."
  type        = bool
  default     = false
}

# NOTE: TLS is intentionally not enabled. The application uses redis:// URLs without
# SSL parameters (see backend/app/redis_client.py). Enabling transit encryption would
# require application changes to use rediss:// and ssl_cert_reqs.

# ------------------------------------------------------------------------------
# CloudWatch
# ------------------------------------------------------------------------------

variable "cloudwatch_log_retention_days" {
  description = "Retention period for ECS log groups in days."
  type        = number
  default     = 7
}

# ------------------------------------------------------------------------------
# Application configuration (non-secret)
# ------------------------------------------------------------------------------

variable "app_name" {
  description = "Human-readable service name exposed in OpenAPI."
  type        = string
  default     = "Agent WAF"
}

variable "app_env" {
  description = "Application environment label passed to the backend."
  type        = string
  default     = "production"
}

variable "log_level" {
  description = "Backend log level."
  type        = string
  default     = "INFO"
}

variable "api_prefix" {
  description = "API route prefix for the backend."
  type        = string
  default     = "/api/v1"
}

variable "backend_port" {
  description = "Backend container port."
  type        = number
  default     = 8000
}

variable "frontend_port" {
  description = "Frontend container port."
  type        = number
  default     = 3000
}

variable "waf_enforcement_mode" {
  description = "WAF enforcement mode: ENFORCE or SHADOW."
  type        = string
  default     = "ENFORCE"

  validation {
    condition     = contains(["ENFORCE", "SHADOW"], var.waf_enforcement_mode)
    error_message = "waf_enforcement_mode must be ENFORCE or SHADOW."
  }
}

variable "redis_key_prefix" {
  description = "Redis key namespace prefix."
  type        = string
  default     = "agent-waf"
}

variable "redis_socket_timeout_seconds" {
  description = "Redis socket timeout in seconds."
  type        = number
  default     = 5
}

variable "redis_state_ttl_seconds" {
  description = "TTL for Redis rate-limit and sequence state."
  type        = number
  default     = 86400
}

variable "idempotency_ttl_seconds" {
  description = "TTL for Redis idempotency keys."
  type        = number
  default     = 3600
}

variable "idempotency_wait_timeout_seconds" {
  description = "Maximum wait for an in-flight idempotent request."
  type        = number
  default     = 30
}

variable "database_pool_size" {
  description = "SQLAlchemy connection pool size."
  type        = number
  default     = 5
}

variable "database_connect_timeout_seconds" {
  description = "PostgreSQL connection timeout in seconds."
  type        = number
  default     = 5
}

variable "database_create_tables" {
  description = "Create database schema at backend startup."
  type        = bool
  default     = true
}

variable "openai_model" {
  description = "OpenAI model used by the sample agent endpoint."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "openai_timeout_seconds" {
  description = "OpenAI request timeout in seconds."
  type        = number
  default     = 30
}

variable "openai_base_url" {
  description = "Optional OpenAI-compatible API base URL (e.g. Gemini). Leave empty for api.openai.com."
  type        = string
  default     = ""
}

variable "openai_api_key_secret_enabled" {
  description = "Inject OPENAI_API_KEY from Secrets Manager. Update the secret value manually after apply."
  type        = bool
  default     = false
}

# ------------------------------------------------------------------------------
# AWS Budget
# ------------------------------------------------------------------------------

variable "budget_limit_usd" {
  description = "Monthly AWS budget limit in USD."
  type        = string
  default     = "100"
}

variable "budget_notification_emails" {
  description = "Email addresses that receive AWS Budget alerts. Must be verified in the AWS account."
  type        = list(string)
  default     = []
}

variable "budget_alert_thresholds" {
  description = "Budget alert thresholds as percentages of the monthly limit."
  type        = list(number)
  default     = [50, 80, 100]
}

variable "enable_budget" {
  description = "Create an AWS Budget and cost alerts. Requires AWS Budgets to be available in the account."
  type        = bool
  default     = true
}

# ------------------------------------------------------------------------------
# ECR lifecycle
# ------------------------------------------------------------------------------

variable "ecr_max_image_count" {
  description = "Maximum number of tagged images retained per ECR repository."
  type        = number
  default     = 10
}
