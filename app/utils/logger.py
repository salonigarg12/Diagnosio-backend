import logging
import sys
import contextvars
from typing import Optional

# Context variable to hold request correlation ID across async tasks
request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id_ctx", default=None)

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "system"
        return True

def setup_logger(name: str = "eve_healthcare") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | [%(name)s] [req_id=%(request_id)s] | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger

logger = setup_logger()