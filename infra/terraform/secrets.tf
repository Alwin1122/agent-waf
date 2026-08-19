resource "random_password" "db_master" {
  length  = 32
  special = true

  # RDS master password constraints.
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_password" "redis_auth" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${local.name_prefix}/database-url"
  recovery_window_in_days = 0

  tags = {
    Name = "${local.name_prefix}-database-url"
  }
}

resource "aws_secretsmanager_secret" "redis_url" {
  name                    = "${local.name_prefix}/redis-url"
  recovery_window_in_days = 0

  tags = {
    Name = "${local.name_prefix}-redis-url"
  }
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  count = var.openai_api_key_secret_enabled ? 1 : 0

  name                    = "${local.name_prefix}/openai-api-key"
  recovery_window_in_days = 0

  tags = {
    Name = "${local.name_prefix}-openai-api-key"
  }
}

# WARNING: Terraform state stores these secret values. Do not commit tfstate.
# Prefer a remote encrypted backend after bootstrapping S3/DynamoDB separately.

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql+psycopg://%s:%s@%s:%s/%s",
    var.db_username,
    urlencode(random_password.db_master.result),
    aws_db_instance.main.address,
    aws_db_instance.main.port,
    var.db_name,
  )

  depends_on = [aws_db_instance.main]
}

resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id = aws_secretsmanager_secret.redis_url.id
  secret_string = format(
    "redis://:%s@%s:6379/0",
    urlencode(random_password.redis_auth.result),
    aws_elasticache_replication_group.main.primary_endpoint_address,
  )

  depends_on = [aws_elasticache_replication_group.main]
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  count = var.openai_api_key_secret_enabled ? 1 : 0

  secret_id     = aws_secretsmanager_secret.openai_api_key[0].id
  secret_string = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
