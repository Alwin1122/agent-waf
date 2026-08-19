output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer."
  value       = aws_lb.app.dns_name
}

output "application_url" {
  description = "Primary URL for the dashboard. Uses HTTPS when an ACM certificate is configured."
  value       = local.enable_https ? "https://${aws_lb.app.dns_name}" : "http://${aws_lb.app.dns_name}"
}

output "frontend_ecr_repository_url" {
  description = "ECR repository URL for frontend images."
  value       = aws_ecr_repository.frontend.repository_url
}

output "backend_ecr_repository_url" {
  description = "ECR repository URL for backend images."
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "frontend_ecs_service_name" {
  description = "Frontend ECS service name."
  value       = aws_ecs_service.frontend.name
}

output "backend_ecs_service_name" {
  description = "Backend ECS service name."
  value       = aws_ecs_service.backend.name
}

output "vpc_id" {
  description = "VPC identifier."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs used by the ALB."
  value       = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  description = "Private application subnet IDs used by ECS."
  value       = aws_subnet.private_app[*].id
}

output "private_data_subnet_ids" {
  description = "Private data subnet IDs used by RDS and Redis."
  value       = aws_subnet.private_data[*].id
}

output "rds_endpoint" {
  description = "RDS hostname (port 5432)."
  value       = aws_db_instance.main.address
}

output "redis_primary_endpoint" {
  description = "ElastiCache Redis primary endpoint address."
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "backend_service_discovery_dns" {
  description = "Private DNS name registered for the backend ECS service."
  value       = local.backend_service_discovery_dns
}

output "database_url_secret_arn" {
  description = "Secrets Manager ARN for DATABASE_URL."
  value       = aws_secretsmanager_secret.database_url.arn
}

output "redis_url_secret_arn" {
  description = "Secrets Manager ARN for REDIS_URL."
  value       = aws_secretsmanager_secret.redis_url.arn
}

output "openai_api_key_secret_arn" {
  description = "Secrets Manager ARN for OPENAI_API_KEY when secret injection is enabled."
  value       = var.openai_api_key_secret_enabled ? aws_secretsmanager_secret.openai_api_key[0].arn : null
}

output "nat_gateway_id" {
  description = "Single NAT Gateway identifier."
  value       = aws_nat_gateway.main.id
}

output "budget_name" {
  description = "AWS Budget name when budget alerts are enabled."
  value       = var.enable_budget && length(var.budget_notification_emails) > 0 ? aws_budgets_budget.monthly[0].name : null
}
