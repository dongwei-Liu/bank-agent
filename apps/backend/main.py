from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from api.accounts import router as accounts_router
from api.health import router as health_router
from api.auth import router as auth_router
from api.transfers import router as transfers_router
from api.billing import router as billing_router
from api.investments import router as investments_router
from api.subscriptions import router as subscriptions_router
from api.cards import router as cards_router
from api.demo_cards import router as demo_cards_router
from api.tasks import router as tasks_router
from api.agent import router as agent_router, stream_router as agent_stream_router
from clients.fineract import (
    FineractError,
    FineractUnavailableError,
    FineractNotFoundError,
)
from core.config import get_settings
from core.errors import DomainError


@asynccontextmanager
async def lifespan(app):
    if len(get_settings().otp_secret) < 32:
        raise RuntimeError("必须配置至少32字符的 OTP_SECRET；先运行初始化脚本")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Bank Agent Backend",
        description="银行业务与受控 Agent API；资金事实与执行来自 Apache Fineract。",
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def private_analysis_cache_policy(request: Request, call_next):
        response = await call_next(request)
        if (request.url.path.startswith("/api/agent/analyses/")
                or request.url.path.startswith("/api/bill-reports")
                or request.url.path.startswith("/api/bill-report")):
            # Includes report summaries, details, snapshots, auth and error responses.
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                }
            },
        )

    @app.exception_handler(FineractError)
    async def upstream_error(request: Request, exc: FineractError):
        status = (
            503
            if isinstance(exc, FineractUnavailableError)
            else 404
            if isinstance(exc, FineractNotFoundError)
            else 502
        )
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": str(exc),
                    "retryable": False,
                }
            },
        )

    for router in [
        health_router,
        auth_router,
        accounts_router,
        transfers_router,
        billing_router,
        investments_router,
        subscriptions_router,
        cards_router,
        demo_cards_router,
        tasks_router,
        agent_router,
        agent_stream_router,
    ]:
        app.include_router(router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
