import asyncio
from typing import Optional

from openai import AsyncOpenAI

from ai_marketer import config
from ai_marketer.logging_utils import log_event

client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


async def chatgpt_answer(prompt: str, system: Optional[str] = None, temperature: float = config.TEMPERATURE) -> str:
    sys_msg = system or (
        "Ты — AI-маркетолог 360° в России в 2025 году, эксперт по стратегиям роста бизнеса, аналитике и автоматизации. "
        "Отвечай чётко, по делу. Анализируй существующую информацию на данный момент по законам РФ и стратегиям, используемых "
        "в РФ и отвечай с их пониманием. Укладывай свой ответ в 4096 символов (русских символов, кириллица)"
    )
    last_err = None
    for attempt in range(config.OPENAI_RETRIES):
        try:
            resp = await client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
            answer = (resp.choices[0].message.content or "").strip()
            log_event(
                user_id=0,  # потом заменим на реальный ID в текстовом роутере
                user_message=prompt,
                bot_answer=answer,
                stage="chatgpt_core",
            )
            return answer
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            await asyncio.sleep(0.8 * (attempt + 1))
    if last_err:
        raise last_err
    return ""


async def ask_gpt_with_typing(bot, chat_id: int, prompt: str, system: Optional[str] = None, temperature: float = config.TEMPERATURE):
    """Показывает статус typing и вызывает chatGPT с ретраями."""
    try:
        if bot and chat_id:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        pass
    return await chatgpt_answer(prompt, system=system, temperature=temperature)
