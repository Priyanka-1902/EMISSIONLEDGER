variable "aws_region" {
  default = "ap-south-1"
  description = "AWS region — all pilot SME data in Mumbai for data sovereignty"
}

variable "environment" {
  default = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be dev, staging, or prod"
  }
}

variable "vpc_cidr"         { default = "10.0.0.0/16" }
variable "private_subnets"  { default = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"] }
variable "public_subnets"   { default = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"] }
variable "database_subnets" { default = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"] }

variable "k8s_version"              { default = "1.29" }
variable "eks_node_instance_types"  { default = ["m6i.xlarge", "m6i.2xlarge"] }
variable "eks_node_min_size"        { default = 3 }
variable "eks_node_max_size"        { default = 20 }

variable "db_instance_class"    { default = "db.r7g.xlarge" }
variable "db_allocated_storage" { default = 200 }
variable "postgres_version"     { default = "15.6" }

variable "redis_node_type" { default = "cache.r7g.large" }

variable "ses_email_domain" { default = "emissionledger.in" }
variable "cognito_callback_urls" {
  default = ["https://app.emissionledger.in/"]
}
variable "cognito_logout_urls" {
  default = ["https://app.emissionledger.in/login"]
}
variable "waf_allowed_countries" {
  default = ["IN", "DE", "NL", "FR", "GB", "SG", "US"]
  description = "Countries allowed by WAF geo-restriction — India + EU + Singapore + US"
}
