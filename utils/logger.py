import logging
import sys

from loguru import logger

from config import settings


class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentation.
    See https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger() -> None:
    """
    Configures the logger.
    """
    # Remove all existing handlers
    logger.remove()

    # Determine log level
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    # Add stderr handler
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        serialize=False,
        backtrace=True,
        diagnose=True,
    )

    # Add file handler with rotation
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="1 week",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        backtrace=True,
        diagnose=True,
    )

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Silence noisy libraries if needed
    # logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Set exception hooks
    sys.excepthook = handle_exception
    sys.unraisablehook = lambda exc: logger.error(
        "Unraisable exception", exc=exc.exc_type, exc_info=exc.exc_value
    )


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
        "Unhandled exception"
    )
