resource "aws_cognito_user_pool" "main" {
  name = "${var.name_prefix}-users"

  # Password policy
  password_policy {
    minimum_length                   = 12
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }

  # MFA — required for org_admin and sustainability_officer; optional for others
  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  # Email verification
  auto_verified_attributes = ["email"]
  username_attributes      = ["email"]
  username_configuration {
    case_sensitive = false
  }

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Custom attributes for multi-tenancy
  schema {
    name                = "tenant_id"
    attribute_data_type = "String"
    mutable             = true
    string_attribute_constraints { min_length = 1; max_length = 36 }
  }
  schema {
    name                = "tenant_slug"
    attribute_data_type = "String"
    mutable             = true
    string_attribute_constraints { min_length = 1; max_length = 63 }
  }
  schema {
    name                = "tenant_name"
    attribute_data_type = "String"
    mutable             = true
    string_attribute_constraints { min_length = 1; max_length = 255 }
  }
  schema {
    name                = "tenant_tier"
    attribute_data_type = "String"
    mutable             = true
    string_attribute_constraints { min_length = 1; max_length = 20 }
  }
  schema {
    name                = "role"
    attribute_data_type = "String"
    mutable             = true
    string_attribute_constraints { min_length = 1; max_length = 50 }
  }

  # Email configuration via SES
  email_configuration {
    email_sending_account = "DEVELOPER"
    from_email_address    = "noreply@${var.ses_email_domain}"
    source_arn            = "arn:aws:ses:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:identity/${var.ses_email_domain}"
  }

  # Advanced security (anomaly detection, compromised credential protection)
  user_pool_add_ons {
    advanced_security_mode = "ENFORCED"
  }

  # Token validity
  device_configuration {
    challenge_required_on_new_device      = true
    device_only_remembered_on_user_prompt = true
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.name_prefix}-web"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = false  # Public SPA client
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_CUSTOM_AUTH",
  ]

  # Token validity — short-lived access tokens
  access_token_validity  = 1     # 1 hour
  id_token_validity      = 1     # 1 hour
  refresh_token_validity = 30    # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls
  supported_identity_providers = ["COGNITO"]

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  allowed_oauth_flows_user_pool_client = true
}

# Server-side client for backend services
resource "aws_cognito_user_pool_client" "backend" {
  name         = "${var.name_prefix}-backend"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret               = true  # Backend keeps secret
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true
  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
  ]
  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

output "user_pool_id"  { value = aws_cognito_user_pool.main.id }
output "client_id"     { value = aws_cognito_user_pool_client.web.id }
output "backend_client_id"     { value = aws_cognito_user_pool_client.backend.id }
output "backend_client_secret" { value = aws_cognito_user_pool_client.backend.client_secret; sensitive = true }
