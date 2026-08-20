resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb"
  description = "Public Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-alb"
  }
}

resource "aws_security_group" "frontend_ecs" {
  name        = "${local.name_prefix}-frontend-ecs"
  description = "Private frontend ECS tasks"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-frontend-ecs"
  }
}

resource "aws_security_group" "backend_ecs" {
  name        = "${local.name_prefix}-backend-ecs"
  description = "Private backend ECS tasks"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-backend-ecs"
  }
}

resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds"
  description = "Private PostgreSQL RDS"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-rds"
  }
}

resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis"
  description = "Private ElastiCache Redis"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}

# ALB ingress from approved CIDRs only.
resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from approved CIDRs"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = var.allowed_ingress_cidrs[count.index]

  count = length(var.allowed_ingress_cidrs)
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP redirect from approved CIDRs"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  cidr_ipv4         = var.allowed_ingress_cidrs[count.index]

  count = length(var.allowed_ingress_cidrs)
}

resource "aws_vpc_security_group_egress_rule" "alb_to_frontend" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward traffic to frontend ECS"
  from_port                    = var.frontend_port
  to_port                      = var.frontend_port
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.frontend_ecs.id
}

# Frontend accepts traffic only from the ALB.
resource "aws_vpc_security_group_ingress_rule" "frontend_from_alb" {
  security_group_id            = aws_security_group.frontend_ecs.id
  description                  = "HTTP from ALB"
  from_port                    = var.frontend_port
  to_port                      = var.frontend_port
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.alb.id
}

resource "aws_vpc_security_group_egress_rule" "frontend_to_backend" {
  security_group_id            = aws_security_group.frontend_ecs.id
  description                  = "Server-side proxy to backend ECS"
  from_port                    = var.backend_port
  to_port                      = var.backend_port
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.backend_ecs.id
}

resource "aws_vpc_security_group_egress_rule" "frontend_https_egress" {
  security_group_id = aws_security_group.frontend_ecs.id
  description       = "ECR image pull and AWS APIs over HTTPS via NAT"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "frontend_dns_udp" {
  security_group_id = aws_security_group.frontend_ecs.id
  description       = "VPC DNS resolver UDP"
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
  cidr_ipv4         = var.vpc_cidr
}

resource "aws_vpc_security_group_egress_rule" "frontend_dns_tcp" {
  security_group_id = aws_security_group.frontend_ecs.id
  description       = "VPC DNS resolver TCP"
  from_port         = 53
  to_port           = 53
  ip_protocol       = "tcp"
  cidr_ipv4         = var.vpc_cidr
}

# Backend accepts traffic only from the frontend ECS service.
resource "aws_vpc_security_group_ingress_rule" "backend_from_frontend" {
  security_group_id            = aws_security_group.backend_ecs.id
  description                  = "API traffic from frontend ECS"
  from_port                    = var.backend_port
  to_port                      = var.backend_port
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.frontend_ecs.id
}

resource "aws_vpc_security_group_egress_rule" "backend_to_rds" {
  security_group_id            = aws_security_group.backend_ecs.id
  description                  = "PostgreSQL"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.rds.id
}

resource "aws_vpc_security_group_egress_rule" "backend_to_redis" {
  security_group_id            = aws_security_group.backend_ecs.id
  description                  = "Redis"
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.redis.id
}

resource "aws_vpc_security_group_egress_rule" "backend_https_egress" {
  security_group_id = aws_security_group.backend_ecs.id
  description       = "OpenAI and AWS APIs over HTTPS via NAT"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "backend_dns_udp" {
  security_group_id = aws_security_group.backend_ecs.id
  description       = "VPC DNS resolver UDP"
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
  cidr_ipv4         = var.vpc_cidr
}

resource "aws_vpc_security_group_egress_rule" "backend_dns_tcp" {
  security_group_id = aws_security_group.backend_ecs.id
  description       = "VPC DNS resolver TCP"
  from_port         = 53
  to_port           = 53
  ip_protocol       = "tcp"
  cidr_ipv4         = var.vpc_cidr
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_backend" {
  security_group_id            = aws_security_group.rds.id
  description                  = "PostgreSQL from backend ECS"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.backend_ecs.id
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_backend" {
  security_group_id            = aws_security_group.redis.id
  description                  = "Redis from backend ECS"
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.backend_ecs.id
}
