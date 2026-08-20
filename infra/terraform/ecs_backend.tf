locals {
  backend_openai_env = var.openai_base_url != "" ? [
    { name = "OPENAI_BASE_URL", value = var.openai_base_url },
  ] : []

  backend_environment = concat([
    { name = "APP_NAME", value = var.app_name },
    { name = "APP_ENV", value = var.app_env },
    { name = "LOG_LEVEL", value = var.log_level },
    { name = "API_PREFIX", value = var.api_prefix },
    { name = "HOST", value = "0.0.0.0" },
    { name = "PORT", value = tostring(var.backend_port) },
    { name = "CORS_ALLOWED_ORIGINS", value = local.enable_https ? "https://${aws_lb.app.dns_name}" : "http://${aws_lb.app.dns_name}" },
    { name = "CORS_ALLOW_CREDENTIALS", value = "false" },
    { name = "PERSISTENCE_ENABLED", value = "true" },
    { name = "REDIS_KEY_PREFIX", value = var.redis_key_prefix },
    { name = "REDIS_SOCKET_TIMEOUT_SECONDS", value = tostring(var.redis_socket_timeout_seconds) },
    { name = "REDIS_STATE_TTL_SECONDS", value = tostring(var.redis_state_ttl_seconds) },
    { name = "IDEMPOTENCY_TTL_SECONDS", value = tostring(var.idempotency_ttl_seconds) },
    { name = "IDEMPOTENCY_WAIT_TIMEOUT_SECONDS", value = tostring(var.idempotency_wait_timeout_seconds) },
    { name = "DATABASE_ECHO", value = "false" },
    { name = "DATABASE_POOL_SIZE", value = tostring(var.database_pool_size) },
    { name = "DATABASE_CONNECT_TIMEOUT_SECONDS", value = tostring(var.database_connect_timeout_seconds) },
    { name = "DATABASE_CREATE_TABLES", value = tostring(var.database_create_tables) },
    { name = "OPENAI_MODEL", value = var.openai_model },
    { name = "OPENAI_TIMEOUT_SECONDS", value = tostring(var.openai_timeout_seconds) },
    { name = "WAF_ENFORCEMENT_MODE", value = var.waf_enforcement_mode },
  ], local.backend_openai_env)

  backend_secrets = concat(
    [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
      { name = "REDIS_URL", valueFrom = aws_secretsmanager_secret.redis_url.arn },
      { name = "API_AUTH_KEY", valueFrom = aws_secretsmanager_secret.api_auth_key.arn },
    ],
    var.openai_api_key_secret_enabled ? [
      { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_api_key[0].arn },
    ] : [],
  )
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.backend_task.arn

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
      essential = true

      portMappings = [
        {
          containerPort = var.backend_port
          hostPort      = var.backend_port
          protocol      = "tcp"
        }
      ]

      environment = local.backend_environment
      secrets     = local.backend_secrets

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.backend.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "backend"
        }
      }

      healthCheck = {
        command = [
          "CMD",
          "python",
          "-c",
          "import os, urllib.request; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '${var.backend_port}') + '/api/v1/ready')",
        ]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-backend-task"
  }
}

resource "aws_ecs_service" "backend" {
  name            = "${local.name_prefix}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private_app[*].id
    security_groups  = [aws_security_group.backend_ecs.id]
    assign_public_ip = var.ecs_assign_public_ip
  }

  service_registries {
    registry_arn = aws_service_discovery_service.backend.arn
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  depends_on = [
    aws_secretsmanager_secret_version.database_url,
    aws_secretsmanager_secret_version.redis_url,
  ]

  tags = {
    Name = "${local.name_prefix}-backend-service"
  }
}
