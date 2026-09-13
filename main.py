"""Main application entry point for the production Telegram automation bot."""

import argparse
import asyncio
import signal
import sys
import uvicorn
from app.api.server import create_api_app
from app.bot.bot_app import build_telegram_application
from app.config import get_settings
from app.database.session import init_db
from app.logger import logger
from app.services.scheduler import PeriodicSyncScheduler
from app.services.sync_service import SyncService


async def run_sync_only() -> None:
    """Execute a single sync pass from CLI and exit."""
    settings = get_settings()
    logger.info("Initializing database...")
    await init_db()

    app = build_telegram_application(settings=settings)
    await app.initialize()

    service = SyncService(bot=app.bot, settings=settings)
    result = await service.run_sync(sync_source="cli_manual")
    logger.info(f"Sync completed successfully: {result}")

    await app.shutdown()


async def run_server() -> None:
    """Run full production system: Database, Healthcheck Server, Scheduler, and Telegram Bot."""
    settings = get_settings()

    logger.info("=====================================================")
    logger.info("Starting Telegram Automation Bot Service...")
    logger.info(f"Storage Provider: {settings.storage_provider.upper()}")
    logger.info(f"Channel ID: {settings.telegram_channel_id or 'Not Configured'}")
    logger.info(f"Admins: {len(settings.admin_user_ids)} configured")
    logger.info("=====================================================")

    # 1. Initialize SQLite database schema
    await init_db()

    # 2. Build Telegram Bot Application
    bot_app = build_telegram_application(settings=settings)
    await bot_app.initialize()
    await bot_app.start()

    # 3. Create SyncService and Scheduler
    sync_service = SyncService(bot=bot_app.bot, settings=settings)
    scheduler = PeriodicSyncScheduler(bot=bot_app.bot, settings=settings)
    scheduler.start()

    # 4. Optional initial sync on startup
    if settings.run_sync_on_startup:
        asyncio.create_task(sync_service.run_sync(sync_source="startup"))

    # 5. Start Healthcheck & Webhook API server in background
    api_app = create_api_app(sync_service=sync_service)
    uvi_config = uvicorn.Config(
        app=api_app,
        host=settings.health_check_host,
        port=settings.health_check_port,
        log_level="warning",
        access_log=False,
    )
    uvi_server = uvicorn.Server(uvi_config)
    server_task = asyncio.create_task(uvi_server.serve())

    # 6. Start Telegram Bot Polling
    updater = bot_app.updater
    if updater:
        try:
            # Clear any stale webhook before starting polling
            await bot_app.bot.delete_webhook(drop_pending_updates=True)
        except Exception as e:
            logger.warning(f"Could not reset webhook: {e}")

        await updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram Bot polling started. Ready to receive commands.")

    # Graceful shutdown event
    stop_event = asyncio.Event()

    def handle_signal(*args):
        logger.info("Received termination signal, shutting down gracefully...")
        stop_event.set()

    # Register OS signals if supported on platform
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except (NotImplementedError, RuntimeError):
            # Windows may not support add_signal_handler for some signals
            signal.signal(sig, lambda s, f: handle_signal())

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Initiating graceful shutdown...")
        scheduler.shutdown()
        uvi_server.should_exit = True
        await server_task

        if updater and updater.running:
            await updater.stop()
        if bot_app.running:
            await bot_app.stop()
        await bot_app.shutdown()
        logger.info("All services stopped successfully. Goodbye.")


def main():
    parser = argparse.ArgumentParser(description="Production Telegram Automation Bot")
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="Run a single storage sync pass and exit without starting the bot server.",
    )
    args = parser.parse_args()

    try:
        if args.sync_only:
            asyncio.run(run_sync_only())
        else:
            asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        import traceback
        err_msg = f"\n{'='*60}\nFATAL STARTUP CRASH:\n{traceback.format_exc()}{'='*60}\n"
        sys.stderr.write(err_msg)
        sys.stderr.flush()
        sys.stdout.write(err_msg)
        sys.stdout.flush()
        logger.critical(f"Application crashed on startup: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
