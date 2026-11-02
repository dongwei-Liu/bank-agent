"""Separate durable Agent worker; run with ``python agent_worker.py``."""

import logging
import time

from api.agent import (
    execute_agent_message,
    get_agent_graph,
    get_agent_router,
)
from clients.fineract import FineractError
from core.config import get_settings
from core.database import session_factory
from core.deps import get_fineract_client
from core.errors import DomainError
from services.agent_conversation_service import AgentConversationService


def run_one() -> bool:
    settings = get_settings()
    with session_factory()() as db:
        service = AgentConversationService(db, settings)
        run_id = service.claim_one()
        if run_id is None:
            return False
        try:
            run, user, body = service.execution_input(run_id)
            option_ref = run.request.get("option_ref")
            trusted_option = (
                service.resolve_reference(user, run.conversation_id, option_ref)
                if option_ref
                else None
            )
            response = execute_agent_message(
                body,
                user,
                db,
                get_agent_router(),
                get_agent_graph,
                trace_id=run.trace_id,
                run_id=run.id,
                conversation_id=run.conversation_id,
                reference_service=service,
                selected_option_ref=option_ref,
                trusted_option=trusted_option,
                trusted_history_routing=True,
            )
            service.complete(run_id, response)
        except DomainError as exc:
            db.rollback()
            AgentConversationService(db, settings).fail(
                run_id,
                exc.code,
                exc.message,
                retryable=exc.retryable,
            )
        except FineractError:
            db.rollback()
            AgentConversationService(db, settings).fail(
                run_id,
                "UPSTREAM_ERROR",
                "核心银行服务暂时不可用",
                retryable=True,
            )
        except Exception:
            logging.exception("Agent run %s failed", run_id)
            db.rollback()
            AgentConversationService(db, settings).fail(
                run_id,
                "AGENT_UNAVAILABLE",
                "Agent 服务暂时不可用",
                retryable=True,
            )
        return True


def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    last_cleanup = 0.0
    client = get_fineract_client()
    try:
        while True:
            worked = run_one()
            if time.monotonic() - last_cleanup >= 3600:
                try:
                    with session_factory()() as db:
                        removed = AgentConversationService(db, settings).cleanup_expired()
                    if removed:
                        logging.info("Removed %s expired Agent conversations", removed)
                except Exception:
                    logging.exception("Agent conversation cleanup failed")
                last_cleanup = time.monotonic()
            if not worked:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
