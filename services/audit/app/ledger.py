"""
Hash-chained audit ledger.

Every audit event is linked to the previous event by its hash, creating
a tamper-evident chain. Any modification to a past entry breaks all
subsequent chain hashes, which can be detected by chain_verify().

Chain integrity: chain_hash[n] = sha256(payload_hash[n] + chain_hash[n-1] + str(sequence[n]))
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class AuditEvent:
    def __init__(
        self,
        tenant_id: UUID,
        event_type: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        payload: dict | None = None,
    ):
        self.tenant_id = tenant_id
        self.event_type = event_type
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.actor_id = actor_id
        self.actor_email = actor_email
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.payload = payload or {}
        self.created_at = datetime.now(timezone.utc)


def _compute_payload_hash(event: AuditEvent) -> str:
    """Deterministic hash of event content."""
    payload = {
        "tenant_id": str(event.tenant_id),
        "event_type": event.event_type,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "actor_email": event.actor_email,
        "ip_address": event.ip_address,
        "created_at": event.created_at.isoformat(),
        "payload": event.payload,
    }
    serialised = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()


def _compute_chain_hash(payload_hash: str, previous_hash: str | None, sequence: int) -> str:
    """Chain each entry to the previous one."""
    data = f"{payload_hash}:{previous_hash or 'GENESIS'}:{sequence}"
    return hashlib.sha256(data.encode()).hexdigest()


class AuditLedger:
    """
    In-process audit ledger. In production, each append goes to PostgreSQL
    as an atomic INSERT with sequence = last_sequence + 1 (serialisable transaction).
    """

    def __init__(self, db_session_factory) -> None:
        self._db = db_session_factory

    async def append(self, event: AuditEvent) -> dict:
        """
        Append one event to the chain.
        Returns the audit log row dict (id, sequence_number, chain_hash, ...).
        """
        from sqlalchemy import select, func, text
        from sqlalchemy.ext.asyncio import AsyncSession

        payload_hash = _compute_payload_hash(event)

        async with self._db() as session:
            async with session.begin():
                # Lock the last entry for this tenant to get sequence and previous hash
                stmt = (
                    select(
                        text("sequence_number"),
                        text("chain_hash"),
                    )
                    .select_from(text("audit_logs"))
                    .where(text(f"tenant_id = '{event.tenant_id}'"))
                    .order_by(text("sequence_number DESC"))
                    .limit(1)
                    .with_for_update()
                )
                row = (await session.execute(stmt)).fetchone()

                if row:
                    sequence = row.sequence_number + 1
                    previous_hash = row.chain_hash
                else:
                    sequence = 1
                    previous_hash = None

                chain_hash = _compute_chain_hash(payload_hash, previous_hash, sequence)

                from .models import AuditLogDBModel
                log_entry = AuditLogDBModel(
                    tenant_id=event.tenant_id,
                    sequence_number=sequence,
                    event_type=event.event_type,
                    actor_id=event.actor_id,
                    actor_email=event.actor_email,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    action=event.action,
                    ip_address=event.ip_address,
                    user_agent=event.user_agent,
                    payload_hash=payload_hash,
                    previous_hash=previous_hash,
                    chain_hash=chain_hash,
                )
                session.add(log_entry)
                await session.flush()
                return {
                    "id": log_entry.id,
                    "sequence_number": sequence,
                    "chain_hash": chain_hash,
                    "created_at": event.created_at.isoformat(),
                }

    async def verify_chain(self, tenant_id: UUID) -> dict:
        """
        Walk the entire chain for a tenant and verify integrity.
        Returns {"valid": True} or {"valid": False, "broken_at_sequence": N, "reason": "..."}.
        """
        from sqlalchemy import text

        async with self._db() as session:
            stmt = text("""
                SELECT sequence_number, payload_hash, previous_hash, chain_hash
                FROM audit_logs
                WHERE tenant_id = :tenant_id
                ORDER BY sequence_number ASC
            """)
            rows = (await session.execute(stmt, {"tenant_id": str(tenant_id)})).fetchall()

        if not rows:
            return {"valid": True, "message": "No audit records found", "record_count": 0}

        prev_hash = None
        for row in rows:
            expected_chain = _compute_chain_hash(row.payload_hash, prev_hash, row.sequence_number)
            if expected_chain != row.chain_hash:
                return {
                    "valid": False,
                    "broken_at_sequence": row.sequence_number,
                    "reason": f"Chain hash mismatch at sequence {row.sequence_number}",
                }
            prev_hash = row.chain_hash

        return {
            "valid": True,
            "record_count": len(rows),
            "last_hash": rows[-1].chain_hash,
        }
