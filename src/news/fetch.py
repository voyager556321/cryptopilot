"""Fetch news headlines from various sources"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import requests
import feedparser
from abc import ABC, abstractmethod


@dataclass
class NewsItem:
    """A news headline item"""
    title: str
    url: str
    source: str
    published: Optional[datetime] = None
    summary: Optional[str] = None
    symbols_hint: Optional[List[str]] = None  # tickers this item was fetched for


class NewsProvider(ABC):
    """Abstract base class for news providers"""
    
    @abstractmethod
    def fetch(self, keywords: List[str], max_items: int = 10) -> List[NewsItem]:
        """Fetch news items matching keywords"""
        pass


class RSSNewsProvider(NewsProvider):
    """Fetch news from RSS feeds"""
    
    def __init__(self, feeds: Dict[str, str]):
        """
        Args:
            feeds: Dict mapping source name to RSS URL
        """
        self.feeds = feeds
    
    def fetch(self, keywords: List[str], max_items: int = 10) -> List[NewsItem]:
        """Fetch news from RSS feeds, filter by keywords"""
        items = []
        
        for source, url in self.feeds.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_items]:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    summary = entry.get('summary', '')
                    
                    # Check if any keyword matches
                    text = (title + ' ' + summary).lower()
                    if any(kw.lower() in text for kw in keywords):
                        # Parse published date
                        published = None
                        if 'published_parsed' in entry:
                            try:
                                import time
                                published = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                            except:
                                pass
                        
                        items.append(NewsItem(
                            title=title,
                            url=link,
                            source=source,
                            published=published,
                            summary=summary
                        ))
            except Exception as e:
                # Log error but continue
                print(f"Error fetching from {source}: {e}")
        
        # Sort by published date (newest first)
        items.sort(key=lambda x: x.published or datetime.min, reverse=True)
        return items[:max_items]


class CoinDeskProvider(RSSNewsProvider):
    """CoinDesk RSS feed"""
    
    def __init__(self):
        super().__init__({
            "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/"
        })


class CoinTelegraphProvider(RSSNewsProvider):
    """CoinTelegraph RSS feed"""
    
    def __init__(self):
        super().__init__({
            "cointelegraph": "https://cointelegraph.com/rss"
        })


class NewsFetcher:
    """Main news fetcher that aggregates from multiple providers"""
    
    def __init__(self, providers: List[NewsProvider]):
        self.providers = providers
    
    def fetch_crypto_news(
        self,
        max_items: int = 20,
        keywords: Optional[List[str]] = None
    ) -> List[NewsItem]:
        """
        Fetch crypto-related news.
        
        Args:
            max_items: Maximum number of items to return
            keywords: Optional keywords to filter by (default: common crypto keywords)
        
        Returns:
            List of NewsItem objects
        """
        if keywords is None:
            keywords = [
                "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
                "fed", "federal reserve", "cpi", "inflation", "regulation",
                "etf", "exchange", "hack", "security", "market"
            ]
        
        all_items = []
        for provider in self.providers:
            try:
                items = provider.fetch(keywords, max_items=max_items)
                all_items.extend(items)
            except Exception as e:
                print(f"Error from provider {provider.__class__.__name__}: {e}")
        
        # Deduplicate by URL
        seen_urls = set()
        unique_items = []
        for item in all_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)
        
        # Sort by date
        unique_items.sort(key=lambda x: x.published or datetime.min, reverse=True)
        return unique_items[:max_items]

