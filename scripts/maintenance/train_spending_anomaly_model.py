"""Pretrain trusted personal models, or clean expired private analysis snapshots."""
import argparse
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/backend'))
from sqlalchemy import delete
from clients.fineract import FineractClient
from core.config import get_settings
from core.database import session_factory
from core.errors import require
from core.security import now
from models import AnalysisResult, User
from services.anomaly_detection_service import AnomalyDetectionService
from services.billing_service import BillingService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id', help='Existing bank_agent user UUID')
    parser.add_argument('--as-of', type=date.fromisoformat, help='Exclusive training cutoff YYYY-MM-DD')
    parser.add_argument('--cleanup-results', action='store_true')
    args = parser.parse_args()
    if not args.cleanup_results and (not args.user_id or not args.as_of):
        parser.error('--user-id and --as-of are required for training')
    settings = get_settings()
    with session_factory()() as db:
        if args.cleanup_results:
            result = db.execute(delete(AnalysisResult).where(AnalysisResult.expires_at <= now()))
            db.commit()
            print(f'Expired private results removed: {result.rowcount}')
            return
        user = db.get(User, args.user_id)
        require(user and user.active and user.tenant == settings.fineract_tenant,
                'NOT_FOUND', '有效用户映射不存在', 404)
        client = FineractClient(settings)
        try:
            row = AnomalyDetectionService(BillingService(db, client, settings)).train(user, args.as_of)
            db.commit()
            print(f'Model maintenance completed: status={row.status}, model_id={row.id}')
            for profile, info in row.metadata_.get('profiles', {}).items():
                print(f'Profile {profile}: {info["status"]}')
        finally:
            client.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Maintenance failed: {type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)
