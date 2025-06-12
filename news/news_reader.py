import asyncio
from typing import List
import feedparser

class NewsReader:
    """
    Класс для чтения новостей через RSS.
    """
    def __init__(self, feed_urls: List[str]):
        """Инициализация с перечнем URL RSS-лент"""
        self.feed_urls = feed_urls

    async def fetch_feed(self, url: str) -> feedparser.FeedParserDict:
        """Асинхронное получение и парсинг одной RSS-ленты"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, feedparser.parse, url)

    async def get_latest_entries(self, max_items: int = 5) -> List[dict]:

        tasks = [self.fetch_feed(url) for url in self.feed_urls]
        feeds = await asyncio.gather(*tasks, return_exceptions=True)
        entries = []
        for feed in feeds:
            if hasattr(feed, 'entries'):
                for entry in feed.entries[:max_items]:
                    entries.append({
                        'title': entry.get('title', ''),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', '')
                    })
        return entries
