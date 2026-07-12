import json
import logging
from pathlib import Path
from typing import Any
from pydantic import BaseModel
from app.config import settings as env_settings

logger = logging.getLogger(__name__)

class AppSettings(BaseModel):
    llm_provider: str = "deepseek"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

class SettingsManager:
    def __init__(self, data_dir: str):
        self.settings_file = Path(data_dir) / "settings.json"
        self._current_settings = AppSettings()
        self.load()

    def load(self) -> AppSettings:
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._current_settings = AppSettings(**data)
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
        return self._current_settings

    def save(self, new_settings: AppSettings):
        self._current_settings = new_settings
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, "w", encoding="utf-8") as f:
                f.write(self._current_settings.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get(self) -> AppSettings:
        return self._current_settings

settings_manager = SettingsManager(env_settings.data_dir)
