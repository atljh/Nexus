"""
AI Service for generating comments via OpenAI-compatible API.

Supports:
- OpenAI (default)
- Any OpenAI-compatible API (Ollama, LM Studio, etc.) via base_url
- Fallback to None on error (caller falls back to spintax)
"""

import logging
from collections import defaultdict
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = """You are a social media commenter. Write a short, natural comment for a Telegram channel post.

Channel: {channel_title}
Post text: {post_text}

Requirements:
- Write 1-2 sentences maximum
- Be natural and conversational
- Match the tone of the channel
- Do not use hashtags or emojis excessively
- Write in the same language as the post
- Do not mention that you are an AI

Reply with ONLY the comment text, nothing else."""


class AIService:
    """OpenAI-compatible AI service for comment generation."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def generate_comment(
        self,
        post_text: str,
        channel_title: str = "",
        prompt_template: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 200,
    ) -> Optional[str]:
        """
        Generate a comment for a post using AI.

        Returns:
            Generated comment text or None on error.
        """
        template = prompt_template or DEFAULT_PROMPT
        # Safe format — unknown placeholders resolve to empty string
        format_vars = defaultdict(str, post_text=post_text[:2000], channel_title=channel_title)
        try:
            prompt = template.format_map(format_vars)
        except (KeyError, ValueError, IndexError):
            prompt = template.replace("{post_text}", post_text[:2000]).replace("{channel_title}", channel_title)

        try:
            client = self._get_client()
            response = await client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            # Remove wrapping quotes if AI added them
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            return content

        except httpx.HTTPStatusError as e:
            logger.error(f"AI API error {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
