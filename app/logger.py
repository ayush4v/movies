"""Structured logging setup with rotating file handler and console output."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from app.config import get_settings


def setup_logger(name: str = "telegram_bot") -> logging.Logger:
    """Configures and returns a logger instance with console and file handlers."""
    settings = get_settings()
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if setup_logger is called repeatedly
    if logger.handlers:
        return logger

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    try:
        log_dir = os.path.dirname(settings.log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            settings.log_file_path,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not initialize file log handler: {e}")

    return logger


logger = setup_logger()
