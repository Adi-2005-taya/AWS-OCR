"""Structured logging configuration for DocuSense System

This module configures structured logging using structlog for consistent,
machine-readable log output across all components.
"""

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO", json_logs: bool = False) -> None:
    """Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output logs in JSON format; otherwise use console format
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if json_logs:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console output for development
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True),
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)
