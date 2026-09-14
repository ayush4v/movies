"""FastAPI application providing health checks and storage webhook receivers."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from sqlalchemy import text
from app import __version__
from app.config import get_settings
from app.database.session import get_db
from app.logger import logger
from app.storage.factory import get_storage_provider

START_TIME = datetime.now(timezone.utc)


def create_api_app(sync_service=None, bot_app=None) -> FastAPI:
    """Create configured FastAPI application."""
    app = FastAPI(
        title="Telegram Automation Bot API",
        description="Healthcheck endpoint and official cloud webhook ingestion.",
        version=__version__,
    )

    @app.get("/")
    async def root():
        bot_info = None
        if bot_app and hasattr(bot_app, "bot"):
            try:
                me = await bot_app.bot.get_me()
                bot_info = {"id": me.id, "username": f"@{me.username}", "first_name": me.first_name}
            except Exception as e:
                bot_info = {"error": str(e)}

        return {
            "name": "Telegram Automation Bot",
            "version": __version__,
            "status": "online",
            "bot": bot_info,
        }

    @app.get("/health")
    async def health_check():
        """Production health check endpoint verifying database, telegram, and storage connectivity."""
        settings = get_settings()
        db_healthy = False
        db_error = None

        # 1. Database Health Check
        try:
            async with get_db() as session:
                await session.execute(text("SELECT 1;"))
                db_healthy = True
        except Exception as e:
            db_error = str(e)
            logger.error(f"Healthcheck: Database connectivity failed: {e}")

        # 2. Storage Provider Health Check
        provider = get_storage_provider()
        storage_healthy = await provider.validate_connection()

        # 3. Telegram Bot Health Check
        telegram_healthy = False
        telegram_details = {}
        if bot_app and hasattr(bot_app, "bot"):
            try:
                me = await bot_app.bot.get_me()
                telegram_healthy = True
                telegram_details = {
                    "status": "up",
                    "id": me.id,
                    "username": f"@{me.username}",
                    "polling": bool(bot_app.updater and bot_app.updater.running),
                }
            except Exception as tg_err:
                telegram_details = {"status": "down", "error": str(tg_err)}
        else:
            telegram_details = {"status": "unattached"}

        uptime_seconds = (datetime.now(timezone.utc) - START_TIME).total_seconds()
        is_healthy = db_healthy and storage_healthy

        return {
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": round(uptime_seconds, 2),
            "version": __version__,
            "components": {
                "database": {
                    "status": "up" if db_healthy else "down",
                    "error": db_error,
                },
                "telegram": telegram_details,
                "storage_provider": {
                    "name": provider.provider_name,
                    "status": "up" if storage_healthy else "degraded",
                },
            },
        }

    @app.post("/webhook/storage")
    async def storage_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        x_webhook_secret: Optional[str] = Header(None),
    ):
        """Official webhook receiver for cloud storage upload notifications (e.g. TeraBox push events)."""
        settings = get_settings()

        # Validate secret if configured
        if settings.terabox_webhook_secret:
            if x_webhook_secret != settings.terabox_webhook_secret:
                logger.warning("Rejected webhook: Invalid webhook secret token.")
                raise HTTPException(status_code=403, detail="Invalid webhook secret")

        try:
            payload = await request.json()
            logger.info(f"Received storage webhook event: {payload.get('event', 'unknown')}")
        except Exception:
            payload = {}

        # Trigger background sync if sync service is registered
        if sync_service:
            background_tasks.add_task(sync_service.run_sync, sync_source="webhook")

        return {"status": "accepted", "event": payload.get("event", "sync_triggered")}

    return app
