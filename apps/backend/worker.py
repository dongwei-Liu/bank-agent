"""Run separately: python worker.py. No in-process FastAPI scheduler."""

import logging
import time
from core.config import get_settings
from core.database import session_factory
from core.deps import get_fineract_client
from services.schedule_service import ScheduleService
from services.bill_report_service import BillReportService
from services.subscription_planning_service import SubscriptionPlanningService
from services.orchestration_service import OrchestrationService


def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    client = get_fineract_client()
    last_schedule_tick = 0.0
    last_subscription_tick = 0.0
    try:
        while True:
            if time.monotonic() - last_schedule_tick >= 30:
                try:
                    with session_factory()() as db:
                        ScheduleService(db, client, settings).tick()
                except Exception:
                    logging.exception("Transfer schedule scan failed")
                last_schedule_tick = time.monotonic()

            if time.monotonic() - last_subscription_tick >= 30:
                try:
                    with session_factory()() as db:
                        result = SubscriptionPlanningService(db, client, settings).tick_notifications()
                    if result["reminders"] or result["budgets"]:
                        logging.info("Subscription monitor tick: %s", result)
                except Exception:
                    logging.exception("Subscription reminder/budget scan failed")
                last_subscription_tick = time.monotonic()

            try:
                with session_factory()() as db:
                    BillReportService(db, client, settings).run_one()
            except Exception:
                logging.exception("Bill report worker iteration failed")
            try:
                with session_factory()() as db:
                    OrchestrationService(db, client, settings).tick()
            except Exception:
                logging.exception("Orchestration worker iteration failed")
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
