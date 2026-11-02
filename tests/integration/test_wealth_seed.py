from datetime import date
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/fineract"))

from seed_fineract import FIXED_DEPOSIT_PRODUCTS, Seeder, State
from scripts.development.init_banking import initialize_fixed_product_metadata
from models import ProductMetadata


class FixedProductClient:
    def __init__(self):
        self.products = []
        self.posts = []

    def get(self, path, **kwargs):
        assert path == "/fixeddepositproducts"
        return list(self.products)

    def post(self, path, add_common=True, **kwargs):
        assert path == "/fixeddepositproducts"
        payload = kwargs["json"]
        product_id = len(self.products) + 10
        self.products.append({"id": product_id, "name": payload["name"]})
        self.posts.append(payload)
        return {"resourceId": product_id}


def test_fixed_product_seed_is_idempotent_and_uses_demo_contract(tmp_path):
    client = FixedProductClient()
    state = State(tmp_path / "state.json")
    seeder = Seeder(client, state)
    seeder.as_of = date(2026, 11, 1)

    first = seeder.step_fixed_deposit_products()
    second = seeder.step_fixed_deposit_products()

    assert first == second == {
        "BANK_AGENT_DEMO_FIXED_3M": 10,
        "BANK_AGENT_DEMO_FIXED_6M": 11,
    }
    assert len(client.posts) == 2
    assert [payload["minDepositTerm"] for payload in client.posts] == [3, 6]
    assert [payload["maxDepositTerm"] for payload in client.posts] == [3, 6]
    assert [
        payload["charts"][0]["chartSlabs"][0]["fromPeriod"]
        for payload in client.posts
    ] == [1, 1]
    assert [
        payload["charts"][0]["chartSlabs"][0]["annualInterestRate"]
        for payload in client.posts
    ] == ["1.00", "1.20"]
    assert all(payload["currencyCode"] == "CNY" for payload in client.posts)
    assert all("Demo" in payload["description"] for payload in client.posts)


class MetadataClient:
    def fixed_products(self):
        return [
            {"id": index + 20, "name": spec["name"]}
            for index, spec in enumerate(FIXED_DEPOSIT_PRODUCTS)
        ]


def test_demo_fixed_products_receive_enabled_low_risk_metadata(bank):
    with bank["db"]() as db:
        mapped = initialize_fixed_product_metadata(db, MetadataClient(), "default")
        db.commit()
        assert mapped == {
            "BANK_AGENT_DEMO_FIXED_3M": 20,
            "BANK_AGENT_DEMO_FIXED_6M": 21,
        }
        rows = db.query(ProductMetadata).order_by(ProductMetadata.product_id).all()
        assert [(row.product_id, row.risk_level, row.enabled, row.allows_premature) for row in rows] == [
            (20, 1, True, True),
            (21, 1, True, True),
        ]
