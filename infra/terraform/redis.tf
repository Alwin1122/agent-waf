resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis"
  subnet_ids = aws_subnet.private_data[*].id

  tags = {
    Name = "${local.name_prefix}-redis-subnet-group"
  }
}

resource "aws_elasticache_parameter_group" "main" {
  family = "redis7"
  name   = "${local.name_prefix}-redis7"

  tags = {
    Name = "${local.name_prefix}-redis7"
  }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${local.name_prefix}-redis"
  description          = "Agent WAF Redis state store"

  engine               = "redis"
  engine_version       = var.redis_engine_version
  node_type            = var.redis_node_type
  parameter_group_name = aws_elasticache_parameter_group.main.name
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  num_cache_clusters = local.redis_num_cache_clusters

  automatic_failover_enabled = local.redis_automatic_failover
  multi_az_enabled           = local.redis_multi_az

  at_rest_encryption_enabled = true
  transit_encryption_enabled = false

  auth_token                 = random_password.redis_auth.result
  auth_token_update_strategy = "SET"

  apply_immediately = true

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}
