"""Causal, read-only spending detectors and explicitly maintained personal models.

All evidence stays in the trusted service/private result channel. No LLM imports.
"""
import hashlib
import math
import os
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from statistics import median
from uuid import uuid4

from sqlalchemy import select

from core.config import PROJECT_ROOT
from core.errors import require
from core.security import SHANGHAI, aware, fingerprint, now
from models import AnomalyModel, Annotation, AnomalyReview, Category, ClassificationRule, Merchant, Subscription
from services.common import safe_json
from services.subscription_service import normalized_merchant, CADENCES, AMOUNT_TOLERANCE

FEATURE_VERSION = "spending-bundle-v2"
POLICY_VERSION = "spending-six-v1"
PROFILES = ("transaction", "user_day", "account_day")
PACKAGES = ("scikit-learn", "numpy", "scipy", "skops")
TRUSTED_MODEL_TYPES = ["sklearn.tree._tree.Tree"]
TYPES = ("SPENDING_SURGE_V1", "DAILY_CONCENTRATION_V1", "MERCHANT_DEVIATION_V1",
         "CATEGORY_MIX_SHIFT_V1", "SUBSCRIPTION_DEVIATION_V1", "ACCOUNT_HABIT_SHIFT_V1")
ZERO = Decimal(0)
SUBSCRIPTION_LOOKBACK = {"MONTHLY": 180, "YEARLY": 1200}


def dependency_versions():
    return {name: version(name) for name in PACKAGES}


def day_of(row):
    return date.fromisoformat(row["date"])


def expenses(rows):
    return sorted((r for r in rows if r["kind"] == "expense" and not r["reversed"]),
                  key=lambda r: (r["date"], r["account_id"], r["transaction_id"]))


def quantile(values, q):
    """Linear quantile without converting monetary comparisons to floats."""
    values = sorted(Decimal(str(v)) for v in values)
    if not values:
        return ZERO
    position = Decimal(str(q)) * (len(values) - 1)
    low = int(position)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)


def ratio(value, baseline):
    return math.log(float((Decimal(value) + 1) / (Decimal(baseline) + 1)))


def known_category(row):
    return bool(row.get("category") and row["category"] not in ("未分类", "其他", "unknown"))


def distribution(rows):
    groups = defaultdict(lambda: ZERO)
    for r in rows:
        groups[r.get("category") or "未分类"] += Decimal(r["amount"])
    total = sum(groups.values(), ZERO)
    return {k: float(v / total) for k, v in groups.items()} if total else {}


def divergence(left, right):
    if not left or not right:
        return 0.0
    result = 0.0
    for key in left.keys() | right.keys():
        p, q = left.get(key, 0), right.get(key, 0)
        m = (p + q) / 2
        if p:
            result += p * math.log2(p / m) / 2
        if q:
            result += q * math.log2(q / m) / 2
    return max(0.0, result)


class DailyIndex:
    """Request-local date groups and cached windows; identifiers are grouping keys only."""
    def __init__(self, rows):
        self.rows = expenses(rows)
        self.days = defaultdict(list)
        for r in self.rows:
            self.days[day_of(r)].append(r)
        self.first = min(self.days) if self.days else None
        self.cache = {}

    def between(self, start, end):
        return [r for d in sorted(self.days) if start <= d <= end for r in self.days[d]]

    def window(self, end, width=1):
        key = (end, width)
        if key not in self.cache:
            start = end - timedelta(days=width - 1)
            rows = self.between(start, end)
            self.cache[key] = {"start": start, "end": end, "rows": rows,
                "amount": sum((Decimal(r["amount"]) for r in rows), ZERO), "count": len(rows)}
        return self.cache[key]

    def baseline(self, start, width=1):
        # Disjoint from the target window, including for rolling seven-day evidence.
        first = max(start - timedelta(days=90), self.first or start) + timedelta(days=width - 1)
        return [self.window(first + timedelta(days=i), width)
                for i in range(max(0, (start - first).days))
                if self.first and first + timedelta(days=i - width + 1) >= self.first]

    def eligible(self, start, width=1):
        base = self.baseline(start, width)
        active = len({day_of(r) for r in self.between(start - timedelta(days=90), start - timedelta(days=1))})
        return len(base) >= 20 and active >= 10

    def js(self, end, width):
        w = self.window(end, width)
        prior = self.between(w["start"] - timedelta(days=90), w["start"] - timedelta(days=1))
        return divergence(distribution(w["rows"]), distribution(prior))


