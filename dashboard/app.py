"""
📚 Book Sentiment Intelligence Dashboard

A comprehensive platform for exploring book reviews, sentiment analysis,
and personalized recommendations across Mind, Wealth, Health, Skills,
and Masculinity categories.

Features:
- Search books by title, author, or topic
- View sentiment analysis with word clouds
- Browse by category
- See top positive/negative reviews
- Get book recommendations
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from pathlib import Path
from datetime import datetime
from wordcloud import WordCloud
import matplotlib
matplotlib.use('Agg')  # Required for headless environments
import matplotlib.pyplot as plt
import numpy as np
import os

# Page configuration
st.set_page_config(
    page_title="📚 Book Sentiment Intelligence",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
# Try to find the data directory
current_dir = Path(__file__).parent
root_dir = current_dir.parent
data_dir_candidates = [
    root_dir / "data",              # Local development
    Path("data"),                   # Streamlit Cloud (CWD=root)
    Path("../data"),                # Fallback
    current_dir / "data"            # Fallback
]

DATA_DIR = None
for d in data_dir_candidates:
    if d.exists():
        DATA_DIR = d
        break

if DATA_DIR is None:
    st.error("Could not find data directory. Please check deployment structure.")
    st.stop()

PROCESSED_DIR = DATA_DIR / "processed"

# Custom CSS for futuristic dark theme
st.markdown("""
<style>
    /* Main theme */
    .stApp {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
    }
    
    /* Header styling */
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #00d4ff, #7b2ff7, #f107a3);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 20px 0;
    }
    
    .sub-header {
        color: #888;
        text-align: center;
        font-size: 1.2rem;
        margin-bottom: 30px;
    }
    
    /* Category cards */
    .category-card {
        background: linear-gradient(135deg, rgba(123, 47, 247, 0.2), rgba(0, 212, 255, 0.1));
        border: 1px solid rgba(123, 47, 247, 0.3);
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .category-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(123, 47, 247, 0.3);
    }
    
    /* Metric cards */
    .metric-container {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(123, 47, 247, 0.1));
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #00d4ff, #7b2ff7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-label {
        color: #888;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* Sentiment badges */
    .sentiment-positive {
        background: linear-gradient(90deg, #00c853, #00e676);
        color: black;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
    }
    
    .sentiment-negative {
        background: linear-gradient(90deg, #ff1744, #ff5252);
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
    }
    
    .sentiment-neutral {
        background: linear-gradient(90deg, #ffc107, #ffeb3b);
        color: black;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
    }
    
    /* Book cards */
    .book-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    
    /* Live banner */
    .live-banner {
        background: linear-gradient(90deg, #7b2ff7, #f107a3);
        color: white;
        padding: 10px 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
        font-weight: bold;
    }
    
    /* Search box */
    .stTextInput > div > div > input {
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(123, 47, 247, 0.3);
        border-radius: 10px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data():
    """Load all data from JSON files (no database dependency for Streamlit Cloud)"""
    data = {
        'books': pd.DataFrame(),
        'reviews': pd.DataFrame(),
        'sentiment_results': {},
        'stats': {}
    }
    
    # Load books from JSON
    books_file = PROCESSED_DIR / "books.json"
    if books_file.exists():
        try:
            with open(books_file) as f:
                books_list = json.load(f)
            data['books'] = pd.DataFrame(books_list)
        except Exception as e:
            st.error(f"Error loading books: {e}")
    
    # Load reviews from JSON
    reviews_file = PROCESSED_DIR / "reviews.json"
    if reviews_file.exists():
        try:
            with open(reviews_file) as f:
                reviews_list = json.load(f)
            data['reviews'] = pd.DataFrame(reviews_list)
        except Exception as e:
            st.error(f"Error loading reviews: {e}")
    
    # Load sentiment results
    sentiment_file = PROCESSED_DIR / "sentiment_results.json"
    if sentiment_file.exists():
        try:
            with open(sentiment_file) as f:
                data['sentiment_results'] = json.load(f)
        except Exception as e:
            st.error(f"Error loading sentiment: {e}")
    
    # Calculate stats
    if not data['books'].empty:
        data['stats']['total_books'] = len(data['books'])
        data['stats']['categories'] = data['books']['category'].nunique()
    
    if not data['reviews'].empty:
        data['stats']['total_reviews'] = len(data['reviews'])
        sentiment_cols = data['reviews']['sentiment_score'].dropna()
        data['stats']['avg_sentiment'] = round(sentiment_cols.mean(), 3) if len(sentiment_cols) > 0 else 0
    
    return data


def generate_wordcloud(word_data):
    """Generate word cloud from frequency data"""
    if not word_data:
        return None
    
    word_freq = {item['word']: item['count'] for item in word_data[:100]}
    
    wc = WordCloud(
        width=800,
        height=400,
        background_color='#0a0a0a',
        colormap='viridis',
        max_words=100,
        prefer_horizontal=0.7
    ).generate_from_frequencies(word_freq)
    
    return wc


def sentiment_color(score):
    """Get color based on sentiment score"""
    if score >= 0.2:
        return '#00e676'  # Green
    elif score <= -0.2:
        return '#ff5252'  # Red
    else:
        return '#ffc107'  # Yellow


def main():
    """Main dashboard"""
    
    # Header
    st.markdown('<p class="main-header">📚 Book Sentiment Intelligence</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Discover what readers really think • Mind • Wealth • Health • Skills</p>', unsafe_allow_html=True)
    
    # Load data
    data = load_data()
    
    if not data['books'].empty:
        st.markdown("""
        <div class="live-banner">
            🔴 LIVE DATA • Analyzing thousands of book reviews from Reddit, Goodreads & more
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ No data available. Run the scraper first:")
        st.code("""
cd scripts
python scrape_books.py
python analyze_sentiment.py
        """)
        return
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/nolan/96/books.png", width=80)
        st.header("🔍 Navigation")
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # Category filter
        categories = ['All'] + sorted(data['books']['category'].dropna().unique().tolist())
        selected_category = st.selectbox("📁 Category", categories)
        
        # Search
        search_query = st.text_input("🔍 Search books", placeholder="forex, stoicism, habits...")
        
        # Sentiment filter
        sentiment_filter = st.radio(
            "💭 Sentiment Filter",
            ['All', 'Positive', 'Neutral', 'Negative']
        )
        
        st.markdown("---")
        st.markdown("### 📊 About")
        st.info("""
        This dashboard analyzes sentiment from book reviews across:
        - 📖 Open Library
        - 📚 Google Books
        - 🔴 Reddit discussions
        """)
    
    # Key Metrics
    st.markdown("## 📈 Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📚 Books Tracked",
            value=f"{data['stats'].get('total_books', 0):,}"
        )
    
    with col2:
        st.metric(
            label="💬 Reviews Analyzed",
            value=f"{data['stats'].get('total_reviews', 0):,}"
        )
    
    with col3:
        avg_sent = data['stats'].get('avg_sentiment', 0)
        st.metric(
            label="😊 Avg Sentiment",
            value=f"{avg_sent:.2f}",
            delta="Positive" if avg_sent > 0 else "Negative"
        )
    
    with col4:
        st.metric(
            label="📁 Categories",
            value=data['stats'].get('categories', 0)
        )
    
    st.markdown("---")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", "📚 Books", "💬 Reviews", "☁️ Word Cloud", "🔍 Search"
    ])
    
    # Tab 1: Dashboard
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Sentiment Distribution")
            
            if 'sentiment_results' in data and data['sentiment_results']:
                dist = data['sentiment_results'].get('sentiment_distribution', {})
                
                fig = go.Figure(data=[go.Pie(
                    labels=['Positive', 'Neutral', 'Negative'],
                    values=[dist.get('positive', 0), dist.get('neutral', 0), dist.get('negative', 0)],
                    hole=0.4,
                    marker=dict(colors=['#00e676', '#ffc107', '#ff5252'])
                )])
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 📁 Books by Category")
            
            if not data['books'].empty:
                cat_counts = data['books']['category'].value_counts()
                
                fig = px.bar(
                    x=cat_counts.values,
                    y=cat_counts.index,
                    orientation='h',
                    color=cat_counts.values,
                    color_continuous_scale='viridis'
                )
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    showlegend=False,
                    height=350,
                    xaxis_title="Count",
                    yaxis_title=""
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Top Reviews
        st.markdown("### ⭐ Top Positive Reviews")
        
        if 'sentiment_results' in data and data['sentiment_results']:
            top_positive = data['sentiment_results'].get('top_positive_reviews', [])[:5]
            
            for review in top_positive:
                with st.container():
                    st.markdown(f"""
                    <div class="book-card">
                        <span class="sentiment-positive">😊 Score: {review.get('score', 0):.2f}</span>
                        <p style="margin-top: 10px; color: #ccc;">{review.get('content', '')[:300]}...</p>
                        <small style="color: #666;">Source: {review.get('source', 'Unknown')}</small>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Tab 2: Books
    with tab2:
        st.markdown("### 📚 Book Library")
        
        books_df = data['books'].copy()
        
        # Apply filters
        if selected_category != 'All':
            books_df = books_df[books_df['category'] == selected_category]
        
        if search_query:
            mask = (
                books_df['title'].str.lower().str.contains(search_query.lower(), na=False) |
                books_df['author'].str.lower().str.contains(search_query.lower(), na=False) |
                books_df['description'].str.lower().str.contains(search_query.lower(), na=False)
            )
            books_df = books_df[mask]
        
        # Display books
        if not books_df.empty:
            for idx, book in books_df.head(20).iterrows():
                col1, col2 = st.columns([1, 4])
                
                with col1:
                    if book.get('cover_url'):
                        st.image(book['cover_url'], width=100)
                    else:
                        st.markdown("📖")
                
                with col2:
                    st.markdown(f"**{book['title']}**")
                    st.markdown(f"*by {book.get('author', 'Unknown')}*")
                    
                    rating = book.get('avg_rating')
                    if rating:
                        st.markdown(f"⭐ {rating:.1f} ({book.get('ratings_count', 0):,} ratings)")
                    
                    st.markdown(f"📁 {book.get('category', 'Uncategorized')}")
                    
                    if book.get('description'):
                        with st.expander("Description"):
                            st.write(book['description'][:500])
                
                st.markdown("---")
        else:
            st.info("No books found matching your criteria.")
    
    # Tab 3: Reviews
    with tab3:
        st.markdown("### 💬 Review Analysis")
        
        reviews_df = data['reviews'].copy()
        
        # Apply sentiment filter
        if sentiment_filter == 'Positive':
            reviews_df = reviews_df[reviews_df['sentiment_score'] >= 0.2]
        elif sentiment_filter == 'Negative':
            reviews_df = reviews_df[reviews_df['sentiment_score'] <= -0.2]
        elif sentiment_filter == 'Neutral':
            reviews_df = reviews_df[(reviews_df['sentiment_score'] > -0.2) & (reviews_df['sentiment_score'] < 0.2)]
        
        if not reviews_df.empty:
            for idx, review in reviews_df.head(20).iterrows():
                score = review.get('sentiment_score', 0)
                color = sentiment_color(score)
                label = review.get('sentiment_label', 'neutral')
                
                st.markdown(f"""
                <div class="book-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: {color}; font-weight: bold;">
                            {'😊' if label == 'positive' else '😐' if label == 'neutral' else '😞'} 
                            Sentiment: {score:.2f}
                        </span>
                        <small style="color: #666;">{review.get('source', 'Unknown')}</small>
                    </div>
                    <p style="margin-top: 10px; color: #ccc;">
                        {str(review.get('content', ''))[:400]}...
                    </p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No reviews found.")
    
    # Tab 4: Word Cloud
    with tab4:
        st.markdown("### ☁️ Word Cloud")
        
        if 'sentiment_results' in data and data['sentiment_results']:
            wc_data = data['sentiment_results'].get('word_cloud_data', [])
            
            if wc_data:
                wc = generate_wordcloud(wc_data)
                
                if wc:
                    fig, ax = plt.subplots(figsize=(12, 6))
                    ax.imshow(wc, interpolation='bilinear')
                    ax.axis('off')
                    fig.patch.set_facecolor('#0a0a0a')
                    st.pyplot(fig)
                
                # Top words table
                st.markdown("### 📊 Top Keywords")
                
                top_words = pd.DataFrame(wc_data[:30])
                top_words.columns = ['Word', 'Count']
                
                fig = px.bar(
                    top_words.head(20),
                    x='Count',
                    y='Word',
                    orientation='h',
                    color='Count',
                    color_continuous_scale='viridis'
                )
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run sentiment analysis to generate word cloud.")
    
    # Tab 5: Search
    with tab5:
        st.markdown("### 🔍 Advanced Search")
        
        search_term = st.text_input("Search for books on any topic", key="advanced_search", placeholder="e.g., forex trading, stoic philosophy, weight loss")
        
        if search_term:
            books_df = data['books'].copy()
            reviews_df = data['reviews'].copy()
            
            # Search books
            book_mask = (
                books_df['title'].str.lower().str.contains(search_term.lower(), na=False) |
                books_df['author'].str.lower().str.contains(search_term.lower(), na=False) |
                books_df['description'].str.lower().str.contains(search_term.lower(), na=False) |
                books_df['subcategory'].str.lower().str.contains(search_term.lower(), na=False)
            )
            matching_books = books_df[book_mask]
            
            # Search reviews
            review_mask = reviews_df['content'].str.lower().str.contains(search_term.lower(), na=False)
            matching_reviews = reviews_df[review_mask]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"### 📚 Books ({len(matching_books)})")
                for idx, book in matching_books.head(10).iterrows():
                    st.markdown(f"""
                    **{book['title']}** by {book.get('author', 'Unknown')}  
                    ⭐ {book.get('avg_rating', 'N/A')} | 📁 {book.get('category', 'Unknown')}
                    """)
            
            with col2:
                st.markdown(f"### 💬 Discussions ({len(matching_reviews)})")
                for idx, review in matching_reviews.head(10).iterrows():
                    score = review.get('sentiment_score', 0)
                    emoji = '😊' if score > 0.2 else '😐' if score > -0.2 else '😞'
                    st.markdown(f"""
                    {emoji} **{score:.2f}** | {review.get('source', 'Unknown')}  
                    {str(review.get('content', ''))[:150]}...
                    """)
    
    # Footer
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🔗 Data Sources")
        st.markdown("""
        - Open Library API
        - Google Books API
        - Reddit Discussions
        """)
    
    with col2:
        st.markdown("### 📧 Contact")
        st.markdown("""
        **Nicodemus Werre Amollo**  
        📧 nichodemuswerre@gmail.com
        """)
    
    with col3:
        st.markdown("### 🛠️ Tech Stack")
        st.markdown("""
        - Python + Streamlit
        - SQLite + Pandas
        - VADER Sentiment
        """)
    
    st.markdown(
        "<center style='color: #666;'>Built with ❤️ by Nicodemus Werre | Kenya 🇰🇪</center>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
