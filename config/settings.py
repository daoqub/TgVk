#setting.py
import os
from pydantic import BaseSettings, Field

class Config(BaseSettings):
    """Конфигурация приложения с использованием pydantic"""
    
    # Токены API
    TELEGRAM_TOKEN: str = Field(..., env="TELEGRAM_API_TOKEN")
    VK_API_TOKEN: str = Field(None, env="VK_API_TOKEN")
    
    # VK Client данные
    VK_CLIENT_ID: str = Field(None, env="VK_CLIENT_ID")
    VK_CLIENT_SECRET: str = Field(None, env="VK_CLIENT_SECRET")
    
    # Supabase
    SUPABASE_URL: str = Field(None, env="SUPABASE_URL")
    SUPABASE_KEY: str = Field(None, env="SUPABASE_KEY")
    
    # Настройки файлов
    TEMP_DIR: str = Field("./temp_files", env="TEMP_DIR")
    MAX_FILE_SIZE: int = Field(100 * 1024 * 1024, env="MAX_FILE_SIZE")  # 100MB
    
    # Настройки клиентов
    VK_API_MAX_RETRIES: int = Field(3, env="VK_API_MAX_RETRIES")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
