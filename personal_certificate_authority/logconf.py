import sys

from loguru import logger

from personal_certificate_authority.settings import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
