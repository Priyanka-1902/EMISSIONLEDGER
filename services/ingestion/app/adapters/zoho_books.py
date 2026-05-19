"""
Zoho Books Connector — OAuth 2.0 API Integration

Fetches invoices, bills, expenses, and journal entries from Zoho Books.
Syncs every 15 minutes via scheduled job.
Credentials stored in AWS Secrets Manager.

Zoho Books API: https://www.zoho.com/books/api/v3/
Auth: OAuth 2.0 with server-side token refresh.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator
import httpx
import boto3
import json
import structlog

log = structlog.get_logger(__name__)

ZOHO_API_BASE = "https://www.zohoapis.in/books/v3"
ZOHO_AUTH_URL = "https://accounts.zoho.in/oauth/v2/token"

# Zoho account IDs to sync — tenant configures these
ZOHO_ORGANIZATION_ID_SECRET = "emissionledger/{tenant_id}/zoho_organization_id"
ZOHO_REFRESH_TOKEN_SECRET = "emissionledger/{tenant_id}/zoho_refresh_token"
ZOHO_CLIENT_ID_SECRET = "emissionledger/{tenant_id}/zoho_client_id"
ZOHO_CLIENT_SECRET_SECRET = "emissionledger/{tenant_id}/zoho_client_secret"


@dataclass
class ZohoBill:
    bill_id: str
    bill_number: str
    vendor_name: str
    bill_date: date
    due_date: date | None
    total: Decimal
    currency_code: str
    line_items: list["ZohoBillLine"]
    status: str
    notes: str | None


@dataclass
class ZohoBillLine:
    item_id: str | None
    item_name: str
    description: str | None
    quantity: Decimal
    unit: str | None
    rate: Decimal
    amount: Decimal
    account_name: str | None  # mapped to chart of accounts
    account_id: str | None
    tax_name: str | None


class ZohoBooksAdapter:
    """
    Pulls expense bills from Zoho Books and classifies them as
    fuel/energy activities for GHG calculation.
    """

    def __init__(self, tenant_id: str, aws_region: str = "ap-south-1") -> None:
        self.tenant_id = tenant_id
        self._secrets_client = boto3.client("secretsmanager", region_name=aws_region)
        self._access_token: str | None = None
        self._organization_id: str | None = None
        self._http: httpx.AsyncClient | None = None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def _load_credentials(self) -> None:
        """Fetch Zoho credentials from Secrets Manager and refresh access token."""
        def _get_secret(key: str) -> str:
            resp = self._secrets_client.get_secret_value(
                SecretId=key.format(tenant_id=self.tenant_id)
            )
            return resp["SecretString"]

        organization_id = _get_secret(ZOHO_ORGANIZATION_ID_SECRET)
        refresh_token = _get_secret(ZOHO_REFRESH_TOKEN_SECRET)
        client_id = _get_secret(ZOHO_CLIENT_ID_SECRET)
        client_secret = _get_secret(ZOHO_CLIENT_SECRET_SECRET)

        self._organization_id = organization_id

        http = await self._get_http()
        resp = await http.post(ZOHO_AUTH_URL, data={
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        log.info("zoho.token_refreshed", tenant_id=self.tenant_id)

    async def _get(self, path: str, params: dict | None = None) -> dict:
        if not self._access_token:
            await self._load_credentials()
        http = await self._get_http()
        headers = {
            "Authorization": f"Zoho-oauthtoken {self._access_token}",
        }
        resp = await http.get(
            f"{ZOHO_API_BASE}{path}",
            params={"organization_id": self._organization_id, **(params or {})},
            headers=headers,
        )
        if resp.status_code == 401:
            # Token expired — refresh and retry once
            await self._load_credentials()
            headers["Authorization"] = f"Zoho-oauthtoken {self._access_token}"
            resp = await http.get(
                f"{ZOHO_API_BASE}{path}",
                params={"organization_id": self._organization_id, **(params or {})},
                headers=headers,
            )
        resp.raise_for_status()
        return resp.json()

    async def fetch_bills_paginated(
        self, from_date: date, to_date: date
    ) -> AsyncGenerator[ZohoBill, None]:
        """Yield all bills in date range, handling Zoho pagination (200 per page)."""
        page = 1
        while True:
            data = await self._get("/bills", params={
                "date_start": from_date.isoformat(),
                "date_end": to_date.isoformat(),
                "page": page,
                "per_page": 200,
                "filter_by": "Status.All",
            })
            bills_raw = data.get("bills", [])
            if not bills_raw:
                break

            for raw in bills_raw:
                bill = await self._fetch_bill_detail(raw["bill_id"])
                if bill:
                    yield bill

            if not data.get("page_context", {}).get("has_more_page", False):
                break
            page += 1

    async def _fetch_bill_detail(self, bill_id: str) -> ZohoBill | None:
        """Fetch bill with line items (list API returns summary only)."""
        try:
            data = await self._get(f"/bills/{bill_id}")
            raw = data.get("bill", {})
            return ZohoBill(
                bill_id=raw.get("bill_id", ""),
                bill_number=raw.get("bill_number", ""),
                vendor_name=raw.get("vendor_name", ""),
                bill_date=_parse_zoho_date(raw.get("date")),
                due_date=_parse_zoho_date(raw.get("due_date")),
                total=Decimal(str(raw.get("total", 0))),
                currency_code=raw.get("currency_code", "INR"),
                line_items=[
                    ZohoBillLine(
                        item_id=li.get("item_id"),
                        item_name=li.get("name", ""),
                        description=li.get("description"),
                        quantity=Decimal(str(li.get("quantity", 1))),
                        unit=li.get("unit"),
                        rate=Decimal(str(li.get("rate", 0))),
                        amount=Decimal(str(li.get("item_total", 0))),
                        account_name=li.get("account_name"),
                        account_id=li.get("account_id"),
                        tax_name=li.get("tax_name"),
                    )
                    for li in raw.get("line_items", [])
                ],
                status=raw.get("status", ""),
                notes=raw.get("notes"),
            )
        except Exception as e:
            log.warning("zoho.bill_detail_error", bill_id=bill_id, error=str(e))
            return None

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()


def _parse_zoho_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None
