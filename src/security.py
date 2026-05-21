"""Security features for OCR Document Extraction System

Provides TLS/SSL configuration helpers and secure connection utilities
for storage and search service communications.

Requirements: 9.1, 9.2
"""

import ssl
import structlog
from dataclasses import dataclass, field
from typing import Optional

from config.settings import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class TLSConfig:
    """TLS/SSL configuration for secure connections.

    Attributes:
        enabled: Whether TLS is enabled
        verify_certificates: Whether to verify server certificates
        ca_cert_path: Path to CA certificate bundle (None = system default)
        client_cert_path: Path to client certificate (for mutual TLS)
        client_key_path: Path to client private key (for mutual TLS)
        min_version: Minimum TLS version to accept
    """

    enabled: bool = True
    verify_certificates: bool = True
    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    min_version: int = ssl.TLSVersion.TLSv1_2


class TLSConfigBuilder:
    """Builds TLS configuration from application settings.

    Requirements: 9.2
    """

    @staticmethod
    def from_settings() -> TLSConfig:
        """Create TLS config from application settings.

        Returns:
            TLSConfig populated from settings
        """
        settings = get_settings()
        config = TLSConfig(enabled=settings.security.tls_enabled)
        logger.info(
            "TLS configuration loaded",
            tls_enabled=config.enabled,
            verify_certificates=config.verify_certificates,
        )
        return config

    @staticmethod
    def create_ssl_context(config: TLSConfig) -> Optional[ssl.SSLContext]:
        """Create an ssl.SSLContext from a TLSConfig.

        Args:
            config: TLS configuration

        Returns:
            Configured SSLContext, or None if TLS is disabled
        """
        if not config.enabled:
            logger.warning("TLS is disabled — connections will be unencrypted")
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = config.min_version

        if config.verify_certificates:
            ctx.verify_mode = ssl.CERT_REQUIRED
            if config.ca_cert_path:
                ctx.load_verify_locations(cafile=config.ca_cert_path)
            else:
                ctx.load_default_certs()
        else:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            logger.warning("Certificate verification is disabled")

        if config.client_cert_path and config.client_key_path:
            ctx.load_cert_chain(
                certfile=config.client_cert_path,
                keyfile=config.client_key_path,
            )

        logger.info("SSL context created", tls_version=str(config.min_version))
        return ctx


class EncryptionConfig:
    """Encryption-at-rest configuration.

    Validates that storage encryption is properly configured.

    Requirements: 9.1
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.encryption_enabled: bool = settings.storage.encryption_enabled
        self.logger = logger.bind(component="encryption_config")

    def is_encryption_enabled(self) -> bool:
        """Return whether encryption at rest is enabled."""
        return self.encryption_enabled

    def validate(self) -> None:
        """Validate encryption configuration.

        Logs a warning if encryption is disabled in a non-development
        environment.
        """
        settings = get_settings()
        if not self.encryption_enabled and settings.environment != "development":
            self.logger.warning(
                "Encryption at rest is DISABLED in a non-development environment",
                environment=settings.environment,
            )
        else:
            self.logger.info(
                "Encryption configuration validated",
                encryption_enabled=self.encryption_enabled,
            )


def get_tls_config() -> TLSConfig:
    """Get TLS configuration from application settings.

    Returns:
        TLSConfig instance
    """
    return TLSConfigBuilder.from_settings()


def get_encryption_config() -> EncryptionConfig:
    """Get encryption configuration.

    Returns:
        EncryptionConfig instance
    """
    return EncryptionConfig()
