#!/usr/bin/env python3
"""
Book Scraper - Multi-Source Book Data Collection

Sources:
1. Open Library API (free, no auth required)
2. Google Books API (free, no auth for basic usage)
3. Reddit API (via PRAW or public JSON)
4. Goodreads RSS (public feeds)

Categories:
- Mind: Personal Development, Psychology, Philosophy
- Wealth: Finance, Investing, Business
- Health: Fitness, Nutrition, Mental Health
- Skills: Productivity, Leadership, Communication
- Masculinity: Self-improvement, Relationships
"""
import json
import time
import sqlite3
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "books.db"

RAW_DIR.mkdir(parents=True, exist_ok=True)

# Categories and search terms
CATEGORIES = {
    "Mind": [
        "personal development", "psychology", "stoicism", "philosophy",
        "Jordan Peterson", "Marcus Aurelius", "Friedrich Nietzsche",
        "self improvement", "mindset", "cognitive behavior",
        "12 Rules for Life", "Man's Search for Meaning"
    ],
    "Wealth": [
        "investing", "finance personal", "wealth building", "business",
        "Rich Dad Poor Dad", "Think and Grow Rich", "Warren Buffett",
        "forex trading", "stock market", "financial freedom",
        "The Intelligent Investor", "Money Master the Game"
    ],
    "Health": [
        "fitness", "nutrition", "obesity", "fasting", "mental health",
        "Obesity Code", "Outlive", "Why We Sleep", "Atomic Habits",
        "exercise", "diet", "longevity", "biohacking"
    ],
    "Skills": [
        "productivity", "leadership", "communication", "habits",
        "Deep Work", "The 7 Habits", "How to Win Friends",
        "negotiation", "public speaking", "time management"
    ],
    "Masculinity": [
        "masculinity", "Rational Male", "No More Mr Nice Guy",
        "Way of the Superior Man", "self reliance", "confidence",
        "dating", "relationships men", "alpha male", "stoic man"
    ]
}

HEADERS = {
    'User-Agent': 'BookSentimentAnalysis/1.0 (Educational Project)'
}


def generate_book_id(title: str, author: str) -> str:
    """Generate unique book ID"""
    key = f"{title.lower().strip()}:{author.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


