locals {
  key_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccess"
        Effect = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.account_id}:root" }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowEKSServiceAccount"
        Effect = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.account_id}:role/${var.name_prefix}-eks-pod-role" }
        Action = [
          "kms:Decrypt", "kms:DescribeKey", "kms:Encrypt",
          "kms:GenerateDataKey", "kms:GenerateDataKeyWithoutPlaintext"
        ]
        Resource = "*"
      }
    ]
  })
}

# Master key for tenant-level envelope encryption
resource "aws_kms_key" "master" {
  description             = "${var.name_prefix} — Master tenant encryption key"
  key_usage               = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = local.key_policy
  multi_region            = false  # data sovereignty: stay in ap-south-1
}

resource "aws_kms_alias" "master" {
  name          = "alias/${var.name_prefix}-master"
  target_key_id = aws_kms_key.master.key_id
}

# Dedicated key per data store
resource "aws_kms_key" "rds" {
  description             = "${var.name_prefix} — RDS encryption"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.name_prefix}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

resource "aws_kms_key" "s3" {
  description             = "${var.name_prefix} — S3 documents and reports"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${var.name_prefix}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

resource "aws_kms_key" "elasticache" {
  description             = "${var.name_prefix} — ElastiCache encryption"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "elasticache" {
  name          = "alias/${var.name_prefix}-elasticache"
  target_key_id = aws_kms_key.elasticache.key_id
}

resource "aws_kms_key" "eks" {
  description             = "${var.name_prefix} — EKS secrets encryption"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "secrets" {
  description             = "${var.name_prefix} — Secrets Manager"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

output "master_key_arn"      { value = aws_kms_key.master.arn }
output "rds_key_arn"         { value = aws_kms_key.rds.arn }
output "s3_key_arn"          { value = aws_kms_key.s3.arn }
output "elasticache_key_arn" { value = aws_kms_key.elasticache.arn }
output "eks_key_arn"         { value = aws_kms_key.eks.arn }
output "secrets_key_arn"     { value = aws_kms_key.secrets.arn }
