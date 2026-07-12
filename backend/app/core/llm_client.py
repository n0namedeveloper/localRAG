import json
import logging
from typing import AsyncGenerator
from abc import ABC, abstractmethod

import httpx
from httpx import Timeout

from app.config import settings as env_settings
from app.core.settings_manager import settings_manager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI assistant that helps developers understand codebases.
You have access to repository code via RAG.

RESPONSE RULES:
1. ALWAYS cite sources: `[src/file_path:start_line-end_line]` for every statement.
2. Code link format: `[src/auth/login.py:42-58]`
3. When mentioning functions — include their signature and file.
4. When explaining file relationships — clearly state the import/export chain.
5. Answer in the same language as the question (English or Russian).
6. If there's no exact answer in the code — state this honestly.
7. When providing code examples — use markdown with language specification.

RESPONSE STRUCTURE:
1. Brief answer (1-2 sentences)
2. Detailed explanation with specific functions/classes mentioned
3. Dependencies and relationships with other files (if any)
4. Usage example (if applicable)"""


class BaseLLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], system_prompt: str | None = None, temperature: float = 0.2, max_tokens: int = 4096) -> str:
        pass

    @abstractmethod
    async def chat_stream(self, messages: list[dict], system_prompt: str | None = None, temperature: float = 0.2, max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        pass


class DeepSeekClient(BaseLLMClient):
    def __init__(self):
        conf = settings_manager.get()
        self.api_key = conf.deepseek_api_key or env_settings.deepseek_api_key
        self.base_url = env_settings.deepseek_base_url.rstrip("/")
        self.model = conf.deepseek_model
        self.chat_completions_path = env_settings.deepseek_chat_completions_path.lstrip("/")

        self._http_client = httpx.Client(
            timeout=Timeout(60.0, connect=10.0, read=60.0),
            follow_redirects=True,
        )
        self._async_http_client = httpx.AsyncClient(
            timeout=Timeout(120.0, connect=10.0, read=120.0),
            follow_redirects=True,
        )

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_messages(self, messages: list[dict], system_prompt: str | None) -> list[dict]:
        if system_prompt:
            return [{"role": "system", "content": system_prompt}] + messages
        return messages

    def chat(self, messages: list[dict], system_prompt: str | None = None, temperature: float = 0.2, max_tokens: int = 4096) -> str:
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            response = self._http_client.post(
                f"{self.base_url}/{self.chat_completions_path}",
                headers=self._build_headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error("DeepSeek API error %s: %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("DeepSeek API call failed", exc_info=True)
            raise

    async def chat_stream(self, messages: list[dict], system_prompt: str | None = None, temperature: float = 0.2, max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with self._async_http_client.stream(
                "POST",
                f"{self.base_url}/{self.chat_completions_path}",
                headers=self._build_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        content = choices[0].get("delta", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
                    except (KeyError, IndexError):
                        continue
        except Exception:
            logger.error("DeepSeek streaming failed", exc_info=True)
            yield "\n\n[Error generating response]"


class OllamaClient(BaseLLMClient):
    def __init__(self):
        conf = settings_manager.get()
        self.base_url = conf.ollama_base_url.rstrip("/")
        self.model = conf.ollama_model

        self._http_client = httpx.Client(
            timeout=Timeout(120.0, connect=10.0, read=120.0),
            follow_redirects=True,
        )
        self._async_http_client = httpx.AsyncClient(
            timeout=Timeout(300.0, connect=10.0, read=300.0),
            follow_redirects=True,
        )

    def _build_messages(self, messages: list[dict], system_prompt: str | None) -> list[dict]:
        if system_prompt:
            return [{"role": "system", "content": system_prompt}] + messages
        return messages

    def chat(self, messages: list[dict], system_prompt: str | None = None, temperature: float = 0.2, max_tokens: int = 4096) -> str:
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            },
            "stream": False,
        }

        try:
            response = self._http_client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            logger.error("Ollama API call failed", exc_info=True)
            raise

    async def chat_stream(self, messages: list[dict], system_prompt: str | None = None, temperature: float = 0.2, max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            },
            "stream": True,
        }

        try:
            async with self._async_http_client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception:
            logger.error("Ollama streaming failed", exc_info=True)
            yield "\n\n[Error generating response with Ollama]"


def get_llm_client() -> BaseLLMClient:
    conf = settings_manager.get()
    if conf.llm_provider == "ollama":
        return OllamaClient()
    return DeepSeekClient()
