import re
from pathlib import Path

import httpx

from .config import get_settings
from .errors import ApiError

_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"


class CannotGenerateError(ApiError):
    def __init__(self):
        super().__init__(400, "VALIDATION_ERROR", "Не удалось понять вопрос, попробуйте переформулировать.")


class LlmUnavailableError(ApiError):
    def __init__(self):
        super().__init__(500, "LLM_UNAVAILABLE", "Сервис генерации запросов недоступен.")


def load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_prompt(schema_json: str, question: str, history_pairs: list[tuple[str, str]]) -> str:
    if history_pairs:
        lines = ["Предыдущие вопросы и SQL (для контекста уточнений):"]
        for prev_q, prev_sql in history_pairs[-3:]:
            lines.append(f"Вопрос: {prev_q}")
            lines.append(f"SQL: {prev_sql}")
        history = "\n".join(lines)
    else:
        history = ""
    template = load_prompt_template()
    return template.format(schema=schema_json, question=question, history=history)


def extract_sql(text: str) -> str:
    if not text or not text.strip():
        raise CannotGenerateError()
    text = text.strip()
    if text.upper() == "CANNOT_GENERATE":
        raise CannotGenerateError()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    text = text.strip().rstrip(";").strip()
    if not text:
        raise CannotGenerateError()
    return text


def call_llm(prompt: str) -> str:
    settings = get_settings()
    url = settings.LLM_API_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": 0,
    }
    try:
        # local_address="0.0.0.0" forces IPv4: some providers publish AAAA records
        # that blackhole on networks without working IPv6, hanging httpx requests.
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        with httpx.Client(transport=transport, timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.HTTPError:
        raise LlmUnavailableError()
    if resp.status_code != 200:
        raise LlmUnavailableError()
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        raise LlmUnavailableError()
    if not content or not content.strip():
        raise LlmUnavailableError()
    return content