def feature_rows(rows):
    """Transaction features only use dates strictly earlier than the transaction date."""
    index = DailyIndex(rows)
    output = []
    for day in sorted(index.days):
        past = index.between(day - timedelta(days=90), day - timedelta(days=1))
        amounts = [Decimal(r["amount"]) for r in past]
        personal = median(amounts) if amounts else ZERO
        categories, merchants = defaultdict(list), defaultdict(list)
        for r in past:
            categories[r.get("category")].append(Decimal(r["amount"]))
            if r.get("merchant"):
                merchants[normalized_merchant(r["merchant"])].append(Decimal(r["amount"]))
        n7 = sum(day_of(r) >= day - timedelta(days=7) for r in past)
        n30 = sum(day_of(r) >= day - timedelta(days=30) for r in past)
        gap = (day - day_of(past[-1])).days if past else 90
        for row in index.days[day]:
            same = categories.get(row.get("category"), [])
            merchant = merchants.get(normalized_merchant(row.get("merchant") or ""), [])
            amount = Decimal(row["amount"])
            vector = [math.log1p(float(amount)), math.sin(2 * math.pi * day.weekday() / 7),
                math.cos(2 * math.pi * day.weekday() / 7), ratio(amount, personal),
                ratio(amount, median(same) if same else personal), math.log1p(n7), math.log1p(n30),
                len(same) / max(len(past), 1), float(min(gap, 90)), float(len(past) < 5),
                ratio(amount, median(merchant) if merchant else personal),
                len(merchant) / max(sum(map(len, merchants.values())), 1), float(not merchant)]
            require(all(math.isfinite(v) for v in vector), "FEATURE_INVALID", "无法生成有效行为特征", 422)
            output.append((day, row, vector))
    return output


def daily_vector(index, day, personal=None):
    """Only the target completed day is observed; every reference window precedes it."""
    vector = []
    for width in (1, 7):
        w = index.window(day, width)
        base = index.baseline(w["start"], width)
        nonzero = [b["amount"] for b in base if b["amount"] > 0]
        counts = [b["count"] for b in base if b["count"]]
        vector.extend([ratio(w["amount"], median(nonzero) if nonzero else ZERO),
                       ratio(w["count"], median(counts) if counts else ZERO), index.js(day, width)])
    past = index.between(day - timedelta(days=180), day - timedelta(days=1))
    vector.extend([float(min((day - day_of(past[-1])).days, 180)) if past else 180.,
                   float(not index.eligible(day))])
    if personal is not None:
        own = index.window(day, 7)["amount"]
        total = personal.window(day, 7)["amount"]
        old_own = sum((Decimal(r["amount"]) for r in index.between(day - timedelta(days=96), day - timedelta(days=7))), ZERO)
        old_all = sum((Decimal(r["amount"]) for r in personal.between(day - timedelta(days=96), day - timedelta(days=7))), ZERO)
        vector.append(float(own / total if total else 0) - float(old_own / old_all if old_all else 0))
    return vector


def daily_rows(index, start, end, personal=None, account_id=None):
    if index.first is None:
        return []
    first = max(start, index.first)
    return [(first + timedelta(days=i), {"account_id": account_id,
             "active": bool(index.window(first + timedelta(days=i))["count"])},
             daily_vector(index, first + timedelta(days=i), personal))
            for i in range(max(0, (end - first).days + 1))]


