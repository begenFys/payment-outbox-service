import sys

from loguru import logger

from src.settings import settings

LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan> - <level>{message}</level>"
)


def setup_logging() -> None:
    logger.remove()
    logger.add(sink=sys.stderr, level=settings.log_level, format=LOG_FORMAT)
