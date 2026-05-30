"""Main entry point for DocuSense System

This module provides the main entry point for running the application.
"""

import sys

from config.settings import get_settings
from src.logging_config import configure_logging, get_logger


def main() -> int:
    """Main application entry point.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Load settings
    settings = get_settings()
    
    # Configure logging
    configure_logging(
        log_level=settings.logging.log_level,
        json_logs=settings.logging.log_json,
    )
    
    logger = get_logger(__name__)
    
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    
    try:
        # Application initialization will go here
        logger.info("application_initialized")
        
        # Main application logic will go here
        logger.info("application_running")
        
        return 0
        
    except Exception as e:
        logger.error("application_error", error=str(e), exc_info=True)
        return 1
    finally:
        logger.info("application_shutdown")


if __name__ == "__main__":
    sys.exit(main())