class AnomalyDetectionService:
    def __init__(self, billing):
        self.billing = billing
        self.db, self.settings = billing.db, billing.settings

    def configuration(self, user):
        return fingerprint({"categories": self.billing.list_resources(user, Category),
            "rules": self.billing.list_resources(user, ClassificationRule),
            "annotations": self.billing.list_resources(user, Annotation)})

    def directory(self):
        root = Path(self.settings.anomaly_model_directory)
        return (root if root.is_absolute() else PROJECT_ROOT / root).resolve()

    def train(self, user, as_of):
        import numpy as np
        import skops.io as sio
        from sklearn.ensemble import IsolationForest
        require(as_of <= now().astimezone(SHANGHAI).date(), "INVALID_DATE", "训练截止日不能在未来", 422)
        start = as_of - timedelta(days=180)
        ids, rows = self.billing.scoped_transactions(user, None, start - timedelta(days=180), as_of - timedelta(days=1))
        index = DailyIndex(rows)
        profiles = {"transaction": [r for r in feature_rows(rows) if start <= r[0] < as_of],
                    "user_day": daily_rows(index, start, as_of - timedelta(days=1)), "account_day": []}
        for account_id in ids:
            ai = DailyIndex([r for r in index.rows if r["account_id"] == account_id])
            profiles["account_day"].extend(daily_rows(ai, start, as_of - timedelta(days=1), index, account_id))
        metadata = {"feature_version": FEATURE_VERSION, "policy_version": POLICY_VERSION,
            "configuration": self.configuration(user), "account_ids": sorted(ids), "training_start": start.isoformat(),
            "training_end_exclusive": as_of.isoformat(), "dependencies": dependency_versions(), "profiles": {}}
        bundle = dict.fromkeys(PROFILES)
        for name, vectors in profiles.items():
            vectors.sort(key=lambda r: (r[0], r[1].get("account_id") or 0))
            dates = sorted({r[0] for r in vectors})
            active = len({r[0] for r in vectors if name == "transaction" or r[1]["active"]})
            info = {"status": "insufficient_history", "sample_count": len(vectors), "date_count": len(dates), "active_dates": active}
            metadata["profiles"][name] = info
            if len(vectors) < 100 or active < 30 or (name != "transaction" and len(dates) < 100):
                continue
            split = vectors[int(len(vectors) * .8)][0] if name == "transaction" else dates[int(len(dates) * .8)]
            fit, cal = [r for r in vectors if r[0] < split], [r for r in vectors if r[0] >= split]
            if len(fit) < 80 or len(cal) < 20 or (name != "transaction" and (len({r[0] for r in fit}) < 80 or len({r[0] for r in cal}) < 20)):
                continue
            forest = IsolationForest(n_estimators=100, max_samples="auto", contamination="auto", random_state=42, n_jobs=1)
            forest.fit(np.asarray([r[2] for r in fit]))
            scores = -forest.score_samples(np.asarray([r[2] for r in cal]))
            info.update(status="ready", threshold=float(np.quantile(scores, .95)), high_threshold=float(np.quantile(scores, .99)),
                        calibration_start=split.isoformat(), fit_count=len(fit), calibration_count=len(cal), feature_count=len(fit[0][2]))
            bundle[name] = forest
        row = AnomalyModel(id=str(uuid4()), user_id=user.id, as_of=as_of, status="insufficient_history", metadata_=metadata)
        if any(v is not None for v in bundle.values()):
            root = self.directory()
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            raw = sio.dumps(bundle)
            require(set(sio.get_untrusted_types(data=raw)) <= set(TRUSTED_MODEL_TYPES), "MODEL_TYPE", "模型包含未授权类型", 422)
            name = row.id + ".skops"
            fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(raw)
            metadata.update(filename=name, sha256=hashlib.sha256(raw).hexdigest())
            row.status = "ready"
        self.db.add(row)
        self.db.flush()
        return row

    def load(self, user, start):
        row = self.db.scalar(select(AnomalyModel).where(AnomalyModel.user_id == user.id, AnomalyModel.as_of <= start)
                             .order_by(AnomalyModel.as_of.desc(), AnomalyModel.created_at.desc()))
        if row is None:
            return None, None, "no_model"
        if row.status != "ready":
            return None, None, row.status
        if (start - row.as_of).days > self.settings.anomaly_model_max_age_days:
            return None, None, "stale_model"
        meta = row.metadata_
        try:
            import skops.io as sio
            from sklearn.ensemble import IsolationForest
            if meta["dependencies"] != dependency_versions() or meta["feature_version"] != FEATURE_VERSION or meta.get("policy_version") != POLICY_VERSION:
                return None, None, "incompatible_model"
            if set(meta["profiles"]) != set(PROFILES):
                return None, None, "invalid_model_artifact"
            if meta["configuration"] != self.configuration(user) or meta["account_ids"] != sorted(self.billing.account_scope(user)):
                return None, None, "configuration_changed"
            root = self.directory()
            candidate = root / meta["filename"]
            if candidate.is_symlink() or candidate.resolve().parent != root or candidate.name != row.id + ".skops":
                return None, None, "invalid_model_path"
            if candidate.stat().st_size > 20 * 1024 * 1024:
                return None, None, "invalid_model_artifact"
            raw = candidate.read_bytes()
            if hashlib.sha256(raw).hexdigest() != meta["sha256"] or not set(sio.get_untrusted_types(data=raw)) <= set(TRUSTED_MODEL_TYPES):
                return None, None, "invalid_model_artifact"
            bundle = sio.loads(raw, trusted=TRUSTED_MODEL_TYPES)
            if type(bundle) is not dict or set(bundle) != set(PROFILES) or not any(v is not None for v in bundle.values()):
                return None, None, "invalid_model_artifact"
            for name in PROFILES:
                info, forest = meta["profiles"][name], bundle[name]
                if forest is None:
                    if info["status"] != "insufficient_history":
                        return None, None, "invalid_model_artifact"
                elif (type(forest) is not IsolationForest or info["status"] != "ready"
                      or forest.n_features_in_ != info["feature_count"]
                      or info["feature_count"] != {"transaction": 13, "user_day": 8, "account_day": 9}[name]
                      or not all(math.isfinite(info[k]) for k in ("threshold", "high_threshold"))
                      or not 0 <= info["threshold"] <= info["high_threshold"]):
                    return None, None, "invalid_model_artifact"
            return bundle, row, "ready"
        except Exception:
            return None, None, "model_load_failed"

    def analyze(self, user, account_id, start, end, *, snapshot=None,
                selected_account_ids=None, dependency_account_ids=None):
        today = now().astimezone(SHANGHAI).date()
        require(start <= end, "INVALID_DATE", "开始日期不能晚于结束日期", 422)
        cutoff = min(end, today)
        ids = list(selected_account_ids) if selected_account_ids is not None else self.billing.account_scope(user, account_id)
        subscriptions = list(self.db.scalars(select(Subscription).where(Subscription.user_id == user.id, Subscription.verified_at.is_not(None))))
        lookback = max([180] + [SUBSCRIPTION_LOOKBACK.get(s.cadence, 180) for s in subscriptions])
        # All personal accounts are needed for personal features, shares and subscription disambiguation.
        if snapshot is None:
            dependencies, rows = self.billing.scoped_transactions(user, None, start - timedelta(days=lookback), cutoff)
        else:
            dependencies, rows = snapshot
        if dependency_account_ids is not None:
            dependencies = list(dependency_account_ids)
        selected = [r for r in rows if r["account_id"] in ids]
        legacy = self.billing.rule_anomalies(user, account_id, start, cutoff, snapshot=(ids, selected))
        items = legacy["items"] if isinstance(legacy, dict) else legacy
        personal = DailyIndex(rows)
        scope = personal if account_id is None else DailyIndex(selected)
        accounts = {i: DailyIndex([r for r in personal.rows if r["account_id"] == i]) for i in dependencies}
        bundle, model_row, status = self.load(user, start)
        metadata = {"status": status, "mode": "rules_only", "feature_version": FEATURE_VERSION,
                    "policy_version": POLICY_VERSION, "score_is_fraud_probability": False, "capabilities": {}}
        scores, profile_status = {}, {n: status for n in PROFILES}
        if bundle:
            profiles = {"transaction": [r for r in feature_rows(rows) if start <= r[0] <= cutoff and r[1]["account_id"] in ids],
                        "user_day": daily_rows(personal, start, min(cutoff, today - timedelta(days=1))), "account_day": []}
            for i in ids:
                profiles["account_day"].extend(daily_rows(accounts[i], start, min(cutoff, today - timedelta(days=1)), personal, i))
            for name, targets in profiles.items():
                forest = bundle[name]
                profile_status[name] = "insufficient_history" if forest is None else "no_targets"
                if forest is None or not targets:
                    continue
                try:
                    predicted = -forest.score_samples([r[2] for r in targets])
                    require(len(predicted) == len(targets) and all(math.isfinite(float(v)) for v in predicted), "MODEL_SCORE_INVALID", "模型评分不可用", 422)
                    for (day, r, _), score in zip(targets, predicted):
                        key = (name, day, r.get("account_id"), r.get("transaction_id"))
                        scores[key] = {"score": float(score), **{k: model_row.metadata_["profiles"][name][k] for k in ("threshold", "high_threshold")}}
                    profile_status[name] = "ready"
                except Exception:
                    profile_status[name] = "model_inference_failed"
            metadata["model_id"] = model_row.id
            if "ready" in profile_status.values():
                metadata.update(status="ready", mode="hybrid")
            elif "model_inference_failed" in profile_status.values():
                metadata["status"] = "model_inference_failed"
            else:
                metadata["status"] = "no_model_targets"
        metadata["profiles"] = profile_status
        run = DetectionRun(user.id, items, metadata, today, cutoff, scores, len(dependencies))
        for (_, day, account, transaction), score in scores.items():
            if transaction is not None and score["score"] > score["threshold"]:
                r = next(r for r in scope.days[day] if r["account_id"] == account and r["transaction_id"] == transaction)
                evidence = {"amount": r["amount"], "date": r["date"], **score,
                            "reason_codes": ["PERSONAL_BEHAVIOR_DEVIATION"], "severity": "high" if score["score"] > score["high_threshold"] else "medium"}
                run.add("IFOREST_V1", [r], day, day, ["model"], evidence)
        for offset in range(max(0, (cutoff - start).days + 1)):
            day = start + timedelta(days=offset)
            run.aggregates(scope, day, account_id)
            run.merchants(scope, day)
            for i in ids:
                if account_id is None and len(ids) > 1:
                    run.aggregates(accounts[i], day, i)
                run.account_habit(accounts[i], personal, day, i)
        self.subscription_findings(run, subscriptions, personal, ids, start, cutoff)
        reviews = {r.anomaly_key: r.status for r in self.db.scalars(select(AnomalyReview).where(AnomalyReview.user_id == user.id))}
        for item in items:
            item["status"] = reviews.get(item["anomaly_key"], "unreviewed")
        run.finish()
        return safe_json({"account_id": account_id, "account_ids": ids, "dependency_account_ids": dependencies,
            "complete": True, "from_date": start, "to_date": end, "data_cutoff": now(),
            "expense_count": sum(start <= day_of(r) <= cutoff for r in scope.rows), "items": items, "detection": metadata})

    def subscription_findings(self, run, subscriptions, index, ids, start, cutoff):
        kind = "SUBSCRIPTION_DEVIATION_V1"
        for sub in subscriptions:
            merchant = self.db.get(Merchant, sub.merchant_id)
            if not merchant or sub.cadence not in CADENCES:
                run.skip(kind, "subscription_data_incomplete")
                continue
            low, high = CADENCES[sub.cadence]
            horizon = SUBSCRIPTION_LOOKBACK[sub.cadence]
            matched = [r for r in index.rows if r.get("merchant") and normalized_merchant(r["merchant"]) == normalized_merchant(merchant.name)]
            # Parallel products at a single merchant cannot be unambiguously attributed.
            if sum(s.merchant_id == sub.merchant_id for s in subscriptions) > 1:
                run.skip(kind, "ambiguous_subscription")
                continue
            def active(day):
                return (aware(sub.verified_at).astimezone(SHANGHAI).date() <= day
                        and (not sub.cancelled_at or aware(sub.cancelled_at).astimezone(SHANGHAI).date() > day)
                        and (not sub.ignored_at or aware(sub.ignored_at).astimezone(SHANGHAI).date() > day)
                        and sub.status in ("VERIFIED", "CANCELLED", "IGNORED"))
            def baseline(day):
                prior = [r for r in matched if day - timedelta(days=horizon) <= day_of(r) < day]
                # The last three charges must form a unique stable series. Do not guess a run
                # among intervening one-off purchases; historical changes are not overwritten.
                last = prior[-3:]
                if len(last) < 3:
                    return None
                gaps = [(day_of(b) - day_of(a)).days for a, b in zip(last, last[1:])]
                middle = median([Decimal(r["amount"]) for r in last])
                if middle <= 0 or not all(low <= g <= high for g in gaps) or any(abs(Decimal(r["amount"]) - middle) > middle * AMOUNT_TOLERANCE for r in last):
                    return None
                return last, middle, int(median(gaps))
            for r in matched:
                day = day_of(r)
                if not start <= day <= cutoff or r["account_id"] not in ids or not active(day):
                    continue
                base = baseline(day)
                if base is None:
                    run.skip(kind, "insufficient_subscription_history")
                    continue
                same_day = [v for v in matched if day_of(v) == day]
                if len(same_day) > 1:
                    run.skip(kind, "ambiguous_subscription")
                    continue
                prior, middle, interval = base
                gap = (day - day_of(prior[-1])).days
                reasons = []
                if Decimal(r["amount"]) > middle * (1 + AMOUNT_TOLERANCE):
                    reasons.append("PRICE_INCREASE")
                if gap < low:
                    reasons.append("EARLY_OR_DENSE_CHARGE")
                if gap > high:
                    reasons.append("LATE_CHARGE")
                run.executed(kind, ["rule"])
                if reasons:
                    run.add(kind, [r], day, day, ["rule"], {"reason_codes": reasons, "merchant": merchant.name,
                        "amount": r["amount"], "baseline_amount": middle, "interval_days": gap,
                        "expected_date": day_of(prior[-1]) + timedelta(days=interval)}, provisional=day == run.today)
            if not active(cutoff):
                continue
            base = baseline(cutoff + timedelta(days=1))
            if base is None:
                run.skip(kind, "insufficient_subscription_history")
                continue
            prior, middle, interval = base
            last_day = day_of(prior[-1])
            if not any(r["account_id"] in ids for r in prior):
                run.skip(kind, "not_in_account_scope")
                continue
            if (cutoff - last_day).days <= high:
                run.executed(kind, ["rule"])
                continue
            # Unknown merchants could conceal a payment, including on another owned account.
            uncertain = any(not r.get("merchant") for r in index.between(last_day + timedelta(days=1), cutoff))
            if uncertain:
                run.skip(kind, "payment_cannot_be_excluded")
                continue
            run.executed(kind, ["rule"])
            expected = last_day + timedelta(days=interval)
            run.add(kind, [], expected, cutoff, ["rule"], {"reason_codes": ["EXPECTED_CHARGE_NOT_OBSERVED"],
                "merchant": merchant.name, "expected_date": expected, "cutoff_date": cutoff},
                provisional=cutoff == run.today, observation={"subscription": sub.id, "expected": expected, "accounts": sorted(ids)})
        if not subscriptions:
            run.skip(kind, "no_verified_subscription")


