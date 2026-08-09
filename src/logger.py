import logging
import sys
from types import FrameType

from loguru import logger

from src.settings import settings

LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan> - <level>{message}</level>"
)


class InterceptHandler(logging.Handler):
    """Перенаправляет записи стандартного logging в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def setup_logging() -> None:
    """Настраивает вывод логов в stderr и перехват стандартного logging."""
    logger.remove()
    logger.add(sink=sys.stderr, level=settings.log_level, format=LOG_FORMAT)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # FastStream и uvicorn вешают собственные обработчики и не пропускают
    # записи к корневому логгеру — снимаем их, чтобы всё шло через loguru.
    for name in list(logging.root.manager.loggerDict):
        if name.split(".")[0] in {"faststream", "uvicorn"}:
            intercepted = logging.getLogger(name)
            intercepted.handlers = []
            intercepted.propagate = True
