"""Configuration management for OCR Document Extraction System

This module provides environment-specific configuration using pydantic settings.
Configuration can be loaded from environment variables or .env files.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    """Storage configuration settings"""
    
    storage_type: str = Field(default="local", description="Storage backend type (local, s3, azure)")
    storage_path: str = Field(default="./data/storage", description="Local storage path")
    storage_bucket: Optional[str] = Field(default=None, description="Cloud storage bucket name")
    storage_region: Optional[str] = Field(default=None, description="Cloud storage region")
    encryption_enabled: bool = Field(default=True, description="Enable encryption at rest")
    
    model_config = SettingsConfigDict(env_prefix="STORAGE_")


class OCRSettings(BaseSettings):
    """OCR service configuration settings"""
    
    ocr_provider: str = Field(default="tesseract", description="OCR provider (tesseract, aws, google)")
    ocr_language: str = Field(default="eng", description="OCR language code")
    ocr_confidence_threshold: float = Field(default=0.7, description="Minimum confidence threshold")
    ocr_rate_limit: int = Field(default=10, description="Maximum OCR requests per second")
    
    model_config = SettingsConfigDict(env_prefix="OCR_")


class SearchSettings(BaseSettings):
    """Search engine configuration settings"""
    
    search_backend: str = Field(default="memory", description="Search backend (memory, elasticsearch)")
    search_host: Optional[str] = Field(default=None, description="Search service host")
    search_port: Optional[int] = Field(default=None, description="Search service port")
    search_index_name: str = Field(default="documents", description="Search index name")
    
    model_config = SettingsConfigDict(env_prefix="SEARCH_")


class CacheSettings(BaseSettings):
    """Cache configuration settings"""
    
    cache_enabled: bool = Field(default=True, description="Enable document caching")
    cache_ttl_seconds: int = Field(default=3600, description="Cache TTL in seconds")
    cache_max_size: int = Field(default=1000, description="Maximum cache entries")
    
    model_config = SettingsConfigDict(env_prefix="CACHE_")


class SecuritySettings(BaseSettings):
    """Security configuration settings"""
    
    malware_scan_enabled: bool = Field(default=True, description="Enable malware scanning")
    tls_enabled: bool = Field(default=True, description="Enable TLS for network communications")
    allowed_file_types: list[str] = Field(
        default=["image/png", "image/jpeg", "image/jpg", "image/tiff", "application/pdf"],
        description="Allowed file content types"
    )
    
    model_config = SettingsConfigDict(env_prefix="SECURITY_")


class RetrySettings(BaseSettings):
    """Retry and resilience configuration settings"""
    
    retry_max_attempts: int = Field(default=3, description="Maximum retry attempts")
    retry_initial_delay: float = Field(default=1.0, description="Initial retry delay in seconds")
    retry_max_delay: float = Field(default=60.0, description="Maximum retry delay in seconds")
    retry_exponential_base: float = Field(default=2.0, description="Exponential backoff base")
    
    model_config = SettingsConfigDict(env_prefix="RETRY_")


class LoggingSettings(BaseSettings):
    """Logging configuration settings"""
    
    log_level: str = Field(default="INFO", description="Logging level")
    log_json: bool = Field(default=False, description="Output logs in JSON format")
    
    model_config = SettingsConfigDict(env_prefix="LOG_")


class Settings(BaseSettings):
    """Main application settings"""
    
    app_name: str = Field(default="OCR Document Extraction", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    
    # Component settings
    storage: StorageSettings = Field(default_factory=StorageSettings)
    ocr: OCRSettings = Field(default_factory=OCRSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance.
    
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment.
    
    Returns:
        New settings instance
    """
    global _settings
    _settings = Settings()
    return _settings
