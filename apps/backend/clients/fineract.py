"""Fineract protocol adapter. No business authorization or LLM dependency."""

from __future__ import annotations
import json
from decimal import Decimal
from typing import Any
import httpx
from core.config import Settings


class FineractError(RuntimeError):
    def __init__(self, status: int, message: str, body: Any = None):
        self.status, self.body = status, body
        super().__init__(message)


class FineractNotFoundError(FineractError):
    pass


class FineractUnavailableError(FineractError):
    pass


class FineractClient:
    def __init__(self, settings: Settings):
        self._client = httpx.Client(
            base_url=f"{settings.fineract_base_url}/api/v1/",
            auth=(settings.fineract_user, settings.fineract_password),
            headers={"Fineract-Platform-TenantId": settings.fineract_tenant},
            verify=settings.fineract_verify_ssl,
            timeout=settings.fineract_timeout_seconds,
        )

    def request(self, method, path, *, params=None, payload=None, key=None):
        headers = {"Idempotency-Key": key} if key else {}
        try:
            response = self._client.request(
                method, path.lstrip("/"), params=params, json=payload, headers=headers
            )
        except httpx.HTTPError as exc:
            raise FineractUnavailableError(503, "核心银行连接不可用") from exc
        try:
            data = json.loads(response.text, parse_float=Decimal)
        except (ValueError, TypeError) as exc:
            raise FineractError(502, "核心银行返回非 JSON 响应") from exc
        if response.status_code == 404:
            raise FineractNotFoundError(404, "核心银行资源不存在", data)
        if not response.is_success:
            raise FineractError(response.status_code, "核心银行拒绝请求", data)
        return data

    def _get(self, path, **params):
        return self.request("GET", path, params=params)

    def get_client(self, client_id):
        return self._get(f"clients/{client_id}")

    def list_client_accounts(self, client_id):
        return self._get(f"clients/{client_id}/accounts")

    def get_savings_account(self, account_id):
        return self._get(f"savingsaccounts/{account_id}")

    def savings_products(self):
        return self._get("savingsproducts")

    def create_savings_account(self, payload, key):
        return self.request("POST", "savingsaccounts", payload=payload, key=key)

    def savings_account_command(self, account_id, command, payload, key):
        return self.request(
            "POST",
            f"savingsaccounts/{account_id}",
            params={"command": command},
            payload=payload,
            key=key,
        )

    def search_transactions(self, account_id, page=0, page_size=100, **filters):
        data = self._get(
            f"savingsaccounts/{account_id}/transactions/search",
            offset=page,
            limit=page_size,
            orderBy="transactionDate,id",
            sortOrder="DESC",
            dateFormat="yyyy-MM-dd",
            locale="en",
            **{k: v for k, v in filters.items() if v is not None},
        )
        # Actual pinned image uses total/content. Do not guess a legacy pageItems response.
        if not isinstance(data, dict) or not isinstance(data.get("content"), list):
            raise FineractError(502, "流水分页契约不兼容")
        total = data.get("total", data.get("totalElements"))
        if total is None:
            raise FineractError(502, "流水分页缺少总数")
        return {
            "items": data["content"],
            "total": int(total),
            "page": page,
            "page_size": page_size,
        }

    def get_transaction(self, account_id, transaction_id):
        return self._get(f"savingsaccounts/{account_id}/transactions/{transaction_id}")

    def hold_amount(self, account_id, amount, transaction_date, reason, key):
        return self.request(
            "POST",
            f"savingsaccounts/{account_id}/transactions",
            params={"command": "holdAmount"},
            payload={
                "transactionAmount": str(amount),
                "transactionDate": str(transaction_date),
                "reasonForBlock": reason,
                "lienAllowed": False,
                "dateFormat": "yyyy-MM-dd",
                "locale": "en",
            },
            key=key,
        )

    def release_amount(self, account_id, hold_transaction_id, transaction_date, key):
        return self.request(
            "POST",
            f"savingsaccounts/{account_id}/transactions/{hold_transaction_id}",
            params={"command": "releaseAmount"},
            payload={
                "transactionDate": str(transaction_date),
                "dateFormat": "yyyy-MM-dd",
                "locale": "en",
            },
            key=key,
        )

    def create_transfer(self, payload, key):
        return self.request("POST", "accounttransfers", payload=payload, key=key)

    def get_transfer(self, transfer_id):
        return self._get(f"accounttransfers/{transfer_id}")

    def fixed_products(self):
        return self._get("fixeddepositproducts")

    def fixed_product(self, product_id):
        return self._get(f"fixeddepositproducts/{product_id}")

    def fixed_template(self, client_id, product_id):
        return self._get(
            "fixeddepositaccounts/template", clientId=client_id, productId=product_id
        )

    def fixed_account(self, account_id):
        return self._get(f"fixeddepositaccounts/{account_id}")

    def create_fixed(self, payload, key):
        return self.request("POST", "fixeddepositaccounts", payload=payload, key=key)

    def fixed_command(self, account_id, command, payload, key):
        return self.request(
            "POST",
            f"fixeddepositaccounts/{account_id}",
            params={"command": command},
            payload=payload,
            key=key,
        )

    def fixed_closure_template(self, account_id):
        return self._get(f"fixeddepositaccounts/{account_id}/template", command="close")

    def business_date(self):
        return self._get("businessdate")

    def close(self):
        self._client.close()
