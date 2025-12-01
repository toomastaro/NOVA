import sys

from loguru import logger

logger.configure(
    handlers=[
        {
            "sink": "logs/app.log",
            "rotation": "10 MB",
            "level": "INFO",
            "backtrace": True
        },
        {
            "sink": sys.stderr,
            "format": "<red>{time:HH:mm:ss}</red> | {level} | <level>{message}</level>",
            "level": "INFO"
        }
    ]
)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
        "Unhandled exception"
    )


sys.excepthook = handle_exception
if sys.version_info >= (3, 8):
    sys.unraisablehook = lambda exc: logger.error(
        "Unraisable exception", exc=exc.exc_type, exc_info=exc.exc_value
    )
