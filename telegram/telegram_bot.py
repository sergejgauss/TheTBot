import os
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from ai.chatgpt import ChatGPTClient
from news.news_reader import NewsReader
from datetime import datetime, timedelta, timezone
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # папка telegram/
PROJECT_DIR = os.path.dirname(BASE_DIR)                 # корень проекта
PROMPT_PATH = os.path.join(PROJECT_DIR, 'ai', 'Prompts', 'estimate_news.txt')
SUBSCRIBERS_FILE = "subscribers.txt"
NEWS_READ = "news_read.txt"

class TelegramBot:
    def __init__(self):
        load_dotenv()
        token = os.getenv("TELEGRAM_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHATID")
        if not token or not chat_id:
            raise RuntimeError("TELEGRAM_TOKEN or CHAT_ID not found in .env")

        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.dp = Dispatcher()
        self.chatgpt = ChatGPTClient()

        try:
            with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
                self.subscribers = set(json.load(f))
        except FileNotFoundError:
            self.subscribers = set()

        try:
            with open(NEWS_READ, 'r', encoding='utf-8') as f:
                self.news_complete = set(json.load(f))
        except FileNotFoundError:
            self.news_complete = set()    

        feeds = [
            'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml'
        ]
        self.news_reader = NewsReader(feeds)

        self._register_handlers()

    def _save_subscribers(self):
        with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(self.subscribers), f)    

    def _save_news_complete(self):
        with open(NEWS_READ, 'w', encoding='utf-8') as f:
            json.dump(list(self.news_complete), f)    

    def _register_handlers(self):
        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            await message.reply("Привет! Бот для трейдинга и новостей запущен 🚀")

        @self.dp.message(Command("goaway"))
        async def cmd_goaway(message: types.Message):
            await message.reply("ok i go")

        @self.dp.message(Command("ask"))
        async def cmd_ask(message: types.Message):
            prompt = message.get_args()
            if not prompt:
                return await message.reply("Укажите вопрос после /ask")
            await message.chat.do("typing")
            ans = await self.chatgpt.generate(prompt)
            await message.reply(ans)

        @self.dp.message(Command("news"))
        async def cmd_news(message: types.Message):
            entries = await self.news_reader.get_latest_entries(max_items=3)
            if not entries:
                return await message.reply("Не удалось получить новости.")
            text = "Последние новости:".join([
                f"• [{e['title']}]({e['link']}) ({e['published']})" for e in entries
            ])
            await message.reply(text, parse_mode="Markdown")

        @self.dp.message(Command("subscribe"))
        async def cmd_subscribe(message: types.Message):
            cid = message.chat.id
            if cid in self.subscribers:
                await message.reply("Вы уже подписаны на рассылку.")
            else:
                self.subscribers.add(cid)
                self._save_subscribers()
                await message.reply("Вы успешно подписались!")

        @self.dp.message(Command("unsubscribe"))
        async def cmd_unsubscribe(message: types.Message):
            cid = message.chat.id
            if cid in self.subscribers:
                self.subscribers.remove(cid)
                self._save_subscribers()
                await message.reply("Вы отписались от рассылки.")
            else:
                await message.reply("Вы не были подписаны.")

    async def _news_scheduler(self):
        print("Start read news")

        while True:
            entries = await self.news_reader.get_latest_entries(max_items=25)
            print("########################################################")
            print(f"{datetime.now()} News: Found {len(entries)} news")
            for entry in entries:
              try:  
                if entry['link'] not in self.news_complete:
                    # Анализируем новость через ChatGPT
                    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
                     prompt = f.read()
                     prompt = prompt.replace("--link--", entry['link'])
                    print(prompt) 
                    # Получаем результат анализа
                    analysis = await self.chatgpt.generate(prompt, max_tokens=500, temperature=0.0)
                    important_value = 80 
                    print(analysis)
                    print("#############################################################")
                    # Отправляем сообщение с анализом если важное
                    analysis_data = json.loads(analysis)
                    if analysis_data["important"] >= 70:
                        text = (
                            f"*{analysis_data["description"]}*  \n\n"
                            f"Вероятность реакции: {analysis_data["important"]}% {"\u2757\uFE0F" if analysis_data["important"] >= 80 else ""}  \n\n"
                            f"Влияние на: {', '.join({0: 'Акции', 1: 'Металлы', 2: 'Криптовалюта', 3: 'Валютный рынок'}.get(c, 'Неизвестно') for c in analysis_data['source'])} \n"
                            f"Сектора: {', '.join(c["name"]+"("+c["id"]+")" for c in analysis_data['targets'])} \n\n"
                            f"{"\U0001F4C8 Рост" if analysis_data["UpDown"] else "\U0001F4C9 Падение"} до {analysis_data["change"]}% \n"
                            f"\u231A Время реакции от {analysis_data["start"]} до {analysis_data["end"]} часов \n\n"
                            f"Причина: {analysis_data["why"]} \n\n"
                            f"Оригинальная ссылка: {analysis_data["link"]}"
                        )
                        for cid in self.subscribers:
                         await self.bot.send_message(chat_id=cid, text=text, parse_mode="Markdown")                        
                    self.news_complete.add(entry['link'])
              except Exception as ex:
                   print(f"Error {ex}")    
            # Очищаем кэш старых ссылок для экономии памяти
            if len(self.news_complete) > 1000:
                del self.news_complete[:900]
            self._save_news_complete() 
            await asyncio.sleep(1800)

    async def _run(self):
        # Запускаем фоновый шедулер и поллинг
        asyncio.create_task(self._news_scheduler())
        await self.dp.start_polling(self.bot)

    def run(self):
        # Обёртка для запуска всего
        asyncio.run(self._run())