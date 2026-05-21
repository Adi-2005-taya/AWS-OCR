"""Tests for security features

Requirements: 9.1, 9.2
"""

import ssl

import pytest

from src.security import (
    EncryptionConfig,
    TLSConfig,
    TLSConfigBuilder,
    get_encryption_config,
    get_tls_config,
)


class TestTLSConfig:
    def test_default_tls_config(self):
        config = TLSConfig()
        assert config.enabled is True
        assert config.verify_certificates is True
        assert config.ca_cert_path is None
        assert config.client_cert_path is None
        assert config.client_key_path is None

    def test_disabled_tls_config(self):
        config = TLSConfig(enabled=False)
        assert config.enabled is False

    def test_custom_ca_cert(self):
        config = TLSConfig(ca_cert_path="/etc/ssl/certs/ca.pem")
        assert config.ca_cert_path == "/etc/ssl/certs/ca.pem"


class TestTLSConfigBuilder:
    def test_from_settings_returns_tls_config(self):
        config = TLSConfigBuilder.from_settings()
        assert isinstance(config, TLSConfig)

    def test_create_ssl_context_disabled_returns_none(self):
        config = TLSConfig(enabled=False)
        ctx = TLSConfigBuilder.create_ssl_context(config)
        assert ctx is None

    def test_create_ssl_context_enabled_returns_context(self):
        config = TLSConfig(enabled=True, verify_certificates=False)
        ctx = TLSConfigBuilder.create_ssl_context(config)
        assert isinstance(ctx, ssl.SSLContext)

    def test_create_ssl_context_no_verify(self):
        config = TLSConfig(enabled=True, verify_certificates=False)
        ctx = TLSConfigBuilder.create_ssl_context(config)
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_create_ssl_context_with_verify(self):
        config = TLSConfig(enabled=True, verify_certificates=True)
        ctx = TLSConfigBuilder.create_ssl_context(config)
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_create_ssl_context_minimum_tls_version(self):
        config = TLSConfig(enabled=True, verify_certificates=False)
        ctx = TLSConfigBuilder.create_ssl_context(config)
        assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2


class TestEncryptionConfig:
    def test_encryption_config_creation(self):
        ec = EncryptionConfig()
        assert isinstance(ec.is_encryption_enabled(), bool)

    def test_validate_does_not_raise(self):
        ec = EncryptionConfig()
        ec.validate()  # Should not raise


class TestSecurityHelpers:
    def test_get_tls_config_returns_tls_config(self):
        config = get_tls_config()
        assert isinstance(config, TLSConfig)

    def test_get_encryption_config_returns_encryption_config(self):
        ec = get_encryption_config()
        assert isinstance(ec, EncryptionConfig)
