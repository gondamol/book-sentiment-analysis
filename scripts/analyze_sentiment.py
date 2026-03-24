#!/usr/bin/env python3
"""
Sentiment Analysis Pipeline

Performs sentiment analysis on book reviews and discussions using:
1. VADER (Valence Aware Dictionary and Sentiment Reasoner)
2. TextBlob (for comparison)
3. Custom book-specific sentiment rules

Also generates:
- Word frequencies for word clouds
- Sentiment trends by category
- Top positive/negative reviews
"""
import json
import sqlite3
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set

# Sentiment analysis
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "books.db"
PROCESSED_DIR = DATA_DIR / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Stopwords for word cloud
STOPWORDS = set([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'this',
    'that', 'these', 'those', 'it', 'its', "it's", 'they', 'them', 'their',
    'i', 'me', 'my', 'we', 'us', 'our', 'you', 'your', 'he', 'him', 'his',
    'she', 'her', 'not', 'no', 'so', 'as', 'if', 'when', 'what', 'which',
    'who', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most',
    'other', 'some', 'such', 'only', 'own', 'same', 'than', 'too', 'very',
    'just', 'also', 'now', 'here', 'there', 'where', 'why', 'how', 'about',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up',
    'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once',
    'book', 'read', 'reading', 'books', 'really', 'like', 'one', 'get', 'got',
    'think', 'know', 'even', 'still', 'well', 'back', 'way', 'much', 'many'
])


class SentimentAnalyzer:
    """Multi-method sentiment analyzer"""
    
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer() if VADER_AVAILABLE else None
        
        # Book-specific positive words
        self.positive_words = {
            'life-changing', 'transformative', 'insightful', 'brilliant',
            'must-read', 'masterpiece', 'enlightening', 'inspiring',
            'practical', 'actionable', 'profound', 'excellent', 'amazing',
            'recommend', 'helpful', 'valuable', 'essential', 'powerful',
            'eye-opening', 'game-changer', 'motivating', 'clear', 'concise'
        }
        
        # Book-specific negative words
        self.negative_words = {
            'boring', 'repetitive', 'overrated', 'waste', 'disappointing',
            'shallow', 'outdated', 'confusing', 'poorly', 'tedious',
            'preachy', 'pretentious', 'useless', 'skip', 'avoid',
            'dry', 'rambling', 'simplistic', 'mediocre', 'misleading'
        }
    
    def analyze(self, text: str) -> Dict:
        """Analyze sentiment of text"""
        if not text or len(text.strip()) < 10:
            return {
                'score': 0,
                'label': 'neutral',
                'positive': 0,
                'negative': 0,
                'compound': 0
            }
        
        # VADER analysis
        if self.vader:
            scores = self.vader.polarity_scores(text)
            compound = scores['compound']
        else:
            compound = 0
        
        # TextBlob analysis
        if TEXTBLOB_AVAILABLE:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
        else:
            polarity = 0
        
        # Custom word-based adjustment
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        pos_matches = len(words & self.positive_words)
        neg_matches = len(words & self.negative_words)
        
        custom_score = (pos_matches - neg_matches) * 0.1
        
        # Combined score (weighted average)
        if self.vader and TEXTBLOB_AVAILABLE:
            final_score = (compound * 0.5) + (polarity * 0.3) + (custom_score * 0.2)
        elif self.vader:
            final_score = (compound * 0.7) + (custom_score * 0.3)
        elif TEXTBLOB_AVAILABLE:
            final_score = (polarity * 0.7) + (custom_score * 0.3)
        else:
            final_score = custom_score
        
        # Determine label
        if final_score >= 0.2:
            label = 'positive'
        elif final_score <= -0.2:
            label = 'negative'
        else:
            label = 'neutral'
        
        return {
            'score': round(final_score, 3),
            'label': label,
            'positive': round(max(0, final_score), 3),
            'negative': round(abs(min(0, final_score)), 3),
            'compound': round(compound, 3) if self.vader else 0
        }