class DetectionRun:
    """Pure candidate assembly; tracks applicability independently from model availability."""
    def __init__(self, user_id, items, metadata, today, cutoff, scores, account_count):
        self.user_id, self.items, self.metadata = user_id, items, metadata
        self.today, self.cutoff, self.scores, self.account_count = today, cutoff, scores, account_count
        self.states = {k: {"executed": 0, "skipped": set(), "sources": set()} for k in TYPES}
        self.dedupe = {}

    def skip(self, kind, reason):
        self.states[kind]["skipped"].add(reason)

    def executed(self, kind, sources):
        self.states[kind]["executed"] += 1
        self.states[kind]["sources"].update(sources)

    def score(self, day, account=None, transaction=None):
        profile = "transaction" if transaction is not None else "user_day" if account is None else "account_day"
        return self.scores.get((profile, day, account, transaction))

    def sources(self, metric, historical, score, provisional=False):
        sources = []
        if metric > quantile(historical, .99 if provisional else .95):
            sources.append("rule")
        if not provisional and score and score["score"] > score["threshold"]:
            sources.append("model")
        high = metric > quantile(historical, .99) or ("model" in sources and score["score"] > score["high_threshold"])
        return sources, "high" if high else "medium"

    def add(self, kind, rows, start, end, sources, evidence, provisional=False, observation=None):
        refs = sorted(({"account_id": r["account_id"], "transaction_id": r["transaction_id"]} for r in rows),
                      key=lambda r: (r["account_id"], r["transaction_id"]))
        identity = tuple((r["account_id"], r["transaction_id"]) for r in refs)
        finding = {"type": kind, "sources": sources, "window": {"from_date": start, "to_date": end},
                   "provisional": provisional, "evidence": evidence}
        marker = (kind, (end - start).days + 1, identity) if observation is None else (kind, fingerprint(observation))
        prior = self.dedupe.get(marker)
        if prior:
            # Deterministic strongest, then latest window, with no duplicate evidence explosion.
            strength = (evidence.get("severity") == "high", float(evidence.get("score", evidence.get("metric", 0))), end)
            old = prior["evidence"]
            old_strength = (old.get("severity") == "high", float(old.get("score", old.get("metric", 0))), prior["window"]["to_date"])
            if strength > old_strength:
                prior.clear()
                prior.update(finding)
            return
        self.dedupe[marker] = finding
        existing = next((r for r in self.items if refs and tuple(sorted((t["account_id"], t["transaction_id"]) for t in r["transactions"])) == identity), None)
        if existing is None:
            key = fingerprint({"user": self.user_id, "rule": kind, "transactions": refs, "feature_version": "spending-date-v1"}) if kind == "IFOREST_V1" else fingerprint({"user": self.user_id, "rule": kind, "transactions": refs, "observation": observation})
            existing = {"rule": kind, "transactions": refs, "transaction_ids": [r["transaction_id"] for r in refs],
                        "evidence": evidence, "anomaly_key": key, "candidate_only": True, "status": "unreviewed"}
            if observation:
                existing["observation_kind"] = "expected_charge_not_observed"
            self.items.append(existing)
        existing.setdefault("anomaly_types", [existing["rule"]])
        if kind not in existing["anomaly_types"]:
            existing["anomaly_types"].append(kind)
        existing["detectors"] = list(existing["anomaly_types"])
        existing.setdefault("findings", []).append(finding)
        if kind == "IFOREST_V1":
            existing["ml_evidence"] = evidence

    def aggregates(self, index, day, account):
        provisional = day == self.today
        score = self.score(day, account)
        for width in (1, 7):
            w = index.window(day, width)
            base = index.baseline(w["start"], width)
            eligible = index.eligible(w["start"], width)
            kind = "SPENDING_SURGE_V1"
            if not eligible:
                self.skip(kind, "insufficient_history")
            else:
                self.executed(kind, ["rule"] + (["model"] if score and not provisional else []))
                values = [b["amount"] for b in base]
                nonzero = [v for v in values if v > 0]
                if nonzero and w["amount"] >= 2 * median(nonzero):
                    sources, severity = self.sources(w["amount"], values, score, provisional)
                    if sources:
                        self.add(kind, w["rows"], w["start"], day, sources,
                            {"amount": w["amount"], "baseline_median": median(nonzero), "metric": w["amount"], "severity": severity,
                             **(score or {})}, provisional)
            kind = "CATEGORY_MIX_SHIFT_V1"
            prior = index.between(w["start"] - timedelta(days=90), w["start"] - timedelta(days=1))
            known = sum(known_category(r) for r in w["rows"])
            prior_known = sum(known_category(r) for r in prior)
            if provisional:
                self.skip(kind, "incomplete_day")
            elif not eligible or len(w["rows"]) < 5 or prior_known < 20:
                self.skip(kind, "insufficient_history")
            elif known * 5 < len(w["rows"]) * 4 or prior_known * 5 < len(prior) * 4:
                self.skip(kind, "category_coverage_low")
            else:
                self.executed(kind, ["rule"] + (["model"] if score else []))
                js = index.js(day, width)
                historical = [index.js(b["end"], width) for b in base]
                if js >= .15:
                    sources, severity = self.sources(js, historical, score)
                    if sources:
                        self.add(kind, w["rows"], w["start"], day, sources, {"js_divergence": js, "metric": js,
                            "current_distribution": distribution(w["rows"]), "baseline_distribution": distribution(prior), "severity": severity, **(score or {})})
        kind = "DAILY_CONCENTRATION_V1"
        if not index.eligible(day):
            self.skip(kind, "insufficient_history")
            return
        self.executed(kind, ["rule"] + (["model"] if score and not provisional else []))
        values = [b["count"] for b in index.baseline(day)]
        positive = [v for v in values if v]
        current = index.window(day)
        if positive and current["count"] >= 5 and current["count"] >= median(positive) * 2:
            sources, severity = self.sources(current["count"], values, score, provisional)
            if sources:
                self.add(kind, current["rows"], day, day, sources, {"count": current["count"], "baseline_median": median(positive),
                         "metric": current["count"], "severity": severity, **(score or {})}, provisional)

    def merchants(self, index, day):
        kind = "MERCHANT_DEVIATION_V1"
        prior = index.between(day - timedelta(days=90), day - timedelta(days=1))
        known = [r for r in prior if r.get("merchant")]
        for r in index.days.get(day, []):
            if not r.get("merchant"):
                self.skip(kind, "merchant_missing")
                continue
            if not index.eligible(day):
                self.skip(kind, "insufficient_history")
                continue
            same = [Decimal(v["amount"]) for v in known if normalized_merchant(v["merchant"]) == normalized_merchant(r["merchant"])]
            familiar = len(same) >= 10
            rare = not same or len(same) / max(len(known), 1) < .05
            category = [Decimal(v["amount"]) for v in prior if known_category(v) and v.get("category") == r.get("category")]
            baseline = same if familiar else category
            if not familiar and (not rare or len(known) < 20 or len(category) < 5):
                self.skip(kind, "insufficient_merchant_history")
                continue
            if not baseline or median(baseline) <= 0:
                self.skip(kind, "insufficient_merchant_history")
                continue
            middle, amount = median(baseline), Decimal(r["amount"])
            score = self.score(day, r["account_id"], r["transaction_id"])
            self.executed(kind, ["rule"] + (["model"] if score else []))
            if not (amount > 3 * middle or (familiar and amount * 3 < middle)):
                continue
            metric = abs(amount / middle - 1)
            values = [abs(v / middle - 1) for v in baseline]
            sources, severity = self.sources(metric, values, score)
            if sources:
                self.add(kind, [r], day, day, sources, {"merchant": r["merchant"], "amount": amount,
                    "baseline_median": middle, "metric": metric, "severity": severity,
                    "reason_codes": ["FAMILIAR_MERCHANT_AMOUNT" if familiar else "RARE_MERCHANT_AMOUNT"], **(score or {})})

    def account_habit(self, index, personal, day, account):
        kind = "ACCOUNT_HABIT_SHIFT_V1"
        if day == self.today:
            self.skip(kind, "incomplete_day")
            return
        prior = index.between(day - timedelta(days=180), day - timedelta(days=1))
        if not index.first or (day - index.first).days < 30 or len({day_of(r) for r in prior}) < 10:
            self.skip(kind, "insufficient_account_history")
            return
        score = self.score(day, account)
        self.executed(kind, ["rule"] + (["model"] if score else []))
        current = index.window(day)
        gap = (day - day_of(prior[-1])).days
        if gap >= 30 and current["count"] >= 3:
            historical = sorted({day_of(r) for r in prior})
            gaps = [(b - a).days for a, b in zip(historical, historical[1:])]
            sources, severity = self.sources(gap, gaps, score)
            if "rule" not in sources:
                sources.insert(0, "rule")  # The explicit dormancy gate is itself a deterministic rule.
            if sources:
                self.add(kind, current["rows"], day, day, sources, {"reason_codes": ["DORMANT_ACCOUNT_RESUMED"],
                    "gap_days": gap, "count": current["count"], "metric": gap, "severity": severity, **(score or {})})
        if self.account_count < 2:
            self.skip(kind, "share_not_applicable")
            return
        w = index.window(day, 7)
        base = index.baseline(w["start"], 7)
        if not index.eligible(w["start"], 7):
            self.skip(kind, "insufficient_history")
            return
        old_own = sum((Decimal(r["amount"]) for r in index.between(w["start"] - timedelta(days=90), w["start"] - timedelta(days=1))), ZERO)
        old_all = sum((Decimal(r["amount"]) for r in personal.between(w["start"] - timedelta(days=90), w["start"] - timedelta(days=1))), ZERO)
        total = personal.window(day, 7)["amount"]
        values = [b["amount"] for b in base if b["amount"] > 0]
        if not old_all or not total or not values:
            self.skip(kind, "insufficient_history")
            return
        share, old_share = w["amount"] / total, old_own / old_all
        if share - old_share >= Decimal('.50') and w["amount"] >= 2 * median(values):
            historical_shares = [b["amount"] / personal.window(b["end"], 7)["amount"]
                                 for b in base if personal.window(b["end"], 7)["amount"] > 0]
            sources, severity = self.sources(share, historical_shares, score)
            if "rule" not in sources:
                sources.insert(0, "rule")
            if sources:
                self.add(kind, w["rows"], w["start"], day, sources, {"reason_codes": ["ACCOUNT_SHARE_SHIFT"],
                    "amount": w["amount"], "share": share, "baseline_share": old_share, "metric": w["amount"], "severity": severity, **(score or {})})

    def finish(self):
        for kind, state in self.states.items():
            self.metadata["capabilities"][kind] = {"status": "partial" if state["executed"] and state["skipped"] else "completed" if state["executed"] else "skipped",
                "sources": sorted(state["sources"]), "skip_reasons": sorted(state["skipped"] or ([] if state["executed"] else ["no_targets"])),
                "cutoff_date": self.cutoff}
        self.metadata["partial"] = any(c["status"] != "completed" for c in self.metadata["capabilities"].values())
        self.metadata["provisional"] = any(f["provisional"] for i in self.items for f in i.get("findings", []))
