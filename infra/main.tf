terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
  }
  backend "s3" {
    bucket         = "emissionledger-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "emissionledger-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "EmissionLedger"
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = "platform"
    }
  }
}

# ── Data sources ─────────────────────────────────────────────────────────────
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  azs        = slice(data.aws_availability_zones.available.names, 0, 3)
  name_prefix = "emissionledger-${var.environment}"
}

# ── Modules ───────────────────────────────────────────────────────────────────

module "networking" {
  source = "./modules/networking"

  name_prefix        = local.name_prefix
  azs                = local.azs
  vpc_cidr           = var.vpc_cidr
  private_subnets    = var.private_subnets
  public_subnets     = var.public_subnets
  database_subnets   = var.database_subnets
}

module "kms" {
  source = "./modules/kms"

  name_prefix = local.name_prefix
  account_id  = local.account_id
  region      = local.region
}

module "eks" {
  source = "./modules/eks"

  name_prefix          = local.name_prefix
  vpc_id               = module.networking.vpc_id
  private_subnet_ids   = module.networking.private_subnet_ids
  k8s_version          = var.k8s_version
  node_instance_types  = var.eks_node_instance_types
  node_min_size        = var.eks_node_min_size
  node_max_size        = var.eks_node_max_size
  kms_key_arn          = module.kms.eks_key_arn
}

module "rds" {
  source = "./modules/rds"

  name_prefix          = local.name_prefix
  vpc_id               = module.networking.vpc_id
  database_subnet_ids  = module.networking.database_subnet_ids
  eks_security_group_id = module.eks.node_security_group_id
  kms_key_arn          = module.kms.rds_key_arn
  db_instance_class    = var.db_instance_class
  db_allocated_storage = var.db_allocated_storage
  postgres_version     = var.postgres_version
}

module "elasticache" {
  source = "./modules/elasticache"

  name_prefix           = local.name_prefix
  vpc_id                = module.networking.vpc_id
  database_subnet_ids   = module.networking.database_subnet_ids
  eks_security_group_id = module.eks.node_security_group_id
  kms_key_arn           = module.kms.elasticache_key_arn
  node_type             = var.redis_node_type
}

module "s3" {
  source = "./modules/s3"

  name_prefix = local.name_prefix
  kms_key_arn = module.kms.s3_key_arn
  account_id  = local.account_id
}

module "cognito" {
  source = "./modules/cognito"

  name_prefix       = local.name_prefix
  ses_email_domain  = var.ses_email_domain
  callback_urls     = var.cognito_callback_urls
  logout_urls       = var.cognito_logout_urls
}

module "waf" {
  source = "./modules/waf"

  name_prefix     = local.name_prefix
  alb_arn         = module.eks.alb_arn
  allowed_countries = var.waf_allowed_countries
}

module "secrets" {
  source = "./modules/secrets"

  name_prefix       = local.name_prefix
  kms_key_arn       = module.kms.secrets_key_arn
  db_password       = module.rds.db_password
  db_endpoint       = module.rds.db_endpoint
  redis_endpoint    = module.elasticache.primary_endpoint
  cognito_pool_id   = module.cognito.user_pool_id
  cognito_client_id = module.cognito.client_id
}