def extract_keywords(texts: List[str], top_n: int = 100) -> List[Tuple[str, int]]:
    """Extract top keywords for word cloud"""
    word_counts = Counter()
    
    for text in texts:
        if not text:
            continue
        
        # Clean and tokenize
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter stopwords
        words = [w for w in words if w not in STOPWORDS]
        
        word_counts.update(words)
    
    return word_counts.most_common(top_n)


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> Set[str]:
    """Return the available columns for a SQLite table."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def export_dashboard_snapshots(conn: sqlite3.Connection) -> None:
    """Export database tables to JSON files used by the dashboard."""
    conn.row_factory = sqlite3.Row
    review_columns = get_table_columns(conn, "reviews")

    def review_select(column: str, alias: Optional[str] = None) -> str:
        alias = alias or column
        return f"r.{column} AS {alias}" if column in review_columns else f"NULL AS {alias}"

    books_rows = conn.execute('''
        SELECT *
        FROM books
        ORDER BY COALESCE(ratings_count, 0) DESC, title ASC
    ''').fetchall()

    reviews_rows = conn.execute('''
        SELECT
            r.review_id,
            r.book_id,
            r.source,
            {community},
            {source_kind},
            {category},
            {query_term},
            {title},
            {url},
            r.author,
            r.content,
            r.rating,
            r.upvotes,
            r.sentiment_score,
            r.sentiment_label,
            r.created_at,
            r.scraped_at,
            b.category AS category,
            b.title AS linked_book_title
        FROM reviews r
        LEFT JOIN books b ON r.book_id = b.book_id
        ORDER BY COALESCE(r.created_at, r.scraped_at) DESC
    '''.format(
        community=review_select("community"),
        source_kind=review_select("source_kind"),
        category=review_select("category"),
        query_term=review_select("query_term"),
        title=review_select("title"),
        url=review_select("url"),
    )).fetchall()

    with open(PROCESSED_DIR / "books.json", 'w') as f:
        json.dump([dict(row) for row in books_rows], f, indent=2, default=str)

    with open(PROCESSED_DIR / "reviews.json", 'w') as f:
        json.dump([dict(row) for row in reviews_rows], f, indent=2, default=str)


def process_sentiment():
    """Main sentiment processing pipeline"""
    print("=" * 60)
    print("🧠 SENTIMENT ANALYSIS PIPELINE")
    print("=" * 60)
    
    if not DB_PATH.exists():
        print("❌ Database not found. Run scrape_books.py first.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    review_columns = get_table_columns(conn, "reviews")
    review_category_expr = "COALESCE(r.category, b.category)" if "category" in review_columns else "b.category"
    review_title_expr = "COALESCE(r.title, b.title)" if "title" in review_columns else "b.title"
    
    analyzer = SentimentAnalyzer()
    
    # Analyze reviews
    print("\n📝 Analyzing reviews...")
    cursor.execute("SELECT review_id, content, author FROM reviews")
    reviews = cursor.fetchall()
    
    sentiment_results = []
    all_texts = []
    
    for review_id, content, author in reviews:
        text = f"{content or ''}".strip()
        if not text:
            continue
        
        all_texts.append(text)
        result = analyzer.analyze(text)
        
        # Update database
        cursor.execute('''
            UPDATE reviews 
            SET sentiment_score = ?, sentiment_label = ?
            WHERE review_id = ?
        ''', (result['score'], result['label'], review_id))
        
        sentiment_results.append({
            'review_id': review_id,
            **result
        })
    
    conn.commit()
    
    # Calculate category-level sentiment
    print("\n📊 Calculating category sentiments...")
    
    cursor.execute(f'''
        SELECT {review_category_expr} as category, AVG(r.sentiment_score) as avg_sentiment, COUNT(*) as count
        FROM reviews r
        LEFT JOIN books b ON r.book_id = b.book_id
        WHERE r.sentiment_score IS NOT NULL
        GROUP BY {review_category_expr}
    ''')
    
    category_sentiments = {}
    for row in cursor.fetchall():
        if row[0]:
            category_sentiments[row[0]] = {
                'avg_sentiment': round(row[1], 3),
                'review_count': row[2]
            }
    
    # Get top positive and negative reviews
    print("\n⭐ Finding top reviews...")
    
    cursor.execute(f'''
        SELECT r.content, r.sentiment_score, r.source, {review_title_expr}
        FROM reviews r
        LEFT JOIN books b ON r.book_id = b.book_id
        WHERE r.sentiment_score IS NOT NULL
        ORDER BY r.sentiment_score DESC
        LIMIT 20
    ''')
    top_positive = [{'content': r[0][:500], 'score': r[1], 'source': r[2], 'book': r[3]} for r in cursor.fetchall()]
    
    cursor.execute(f'''
        SELECT r.content, r.sentiment_score, r.source, {review_title_expr}
        FROM reviews r
        LEFT JOIN books b ON r.book_id = b.book_id
        WHERE r.sentiment_score IS NOT NULL
        ORDER BY r.sentiment_score ASC
        LIMIT 20
    ''')
    top_negative = [{'content': r[0][:500], 'score': r[1], 'source': r[2], 'book': r[3]} for r in cursor.fetchall()]
    
    # Extract keywords for word cloud
    print("\n☁️ Generating word cloud data...")
    keywords = extract_keywords(all_texts, top_n=200)
    
    # Calculate overall stats
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE sentiment_label = 'positive'")
    positive_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE sentiment_label = 'negative'")
    negative_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE sentiment_label = 'neutral'")
    neutral_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(sentiment_score) FROM reviews WHERE sentiment_score IS NOT NULL")
    overall_sentiment = cursor.fetchone()[0] or 0

    print("\n💾 Exporting dashboard snapshots...")
    export_dashboard_snapshots(conn)
    
    conn.close()
    
    # Save processed results
    results = {
        'generated_at': datetime.now().isoformat(),
        'total_reviews_analyzed': len(sentiment_results),
        'overall_sentiment': round(overall_sentiment, 3),
        'sentiment_distribution': {
            'positive': positive_count,
            'negative': negative_count,
            'neutral': neutral_count
        },
        'category_sentiments': category_sentiments,
        'top_positive_reviews': top_positive,
        'top_negative_reviews': top_negative,
        'word_cloud_data': [{'word': w, 'count': c} for w, c in keywords]
    }
    
    with open(PROCESSED_DIR / "sentiment_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 SENTIMENT ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"\n📝 Reviews analyzed: {len(sentiment_results)}")
    print(f"😊 Positive: {positive_count}")
    print(f"😐 Neutral: {neutral_count}")
    print(f"😞 Negative: {negative_count}")
    print(f"\n📈 Overall Sentiment Score: {overall_sentiment:.3f}")
    print(f"\n💾 Results saved to: {PROCESSED_DIR / 'sentiment_results.json'}")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    process_sentiment()
