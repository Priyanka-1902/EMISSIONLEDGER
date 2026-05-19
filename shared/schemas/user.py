from __future__ import annotations
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class UserRole(str, Enum):
    ORG_ADMIN = "org_admin"
    FINANCE = "finance"
    PLANT_MANAGER = "plant_manager"
    SUSTAINABILITY_OFFICER = "sustainability_officer"
    EXTERNAL_AUDITOR = "external_auditor"
    EU_VERIFIER = "eu_verifier"
    READ_ONLY_INVESTOR = "read_only_investor"


ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ORG_ADMIN: {
        "tenant:read", "tenant:write", "tenant:manage_users",
        "data:read", "data:write", "data:delete",
        "report:read", "report:generate", "report:approve", "report:submit",
        "audit:read", "settings:write",
    },
    UserRole.FINANCE: {
        "data:read", "data:write",
        "report:read", "report:generate", "report:approve",
        "audit:read",
    },
    UserRole.PLANT_MANAGER: {
        "data:read", "data:write",
        "report:read",
    },
    UserRole.SUSTAINABILITY_OFFICER: {
        "data:read", "data:write",
        "report:read", "report:generate", "report:approve",
        "audit:read", "settings:read",
    },
    UserRole.EXTERNAL_AUDITOR: {
        "data:read",
        "report:read",
        "audit:read",
    },
    UserRole.EU_VERIFIER: {
        "data:read",
        "report:read", "report:verify",
        "audit:read",
    },
    UserRole.READ_ONLY_INVESTOR: {
        "report:read",
    },
}


class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    cognito_sub: str  # Cognito user sub
    email: EmailStr
    full_name: str
    role: UserRole
    facility_ids: list[UUID] = Field(default_factory=list)  # ABAC: scope to facilities
    mfa_enabled: bool = False
    is_active: bool = True
    last_login: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def has_permission(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())

    class Config:
        from_attributes = True
