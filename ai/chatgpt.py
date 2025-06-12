import os
from dotenv import load_dotenv
import asyncio
from openai import OpenAI

class ChatGPTClient:
    def __init__(self):
        """
        Клиент для работы с OpenAI Chat API. Использует модель из переменной окружения OPENAI_MODEL или 'gpt-3.5-turbo' по умолчанию.
        При ошибке квоты возвращает сообщение об исчерпании.
        """
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found in .env")

        # Инициализация клиента OpenAI
        self.client = OpenAI(api_key=api_key)
        # Модель по умолчанию
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    async def generate(self, prompt: str, max_tokens: int = 150, temperature: float = 0.7) -> str:
        """
        Отправляет запрос в OpenAI Chat API и возвращает ответ.
        При превышении квоты возвращает понятное сообщение.
        """
        loop = asyncio.get_event_loop()
        try:
            # Выполняем синхронный запрос в executor
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            )
        except Exception as e:
            text = str(e).lower()
            if 'quota' in text or 'insufficient_quota' in text or 'rate limit' in text:
                return "Извините, квота на использование API исчерпана. Попробуйте позже или проверьте настройки биллинга."
            else:
                raise
        return response.choices[0].message.content.strip()
