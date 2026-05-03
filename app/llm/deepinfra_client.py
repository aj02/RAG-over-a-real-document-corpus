"""DeepInfra client (DeepSeek + other open-weight models).

DeepInfra serves a wide range of open models (DeepSeek-V3, DeepSeek-R1,
Llama, Qwen, …) behind an OpenAI-compatible chat-completions endpoint at
``https://api.deepinfra.com/v1/openai``. We therefore reuse the official
OpenAI Python SDK with a custom ``base_url`` rather than maintaining a
separate HTTP client.

Notes on JSON mode:
  - DeepSeek-V3 honours ``response_format={"type": "json_object"}``.
  - DeepSeek-R1 (reasoning model) emits a `reasoning_content` field
    *before* the answer; some hosts return a 400 if `response_format` is
    set. If you switch to R1, drop ``response_format`` here and rely on
    ``parse_model_json`` to extract the JSON object from the answer text.
"""

from __future__ import annotations

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import get_settings
from app.llm.base import LLMResponse
from app.logging import get_logger

log = get_logger(__name__)


class DeepInfraClient:
    name = "deepinfra"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.deepinfra_api_key:
            raise RuntimeError(
                "DEEPINFRA_API_KEY is unset but LLM_PROVIDER=deepinfra"
            )
        self._client = AsyncOpenAI(
            api_key=settings.deepinfra_api_key,
            base_url=settings.deepinfra_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,  # tenacity handles retries below
        )
        self._model = settings.deepinfra_model
        log.info(
            "deepinfra.client_ready",
            model=self._model,
            base_url=settings.deepinfra_base_url,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=4.0),
        retry=retry_if_exception_type(
            (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)
        ),
        reraise=True,
    )
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        choice = resp.choices[0]
        text = choice.message.content or ""
        usage = resp.usage
        return LLMResponse(
            text=text,
            model=resp.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
