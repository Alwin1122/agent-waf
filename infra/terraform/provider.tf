provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Use configured AZs or the first two available in the region.
  availability_zones = length(var.availability_zones) > 0 ? var.availability_zones : slice(
    data.aws_availability_zones.available.names,
    0,
    min(2, length(data.aws_availability_zones.available.names))
  )

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Subnet layout for a /16 VPC: two public, two private app, two private data.
  public_subnet_cidrs       = [for index in range(2) : cidrsubnet(var.vpc_cidr, 8, index)]
  private_app_subnet_cidrs  = [for index in range(2) : cidrsubnet(var.vpc_cidr, 8, index + 10)]
  private_data_subnet_cidrs = [for index in range(2) : cidrsubnet(var.vpc_cidr, 8, index + 20)]

  # Backend is reached only through Cloud Map; the frontend proxy calls it server-side.
  service_discovery_namespace   = "${var.project_name}.local"
  backend_service_discovery_dns = "backend.${local.service_discovery_namespace}"

  enable_https = var.acm_certificate_arn != ""

  # ElastiCache cluster count = 1 primary + optional read replicas.
  redis_num_cache_clusters = 1 + var.redis_replica_count

  redis_automatic_failover = var.redis_failover_enabled && local.redis_num_cache_clusters > 1
  redis_multi_az           = var.redis_multi_az_enabled && local.redis_num_cache_clusters > 1
}
