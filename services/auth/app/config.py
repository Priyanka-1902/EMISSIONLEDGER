from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    environment: str = "development"
    log_level: str = "INFO"
    service_name: str = "auth"
    port: int = 8001

    # Database
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 40

    # Redis
    redis_url: str

    # AWS Cognito
    cognito_user_pool_id: str
    cognito_client_id: str
    cognito_client_secret: str = ""
    cognito_region: str = "ap-south-1"

    # JWT (Cognito public keys are fetched from JWKS endpoint)
    jwt_algorithm: str = "RS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # AWS KMS
    kms_master_key_arn: str = ""
    aws_region: str = "ap-south-1"

    # Security
    secret_key: str
    allowed_hosts: list[str] = ["localhost", "*.emissionledger.in"]
    cors_origins: list[str] = ["http://localhost:5173"]

    # Sentry
    sentry_dsn: str = ""

    # Audit service
    audit_service_url: str = "http://audit:8005"

    @property
    def cognito_jwks_url(self) -> str:
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com"
            f"/{self.cognito_user_pool_id}/.well-known/jwks.json"
        )

    @property
    def cognito_issuer(self) -> str:
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com"
            f"/{self.cognito_user_pool_id}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
