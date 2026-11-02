"""Reproducible randomized demo transaction data and its category vocabulary."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

GENERATOR_VERSION = "demo-history-v2"
ANALYSIS_ACCOUNT_EXTERNAL_ID = "AGENT-ALICE-ANALYSIS-SAV"
MERCHANT_PREFIX = "[Merchant] "

# Category names and merchant names are shared with the middle-tier fixture.
CATEGORY_MERCHANTS: dict[str, tuple[str, ...]] = {
    "餐饮": ("江南小馆", "麦香面包", "一茶一坐"),
    "交通": ("城市公交", "速行出行", "便利加油站"),
    "购物": ("晴空百货", "日用优选", "数码生活馆"),
    "居住": ("安居物业", "城市水电", "家居修缮"),
    "娱乐": ("星光影院", "周末运动馆", "云端游戏"),
    "医疗": ("仁和药房", "康宁诊所", "明亮眼镜"),
    "教育": ("知行书店", "云课堂", "成长文具"),
    "生活日用": ("清新超市", "四季生鲜", "邻里便利店"),
}

AMOUNT_RANGES_CENTS: dict[str, tuple[int, int]] = {
    "餐饮": (1200, 28000),
    "交通": (300, 12000),
    "购物": (800, 120000),
    "居住": (5000, 180000),
    "娱乐": (1000, 60000),
    "医疗": (1000, 90000),
    "教育": (1500, 100000),
    "生活日用": (500, 45000),
}

MONTHLY_SUBSCRIPTION_MERCHANTS = ("腾讯视频会员", "网易云音乐", "iCloud 云存储")


@dataclass(frozen=True)
class PlannedHistory:
    rows: tuple[tuple[date, str, Decimal, int, str], ...]
    skipped_withdrawals: int


def merchant_category_map() -> dict[str, str]:
    result = {
        merchant: category
        for category, names in CATEGORY_MERCHANTS.items()
        for merchant in names
    }
    result.update({merchant: "娱乐" for merchant in MONTHLY_SUBSCRIPTION_MERCHANTS})
    return result


def _amount(rng: random.Random, category: str) -> Decimal:
    low, high = AMOUNT_RANGES_CENTS[category]
    cents = rng.randint(low, high)
    # Occasionally choose a higher value from the same category range.
    if rng.random() < 0.025:
        cents = rng.randint(max(low, high // 2), high)
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def _apply_balance_guard(rows) -> PlannedHistory:
    """Protect the core balance floor and reserve affordable known monthly charges."""
    history = sorted(rows, key=lambda item: item[0])
    balance = Decimal("0")
    kept = []
    skipped = 0
    subscription_merchants = set(MONTHLY_SUBSCRIPTION_MERCHANTS)
    future_subscription_reserve = sum(
        (amount for _, kind, amount, _, note in history
         if kind == "withdrawal"
         and note.startswith(MERCHANT_PREFIX)
         and note.removeprefix(MERCHANT_PREFIX) in subscription_merchants),
        Decimal("0"),
    )
    for entry in history:
        _, kind, amount, _, note = entry
        if kind == "deposit":
            balance += amount
            kept.append(entry)
            continue
        is_subscription = (
            note.startswith(MERCHANT_PREFIX)
            and note.removeprefix(MERCHANT_PREFIX) in subscription_merchants
        )
        reserve_after = future_subscription_reserve - amount if is_subscription else future_subscription_reserve
        if balance - amount >= Decimal("500.00") + reserve_after:
            balance -= amount
            kept.append(entry)
        else:
            skipped += 1
        if is_subscription:
            future_subscription_reserve -= amount
    return PlannedHistory(tuple(kept), skipped)


def build_random_history(
    *,
    spec,
    start: date,
    days: int,
    seed: int,
    opening_balance: Decimal,
    include_salary: bool = False,
    apply_balance_guard: bool = True,
) -> PlannedHistory:
    """Generate randomized daily spending, monthly subscriptions and recurring income."""
    rng = random.Random(f"{GENERATOR_VERSION}:{seed}:{spec.key}:{start}:{days}:{include_salary}")
    history: list[tuple[date, str, Decimal, int, str]] = [
        (start, "deposit", Decimal(opening_balance).quantize(Decimal("0.01")), 1, "期初余额")
    ]
    end = start + timedelta(days=max(0, days - 1))

    if include_salary:
        cursor = date(start.year, start.month, 10)
        if cursor < start:
            cursor = (cursor.replace(day=1) + timedelta(days=32)).replace(day=10)
        while cursor <= end:
            cents = int(Decimal(str(spec.monthly_salary)) * 100)
            variance = rng.randint(-max(100, cents // 30), max(100, cents // 30))
            history.append((cursor, "deposit", Decimal(cents + variance) / 100, 1, "工资"))
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=10)

    # Recurring housing bills use their own merchant and category.
    cursor = date(start.year, start.month, 5)
    if cursor < start:
        cursor = (cursor.replace(day=1) + timedelta(days=32)).replace(day=5)
    while cursor <= end:
        amount = Decimal(rng.randint(320000, 420000)) / 100
        history.append((cursor, "withdrawal", amount, 3, MERCHANT_PREFIX + "安居物业"))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=5)

    # Monthly subscription history is stable enough for deterministic scanning,
    # while amounts and charge dates vary reproducibly by seed.
    offset = {"ALICE": 0, "BOB": 3, "CHARLIE": 6, "MOM": 9}.get(spec.key, 0)
    for index, merchant in enumerate(MONTHLY_SUBSCRIPTION_MERCHANTS):
        base_cents = (2500, 1500, 2100)[index]
        month = date(start.year, start.month, 1)
        while month <= end:
            charge_day = min(27, 8 + index * 6 + offset % 5 + rng.randint(-1, 1))
            charge_date = month.replace(day=charge_day)
            if start <= charge_date <= end:
                cents = base_cents + rng.randint(-80, 80)
                history.append((charge_date, "withdrawal", Decimal(cents) / 100, 3, MERCHANT_PREFIX + merchant))
            month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)

    categories = tuple(CATEGORY_MERCHANTS)
    previous_amounts: dict[str, Decimal] = {}
    day = start + timedelta(days=1)
    while day <= end:
        # Random phases create natural shifts in both frequency and category mix.
        phase = ((day - start).days // 35) % len(categories)
        category_weights = [1.0] * len(categories)
        category_weights[phase] = 2.5
        transaction_count = rng.choices((0, 1, 2, 3), weights=(0.12, 0.64, 0.21, 0.03), k=1)[0]
        for _ in range(transaction_count):
            category = rng.choices(categories, weights=category_weights, k=1)[0]
            merchant = rng.choice(CATEGORY_MERCHANTS[category])
            if merchant in previous_amounts and rng.random() < 0.10:
                amount = previous_amounts[merchant]
            else:
                amount = _amount(rng, category)
                previous_amounts.setdefault(merchant, amount)
            history.append((day, "withdrawal", amount, 3, MERCHANT_PREFIX + merchant))
        day += timedelta(days=1)

    if not apply_balance_guard:
        return PlannedHistory(tuple(sorted(history, key=lambda item: item[0])), 0)
    return _apply_balance_guard(history)


def split_history_for_analysis_account(
    primary: PlannedHistory,
    *,
    start: date,
    seed: int,
    analysis_opening_balance: Decimal = Decimal("5000.00"),
    analysis_share: float = 0.30,
) -> tuple[PlannedHistory, PlannedHistory]:
    """Randomly route some Alice withdrawals to her separate analysis account."""
    rng = random.Random(f"{GENERATOR_VERSION}:{seed}:payment-account:{start}")
    primary_rows, analysis_rows = [], [
        (start, "deposit", Decimal(analysis_opening_balance).quantize(Decimal("0.01")), 1, "期初余额")
    ]
    for row in primary.rows:
        if row[1] == "deposit" and row[4] == "期初余额":
            primary_rows.append(row)
        elif row[1] == "withdrawal" and rng.random() < analysis_share:
            analysis_rows.append(row)
        else:
            primary_rows.append(row)
    main = _apply_balance_guard(primary_rows)
    analysis = _apply_balance_guard(analysis_rows)
    return (
        PlannedHistory(main.rows, main.skipped_withdrawals + primary.skipped_withdrawals),
        analysis,
    )
