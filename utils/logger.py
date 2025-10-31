import logging

_DEFAULT_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
_DEFAULT_LEVEL = logging.INFO


def setup_logging(level: int = _DEFAULT_LEVEL, fmt: str = _DEFAULT_FORMAT) -> None:
    """Configure root logger once."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    logging.basicConfig(level=level, format=fmt)


def get_logger(name: str) -> logging.Logger:
    """Ensure logging configured and return module-specific logger."""
    setup_logging()
    return logging.getLogger(name)
