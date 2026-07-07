"""
DeepSeek / OpenAI-compatible LLM client.
Supports streaming SSE, system prompts, structured output.
"""

import json
import logging
from typing import AsyncGenerator, Optional

import httpx
from httpx import Timeout

from app.config import settings

logger = logging.getLogger(__name__)

# System prompt tailored for code-aware RAG
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


class DeepSeekClient:
    """
    LLM client for DeepSeek (OpenAI-compatible).

    Supports:
      - Synchronous chat completion
      - Server-Sent Events streaming
      - Tool/function calling (future)
    """

    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.model = settings.deepseek_model

        self._http_client = httpx.Client(
            timeout=Timeout(60.0, connect=10.0, read=60.0),
            follow_redirects=True,
        )
        self._async_http_client = httpx.AsyncClient(
            timeout=Timeout(120.0, connect=10.0, read=120.0),
            follow_redirects=True,
        )

    def _build_headers(self) -> dict:
        """Build request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a synchronous chat request.

        Args:
            messages: List of {"role": "...", "content": "..."}
            system_prompt: Optional override for system prompt.
            temperature: LLM temperature (0.0-1.0).
            max_tokens: Max tokens in response.

        Returns:
            Response text string.
        """
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            response = self._http_client.post(
                f"{self.base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"DeepSeek API call failed: {e}")
            # Try to extract error details
            if hasattr(e, "response") and e.response:
                try:
                    detail = e.response.json()
                    logger.error(f"API error detail: {detail}")
                except Exception:
                    pass
            raise

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat via SSE.

        Args:
            messages: List of {"role": "...", "content": "..."}
            system_prompt: Optional override for system prompt.

        Yields:
            Text chunks as they arrive.
        """
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with self._async_http_client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"DeepSeek streaming failed: {e}")
            yield f"\n\n[Error generating response: {str(e)}]"

    def close(self):
        """Close HTTP clients."""
        self._http_client.close()
        import asyncio
        try:
            asyncio.get_event_loop().run_until_complete(
                self._async_http_client.aclose()
            )
        except Exception:
            pass