class Database:
    """SQLite database for storing books and reviews"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Books table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                book_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                description TEXT,
                category TEXT,
                subcategory TEXT,
                avg_rating REAL,
                ratings_count INTEGER,
                reviews_count INTEGER,
                cover_url TEXT,
                source TEXT,
                source_url TEXT,
                published_year INTEGER,
                isbn TEXT,
                pages INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Reviews table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                book_id TEXT,
                source TEXT,
                community TEXT,
                source_kind TEXT,
                category TEXT,
                query_term TEXT,
                title TEXT,
                url TEXT,
                author TEXT,
                content TEXT,
                rating REAL,
                upvotes INTEGER DEFAULT 0,
                sentiment_score REAL,
                sentiment_label TEXT,
                created_at TIMESTAMP,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books (book_id)
            )
        ''')

        review_columns = {row[1] for row in cursor.execute("PRAGMA table_info(reviews)").fetchall()}
        required_review_columns = {
            'community': 'TEXT',
            'source_kind': 'TEXT',
            'category': 'TEXT',
            'query_term': 'TEXT',
            'title': 'TEXT',
            'url': 'TEXT'
        }
        for column, column_type in required_review_columns.items():
            if column not in review_columns:
                cursor.execute(f"ALTER TABLE reviews ADD COLUMN {column} {column_type}")
        
        # Stats table (for dashboard)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_books INTEGER,
                total_reviews INTEGER,
                avg_sentiment REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def upsert_book(self, book: Dict):
        """Insert or update a book"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO books 
            (book_id, title, author, description, category, subcategory,
             avg_rating, ratings_count, reviews_count, cover_url, 
             source, source_url, published_year, isbn, pages, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            book.get('book_id'),
            book.get('title'),
            book.get('author'),
            book.get('description'),
            book.get('category'),
            book.get('subcategory'),
            book.get('avg_rating'),
            book.get('ratings_count'),
            book.get('reviews_count'),
            book.get('cover_url'),
            book.get('source'),
            book.get('source_url'),
            book.get('published_year'),
            book.get('isbn'),
            book.get('pages'),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def upsert_review(self, review: Dict):
        """Insert or update a review"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO reviews
            (review_id, book_id, source, community, source_kind, category,
             query_term, title, url, author, content, rating, upvotes,
             sentiment_score, sentiment_label, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            review.get('review_id'),
            review.get('book_id'),
            review.get('source'),
            review.get('community'),
            review.get('source_kind'),
            review.get('category'),
            review.get('query_term'),
            review.get('title'),
            review.get('url'),
            review.get('author'),
            review.get('content'),
            review.get('rating'),
            review.get('upvotes', 0),
            review.get('sentiment_score'),
            review.get('sentiment_label'),
            review.get('created_at')
        ))
        
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM books")
        total_books = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reviews")
        total_reviews = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(sentiment_score) FROM reviews WHERE sentiment_score IS NOT NULL")
        avg_sentiment = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_books': total_books,
            'total_reviews': total_reviews,
            'avg_sentiment': round(avg_sentiment, 2)
        }


class OpenLibraryScraper:
    """Scraper for Open Library API (free, no auth)"""
    
    def __init__(self):
        self.base_url = "https://openlibrary.org"
        self.search_url = "https://openlibrary.org/search.json"
    
    def search_books(self, query: str, category: str, limit: int = 20) -> List[Dict]:
        """Search for books on Open Library"""
        logger.info(f"📚 Open Library: Searching '{query}'")
        books = []
        
        try:
            params = {
                'q': query,
                'limit': limit,
                'fields': 'key,title,author_name,first_publish_year,cover_i,isbn,number_of_pages_median,ratings_average,ratings_count'
            }
            
            response = requests.get(self.search_url, params=params, headers=HEADERS, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"   Open Library returned {response.status_code}")
                return books
            
            data = response.json()
            
            for doc in data.get('docs', [])[:limit]:
                title = doc.get('title', '')
                author = ', '.join(doc.get('author_name', ['Unknown']))
                
                if not title:
                    continue
                
                book = {
                    'book_id': generate_book_id(title, author),
                    'title': title,
                    'author': author,
                    'description': '',  # Open Library search doesn't include description
                    'category': category,
                    'subcategory': query,
                    'avg_rating': doc.get('ratings_average'),
                    'ratings_count': doc.get('ratings_count', 0),
                    'reviews_count': 0,
                    'cover_url': f"https://covers.openlibrary.org/b/id/{doc.get('cover_i', '')}-M.jpg" if doc.get('cover_i') else None,
                    'source': 'openlibrary',
                    'source_url': f"https://openlibrary.org{doc.get('key', '')}",
                    'published_year': doc.get('first_publish_year'),
                    'isbn': doc.get('isbn', [None])[0] if doc.get('isbn') else None,
                    'pages': doc.get('number_of_pages_median')
                }
                
                books.append(book)
            
            logger.info(f"   ✅ Found {len(books)} books")
            
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
        
        return books


class GoogleBooksScraper:
    """Scraper for Google Books API (free, no auth for basic usage)"""
    
    def __init__(self):
        self.search_url = "https://www.googleapis.com/books/v1/volumes"
    
    def search_books(self, query: str, category: str, limit: int = 20) -> List[Dict]:
        """Search for books on Google Books"""
        logger.info(f"📖 Google Books: Searching '{query}'")
        books = []
        
        try:
            params = {
                'q': query,
                'maxResults': min(limit, 40),
                'langRestrict': 'en',
                'orderBy': 'relevance'
            }
            
            response = requests.get(self.search_url, params=params, headers=HEADERS, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"   Google Books returned {response.status_code}")
                return books
            
            data = response.json()
            
            for item in data.get('items', []):
                vol = item.get('volumeInfo', {})
                title = vol.get('title', '')
                authors = vol.get('authors', ['Unknown'])
                author = ', '.join(authors) if authors else 'Unknown'
                
                if not title:
                    continue
                
                book = {
                    'book_id': generate_book_id(title, author),
                    'title': title,
                    'author': author,
                    'description': vol.get('description', '')[:1000] if vol.get('description') else '',
                    'category': category,
                    'subcategory': query,
                    'avg_rating': vol.get('averageRating'),
                    'ratings_count': vol.get('ratingsCount', 0),
                    'reviews_count': 0,
                    'cover_url': vol.get('imageLinks', {}).get('thumbnail'),
                    'source': 'googlebooks',
                    'source_url': vol.get('infoLink', ''),
                    'published_year': int(vol.get('publishedDate', '0')[:4]) if vol.get('publishedDate') else None,
                    'isbn': next((i.get('identifier') for i in vol.get('industryIdentifiers', []) if i.get('type') == 'ISBN_13'), None),
                    'pages': vol.get('pageCount')
                }
                
                books.append(book)
            
            logger.info(f"   ✅ Found {len(books)} books")
            
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
        
        return books


class RedditScraper:
    """Scraper for Reddit discussions (public JSON API)"""
    
    def __init__(self):
        self.base_url = "https://www.reddit.com"
        self.subreddits = ['books', 'suggestmeabook', 'selfimprovement', 'getdisciplined', 
                          'financialindependence', 'productivity', 'stoicism', 'philosophy']
    
    def search_discussions(self, query: str, category: str, limit: int = 25) -> List[Dict]:
        """Search Reddit for book discussions"""
        logger.info(f"🔴 Reddit: Searching '{query}'")
        discussions = []
        
        for subreddit in self.subreddits[:3]:  # Limit to 3 subreddits per query
            try:
                url = f"{self.base_url}/r/{subreddit}/search.json"
                params = {
                    'q': query,
                    'restrict_sr': 'true',
                    'sort': 'relevance',
                    'limit': limit
                }
                
                response = requests.get(url, params=params, headers={
                    **HEADERS,
                    'User-Agent': 'BookSentimentBot/1.0'
                }, timeout=30)
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                
                for post in data.get('data', {}).get('children', []):
                    p = post.get('data', {})
                    title = (p.get('title') or '').strip()
                    body = (p.get('selftext') or '').strip()
                    combined_text = "\n\n".join(part for part in [title, body] if part)[:2000]
                    
                    discussions.append({
                        'review_id': hashlib.md5(p.get('id', '').encode()).hexdigest()[:16],
                        'source': f'reddit/r/{subreddit}',
                        'community': f'r/{subreddit}',
                        'source_kind': 'reddit',
                        'category': category,
                        'query_term': query,
                        'author': p.get('author', 'anonymous'),
                        'title': title,
                        'content': combined_text,
                        'upvotes': p.get('ups', 0),
                        'url': f"https://reddit.com{p.get('permalink', '')}",
                        'created_at': datetime.fromtimestamp(p.get('created_utc', 0)).isoformat() if p.get('created_utc') else None
                    })
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.debug(f"   Reddit error for r/{subreddit}: {e}")
        
        logger.info(f"   ✅ Found {len(discussions)} discussions")
        return discussions


def scrape_all_sources():
    """Run all scrapers and save to database"""
    print("=" * 60)
    print("📚 BOOK SENTIMENT ANALYSIS - DATA COLLECTION")
    print("=" * 60)
    
    db = Database()
    
    openlibrary = OpenLibraryScraper()
    googlebooks = GoogleBooksScraper()
    reddit = RedditScraper()
    
    all_books = []
    all_discussions = []
    
    for category, queries in CATEGORIES.items():
        print(f"\n📁 Category: {category}")
        print("-" * 40)
        
        for query in queries[:5]:  # Limit queries per category
            # Open Library
            books = openlibrary.search_books(query, category, limit=10)
            all_books.extend(books)
            time.sleep(0.5)
            
            # Google Books
            books = googlebooks.search_books(query, category, limit=10)
            all_books.extend(books)
            time.sleep(0.5)
            
            # Reddit discussions
            discussions = reddit.search_discussions(query, category, limit=10)
            all_discussions.extend(discussions)
            time.sleep(1)
    
    # Deduplicate books
    seen_ids = set()
    unique_books = []
    for book in all_books:
        if book['book_id'] not in seen_ids:
            seen_ids.add(book['book_id'])
            unique_books.append(book)
            db.upsert_book(book)
    
    # Save discussions (will be linked to books later)
    for disc in all_discussions:
        disc['book_id'] = None  # Will be linked during sentiment analysis
        db.upsert_review(disc)
    
    # Save raw data as JSON backup
    with open(RAW_DIR / f"books_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
        json.dump(unique_books, f, indent=2, default=str)
    
    with open(RAW_DIR / f"discussions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
        json.dump(all_discussions, f, indent=2, default=str)
    
    # Print summary
    stats = db.get_stats()
    
    print("\n" + "=" * 60)
    print("📊 SCRAPING SUMMARY")
    print("=" * 60)
    print(f"\n📚 Total Books: {stats['total_books']}")
    print(f"💬 Total Discussions: {stats['total_reviews']}")
    print(f"\n📁 Categories scraped: {len(CATEGORIES)}")
    print(f"🔍 Search queries: {sum(len(q) for q in CATEGORIES.values())}")
    print(f"\n💾 Database: {DB_PATH}")
    print("=" * 60)
    
    return stats


if __name__ == "__main__":
    scrape_all_sources()
