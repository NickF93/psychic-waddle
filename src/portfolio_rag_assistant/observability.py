"""Human-readable application logs without enabling third-party HTTP logs."""

import logging


def configure_logging() -> None:
    logger = logging.getLogger("portfolio_rag_assistant")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
