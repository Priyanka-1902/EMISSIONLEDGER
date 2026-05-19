import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class AuditLogDBModel(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    event_type = Column(String(100), nullable=False)
    actor_id = Column(UUID(as_uuid=True))
    actor_email = Column(String(255))
    resource_type = Column(String(100))
    resource_id = Column(String(255))
    action = Column(String(50), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    payload_hash = Column(String(64))
    previous_hash = Column(String(64))
    chain_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
