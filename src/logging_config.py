"""
Logging configuration for ClusterSecret operator.

Environment variables:
- LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- LOG_ENCODER: plain, json (default: plain)
- LOG_FORMAT: Python format string (default: %(asctime)s - %(name)s - %(levelname)s - %(message)s)
           Only used when LOG_ENCODER=plain
- LOG_INCLUDE_KOPF: true, false (default: false) - Include Kopf framework logs in configuration
"""

import logging
import os
import sys
from functools import cache
from typing import Optional

from pythonjsonlogger.json import JsonFormatter as BaseJsonFormatter


DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_LOG_ENCODER = 'plain'

VALID_LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
VALID_LOG_ENCODERS = ('plain', 'json')


@cache
def get_log_level() -> int:
    """Get logging level from LOG_LEVEL environment variable."""
    level_str = os.getenv('LOG_LEVEL', DEFAULT_LOG_LEVEL).upper()
    if level_str not in VALID_LOG_LEVELS:
        level_str = DEFAULT_LOG_LEVEL
    return getattr(logging, level_str)


@cache
def get_log_encoder() -> str:
    """Get log encoder from LOG_ENCODER environment variable."""
    encoder = os.getenv('LOG_ENCODER', DEFAULT_LOG_ENCODER).lower()
    if encoder not in VALID_LOG_ENCODERS:
        return DEFAULT_LOG_ENCODER
    return encoder


@cache
def get_log_format() -> str:
    """Get log format from LOG_FORMAT environment variable."""
    return os.getenv('LOG_FORMAT', DEFAULT_LOG_FORMAT)


@cache
def get_include_kopf() -> bool:
    """Get whether to include Kopf logs from LOG_INCLUDE_KOPF environment variable."""
    include_kopf = os.getenv('LOG_INCLUDE_KOPF', 'false')
    return include_kopf.lower() == 'true'


def create_handler() -> logging.Handler:
    """Create a logging handler with the configured formatter."""
    handler = logging.StreamHandler(sys.stdout)

    if get_log_encoder() == 'json':
        formatter = BaseJsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
            rename_fields={'asctime': 'timestamp', 'levelname': 'level'},
        )
    else:
        formatter = logging.Formatter(get_log_format())

    handler.setFormatter(formatter)
    return handler


def configure_logging(logger: Optional[logging.Logger] = None) -> None:
    """
    Configure logging for the ClusterSecret operator.

    Args:
        logger: Optional logger to use for startup messages. If None, uses root logger.
    """
    log_level = get_log_level()
    include_kopf = get_include_kopf()

    handler = create_handler()
    handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Configure Kopf loggers if requested
    if include_kopf:
        kopf_loggers = ['kopf.objects', 'kopf.activities', 'kopf.reactor', 'kopf._core']
        for kopf_logger_name in kopf_loggers:
            kopf_logger = logging.getLogger(kopf_logger_name)
            kopf_logger.setLevel(log_level)
    else:
        # Set Kopf loggers to WARNING to reduce noise
        kopf_loggers = ['kopf.objects', 'kopf.activities', 'kopf.reactor', 'kopf._core']
        for kopf_logger_name in kopf_loggers:
            kopf_logger = logging.getLogger(kopf_logger_name)
            kopf_logger.setLevel(logging.WARNING)

    # Log configuration info
    msg_logger = logger if logger else logging.getLogger(__name__)

    if log_level == logging.DEBUG:
        msg_logger.warning(
            """
      #########################################################################
      # DEBUG MODE ON - NOT FOR PRODUCTION                                    #
      # On this mode secrets are leaked to stdout, this is not safe!. NO-GO ! #
      #########################################################################
            """
        )

    msg_logger.info(
        f'Logging configured: level={logging.getLevelName(log_level)}, '
        f'encoder={get_log_encoder()}, include_kopf={include_kopf}'
    )
