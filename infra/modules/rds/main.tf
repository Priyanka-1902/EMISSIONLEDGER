resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.database_subnet_ids
}

resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds-sg"
  vpc_id      = var.vpc_id
  description = "RDS PostgreSQL — allow EKS nodes only"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.eks_security_group_id]
    description     = "PostgreSQL from EKS nodes"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_instance" "primary" {
  identifier              = "${var.name_prefix}-postgres"
  engine                  = "postgres"
  engine_version          = var.postgres_version
  instance_class          = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  max_allocated_storage   = var.db_allocated_storage * 5  # auto-scaling to 5x
  storage_type            = "gp3"
  storage_encrypted       = true
  kms_key_id              = var.kms_key_arn

  db_name  = "emissionledger"
  username = "emissionledger"
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Multi-AZ for production HA
  multi_az               = true
  backup_retention_period = 35   # 35-day backup retention (SOC 2 requirement)
  backup_window          = "02:00-03:00"
  maintenance_window     = "Mon:03:00-Mon:04:00"

  # Performance and monitoring
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]

  # Security
  deletion_protection      = true
  skip_final_snapshot      = false
  final_snapshot_identifier = "${var.name_prefix}-final-snapshot"
  copy_tags_to_snapshot    = true
  apply_immediately        = false

  parameter_group_name = aws_db_parameter_group.this.name

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [password]
  }
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name_prefix}-pg15"
  family = "postgres15"

  parameter {
    name  = "shared_preload_libraries"
    value = "timescaledb,pg_stat_statements,auto_explain"
    apply_method = "pending-reboot"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking > 1s
  }
  parameter {
    name  = "log_connections"
    value = "1"
  }
  parameter {
    name  = "log_disconnections"
    value = "1"
  }
  parameter {
    name  = "row_security"
    value = "on"
  }
  parameter {
    name  = "ssl"
    value = "1"
  }
}

resource "aws_iam_role" "rds_monitoring" {
  name = "${var.name_prefix}-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

output "db_endpoint"  { value = aws_db_instance.primary.endpoint }
output "db_password"  { value = random_password.db_password.result; sensitive = true }
output "db_name"      { value = aws_db_instance.primary.db_name }
