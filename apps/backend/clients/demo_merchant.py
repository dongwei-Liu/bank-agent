"""Deterministic local adapter for the explicitly labelled Demo merchant."""

from core.errors import require


class DemoMerchantAdapter:
    def cancel_subscription(self, merchant, subscription):
        require(
            merchant.active and merchant.adapter_type == "demo_subscription",
            "DEMO_MERCHANT_UNAVAILABLE",
            "Demo 商户取消服务不可用",
            503,
        )
        return {
            "adapter": "demo_subscription",
            "merchant_reference": merchant.external_key,
            "subscription_id": subscription.id,
            "cancelled": True,
        }
