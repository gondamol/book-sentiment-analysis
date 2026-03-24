"""
Book Sentiment Intelligence dashboard.

This Streamlit app helps readers explore book catalog data alongside public
discussion sentiment, making it easier to discover promising titles,
understand what readers value, and browse themes across categories.
"""
from __future__ import annotations

import html
import json
import re
import sqlite3
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from wordcloud import WordCloud

matplotlib.use("Agg")
import matplotlib.pyplot as plt


st.set_page_config(
    page_title="Book Sentiment Intelligence",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


COLORS = {
    "bg": "#06131f",
    "panel": "rgba(9, 25, 39, 0.88)",
    "panel_soft": "rgba(13, 36, 54, 0.72)",
    "border": "rgba(117, 150, 171, 0.28)",
    "text": "#eef3f7",
    "muted": "#9fb1bf",
    "teal": "#32c7b5",
    "gold": "#f4b860",
    "coral": "#ff7b72",
    "slate": "#6f8798",
}

SENTIMENT_COLORS = {
    "positive": COLORS["teal"],
    "neutral": COLORS["gold"],
    "negative": COLORS["coral"],
}

TOPIC_KEYWORDS = {
    "Mind": [
        "mindset",
        "psychology",
        "stoicism",
        "philosophy",
        "discipline",
        "cognitive",
        "purpose",
        "meaning",
        "spiritual",
        "mental model",
    ],
    "Wealth": [
        "finance",
        "investing",
        "wealth",
        "money",
        "stock",
        "market",
        "business",
        "economics",
        "financial independence",
        "trading",
    ],
    "Health": [
        "health",
        "fitness",
        "nutrition",
        "diet",
        "exercise",
        "sleep",
        "mental health",
        "longevity",
        "fasting",
        "wellness",
    ],
    "Skills": [
        "productivity",
        "leadership",
        "communication",
        "habits",
        "focus",
        "negotiation",
        "writing",
        "career",
        "learning",
        "public speaking",
    ],
    "Masculinity": [
        "masculinity",
        "confidence",
        "relationships",
        "dating",
        "men",
        "male",
        "self reliance",
        "status",
        "identity",
        "attraction",
    ],
}

TOKEN_STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "been",
    "being",
    "between",
    "book",
    "books",
    "could",
    "does",
    "from",
    "have",
    "just",
    "like",
    "make",
    "more",
    "much",
    "need",
    "other",
    "people",
    "read",
    "reading",
    "really",
    "some",
    "that",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "want",
    "what",
    "when",
    "which",
    "with",
    "would",
    "your",
}


current_dir = Path(__file__).parent
root_dir = current_dir.parent
data_dir_candidates = [
    root_dir / "data",
    Path("data"),
    Path("../data"),
    current_dir / "data",
]

DATA_DIR = next((path for path in data_dir_candidates if path.exists()), None)
if DATA_DIR is None:
    st.error("Could not locate the `data/` directory.")
    st.stop()

PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "books.db"


st.markdown(
    f"""
<style>
    .stApp {{
        background:
            radial-gradient(circle at top left, rgba(50, 199, 181, 0.16), transparent 34%),
            radial-gradient(circle at top right, rgba(244, 184, 96, 0.18), transparent 28%),
            linear-gradient(180deg, #081725 0%, #06131f 54%, #071c2a 100%);
        color: {COLORS["text"]};
    }}

    [data-testid="stSidebar"] {{
        background:
            linear-gradient(180deg, rgba(8, 22, 34, 0.97), rgba(10, 28, 42, 0.97));
        border-right: 1px solid {COLORS["border"]};
    }}

    .hero-shell {{
        padding: 1.6rem 1.75rem;
        border-radius: 26px;
        background:
            linear-gradient(135deg, rgba(11, 31, 49, 0.92), rgba(8, 21, 34, 0.94));
        border: 1px solid {COLORS["border"]};
        box-shadow: 0 18px 60px rgba(0, 0, 0, 0.22);
        margin-bottom: 1rem;
    }}

    .eyebrow {{
        display: inline-block;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        background: rgba(50, 199, 181, 0.14);
        color: {COLORS["teal"]};
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 700;
    }}

    .hero-title {{
        font-family: "Georgia", "Times New Roman", serif;
        color: {COLORS["text"]};
        font-size: 3rem;
        line-height: 1.05;
        font-weight: 700;
        margin: 0.8rem 0 0.6rem 0;
    }}

    .hero-copy {{
        color: {COLORS["muted"]};
        font-size: 1.05rem;
        max-width: 60rem;
        line-height: 1.65;
    }}

    .hero-meta {{
        margin-top: 1rem;
        color: {COLORS["text"]};
        font-size: 0.92rem;
    }}

    .filter-pill {{
        display: inline-block;
        padding: 0.38rem 0.72rem;
        border-radius: 999px;
        background: rgba(15, 40, 60, 0.9);
        border: 1px solid {COLORS["border"]};
        color: {COLORS["text"]};
        margin: 0.25rem 0.35rem 0 0;
        font-size: 0.82rem;
    }}

    .signal-card {{
        background: {COLORS["panel"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 20px;
        padding: 1rem 1.05rem;
        min-height: 150px;
    }}

    .signal-card h4 {{
        margin: 0 0 0.4rem 0;
        color: {COLORS["text"]};
        font-size: 1rem;
    }}

    .signal-kicker {{
        color: {COLORS["gold"]};
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.72rem;
        font-weight: 700;
    }}

    .signal-value {{
        color: {COLORS["text"]};
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0.45rem 0;
    }}

    .signal-copy {{
        color: {COLORS["muted"]};
        font-size: 0.92rem;
        line-height: 1.5;
    }}

    div[data-testid="stMetric"] {{
        background: {COLORS["panel"]};
        border: 1px solid {COLORS["border"]};
        padding: 1rem 1rem 0.85rem 1rem;
        border-radius: 18px;
    }}

    div[data-testid="stMetricLabel"] {{
        color: {COLORS["muted"]};
    }}

    div[data-testid="stMetricValue"] {{
        color: {COLORS["text"]};
    }}

    div[data-testid="stMetricDelta"] > div {{
        color: {COLORS["teal"]};
    }}

    .snippet-card {{
        background: {COLORS["panel_soft"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 18px;
        padding: 0.95rem 1rem;
        margin-bottom: 0.8rem;
    }}

    .snippet-header {{
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 0.55rem;
        color: {COLORS["muted"]};
        font-size: 0.84rem;
    }}

    .snippet-score {{
        font-weight: 700;
    }}

    .snippet-body {{
        color: {COLORS["text"]};
        line-height: 1.55;
        font-size: 0.95rem;
    }}

    .book-card {{
        background: {COLORS["panel_soft"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 18px;
        padding: 1rem;
        margin-bottom: 0.85rem;
    }}

    .book-title {{
        color: {COLORS["text"]};
        font-weight: 700;
        font-size: 1.05rem;
        margin-bottom: 0.15rem;
    }}

    .book-meta {{
        color: {COLORS["muted"]};
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
    }}

    .small-note {{
        color: {COLORS["muted"]};
        font-size: 0.85rem;
    }}

    .section-title {{
        font-family: "Georgia", "Times New Roman", serif;
        color: {COLORS["text"]};
        margin-bottom: 0.25rem;
    }}
</style>
""",
    unsafe_allow_html=True,
)


def safe_json_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        with open(path) as file_handle:
            payload = json.load(file_handle)
        if isinstance(payload, list):
            return pd.DataFrame(payload)
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def safe_json_dict(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        with open(path) as file_handle:
            payload = json.load(file_handle)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def load_table_from_db(table_name: str) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as connection:
            return pd.read_sql_query(f"SELECT * FROM {table_name}", connection)
    except Exception:
        return pd.DataFrame()


def parse_community(source: str) -> str:
    if not source:
        return "Unknown"
    if "reddit/r/" in source:
        return f"r/{source.split('reddit/r/', 1)[1]}"
    return source.replace("_", " ").title()


def sentiment_bucket(score: float) -> str:
    if pd.isna(score):
        return "unknown"
    if score >= 0.2:
        return "positive"
    if score <= -0.2:
        return "negative"
    return "neutral"


def infer_topic_category(text: str) -> str:
    lowered = (text or "").lower()
    if not lowered.strip():
        return "Unmapped"

    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        hits = 0
        for keyword in keywords:
            if keyword in lowered:
                hits += 1
        if hits:
            scores[topic] = hits

    if not scores:
        return "Unmapped"
    return max(scores, key=scores.get)


def tokenize_terms(text: str) -> List[str]:
    tokens = re.findall(r"\b[a-z]{4,}\b", (text or "").lower())
    return [token for token in tokens if token not in TOKEN_STOPWORDS]


def build_search_mask(frame: pd.DataFrame, columns: Sequence[str], query: str) -> pd.Series:
    if frame.empty or not query.strip():
        return pd.Series(True, index=frame.index)

    terms = re.findall(r"[a-z0-9]+", query.lower())
    if not terms:
        return pd.Series(True, index=frame.index)

    blob = frame[list(columns)].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    mask = pd.Series(True, index=frame.index)
    for term in terms:
        mask &= blob.str.contains(re.escape(term), regex=True, na=False)
    return mask


def style_figure(figure: go.Figure, height: int | None = None) -> go.Figure:
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text"]),
        legend_title_text="",
        margin=dict(l=18, r=18, t=40, b=18),
        hoverlabel=dict(bgcolor="#082030", font_color=COLORS["text"]),
    )
    figure.update_xaxes(gridcolor="rgba(159, 177, 191, 0.14)", zerolinecolor="rgba(159, 177, 191, 0.18)")
    figure.update_yaxes(gridcolor="rgba(159, 177, 191, 0.14)", zerolinecolor="rgba(159, 177, 191, 0.18)")
    if height is not None:
        figure.update_layout(height=height)
    return figure


def generate_wordcloud(texts: Sequence[str]) -> WordCloud | None:
    frequencies = Counter()
    for text in texts:
        frequencies.update(tokenize_terms(text))

    if not frequencies:
        return None

    return WordCloud(
        width=1200,
        height=620,
        background_color=COLORS["bg"],
        colormap="cividis",
        max_words=80,
        prefer_horizontal=0.72,
    ).generate_from_frequencies(dict(frequencies.most_common(120)))


def prepare_books_frame(frame: pd.DataFrame) -> pd.DataFrame:
    expected = [
        "book_id",
        "title",
        "author",
        "description",
        "category",
        "subcategory",
        "avg_rating",
        "ratings_count",
        "published_year",
        "cover_url",
        "source",
    ]
    if frame.empty:
        return pd.DataFrame(columns=expected)

    books = frame.copy()
    for column in expected:
        if column not in books.columns:
            books[column] = ""

    for column in ["title", "author", "description", "category", "subcategory", "source", "cover_url"]:
        books[column] = books[column].fillna("").astype(str)

    books["avg_rating"] = pd.to_numeric(books["avg_rating"], errors="coerce")
    books["ratings_count"] = pd.to_numeric(books["ratings_count"], errors="coerce").fillna(0)
    books["published_year"] = pd.to_numeric(books["published_year"], errors="coerce")
    books["category"] = books["category"].replace("", "Unmapped")
    books["search_blob"] = books[["title", "author", "description", "subcategory"]].agg(" ".join, axis=1).str.lower()
    books = books.drop_duplicates(subset=["book_id", "title", "author"], keep="first")
    books = books.sort_values(["ratings_count", "avg_rating", "title"], ascending=[False, False, True])
    return books


def prepare_reviews_frame(frame: pd.DataFrame) -> pd.DataFrame:
    expected = [
        "review_id",
        "source",
        "community",
        "source_kind",
        "query_term",
        "author",
        "content",
        "title",
        "linked_book_title",
        "url",
        "sentiment_score",
        "sentiment_label",
        "created_at",
        "upvotes",
        "category",
    ]
    if frame.empty:
        return pd.DataFrame(columns=expected)

    reviews = frame.copy()
    for column in expected:
        if column not in reviews.columns:
            reviews[column] = np.nan if column == "sentiment_score" else ""

    for column in [
        "source",
        "community",
        "source_kind",
        "query_term",
        "author",
        "content",
        "title",
        "linked_book_title",
        "url",
        "sentiment_label",
        "category",
    ]:
        reviews[column] = reviews[column].fillna("").astype(str)

    reviews["sentiment_score"] = pd.to_numeric(reviews["sentiment_score"], errors="coerce")
    reviews["upvotes"] = pd.to_numeric(reviews["upvotes"], errors="coerce").fillna(0)
    parsed_dates = pd.to_datetime(reviews["created_at"], errors="coerce", utc=True)
    reviews["created_date"] = parsed_dates.dt.tz_convert(None)
    reviews["community"] = reviews["community"].where(
        reviews["community"].str.strip() != "",
        reviews["source"].apply(parse_community),
    )
    reviews["source_type"] = reviews["source_kind"].where(
        reviews["source_kind"].str.strip() != "",
        reviews["source"].apply(lambda value: "reddit" if "reddit/r/" in value else value.lower()),
    ).str.replace("_", " ").str.title()
    reviews["title"] = reviews["title"].where(reviews["title"].str.strip() != "", reviews["linked_book_title"])
    reviews["text_length"] = reviews["content"].str.len()
    reviews["sentiment_bucket"] = reviews["sentiment_score"].apply(sentiment_bucket)
    reviews["topic_category"] = reviews["category"].where(reviews["category"].str.strip() != "", reviews["content"].apply(infer_topic_category))
    reviews["topic_category"] = reviews["topic_category"].replace("", "Unmapped").fillna("Unmapped")
    reviews["query_term"] = reviews["query_term"].where(
        reviews["query_term"].str.strip() != "",
        reviews["topic_category"],
    )
    reviews["search_blob"] = reviews[
        ["title", "linked_book_title", "query_term", "content", "author", "community", "topic_category"]
    ].agg(" ".join, axis=1).str.lower()
    reviews = reviews.drop_duplicates(subset=["review_id"], keep="first")
    reviews = reviews.sort_values(["created_date", "sentiment_score"], ascending=[False, False], na_position="last")
    return reviews


@st.cache_data(ttl=300)
def load_data() -> Dict[str, object]:
    books = load_table_from_db("books")
    reviews = load_table_from_db("reviews")

    if books.empty:
        books = safe_json_frame(PROCESSED_DIR / "books.json")
    if reviews.empty:
        reviews = safe_json_frame(PROCESSED_DIR / "reviews.json")

    books = prepare_books_frame(books)
    reviews = prepare_reviews_frame(reviews)
    sentiment_results = safe_json_dict(PROCESSED_DIR / "sentiment_results.json")

    stats = {
        "total_books": int(len(books)),
        "total_reviews": int(len(reviews)),
        "avg_sentiment": round(float(reviews["sentiment_score"].dropna().mean()), 3) if not reviews.empty else 0.0,
        "communities": int(reviews["community"].nunique()) if not reviews.empty else 0,
        "topic_categories": int(books["category"].replace("", np.nan).dropna().nunique()) if not books.empty else 0,
    }

    if not reviews.empty and reviews["created_date"].notna().any():
        stats["min_date"] = reviews["created_date"].min().date()
        stats["max_date"] = reviews["created_date"].max().date()
    else:
        stats["min_date"] = None
        stats["max_date"] = None

    return {
        "books": books,
        "reviews": reviews,
        "sentiment_results": sentiment_results,
        "stats": stats,
    }


def apply_book_filters(books: pd.DataFrame, query: str, categories: Sequence[str]) -> pd.DataFrame:
    filtered = books.copy()
    if categories:
        filtered = filtered[filtered["category"].isin(categories)]
    if query.strip():
        filtered = filtered[build_search_mask(filtered, ["title", "author", "description", "subcategory"], query)]
    return filtered


def apply_review_filters(
    reviews: pd.DataFrame,
    query: str,
    categories: Sequence[str],
    communities: Sequence[str],
    sentiments: Sequence[str],
    date_window: Tuple[pd.Timestamp, pd.Timestamp] | None,
    min_length: int,
) -> pd.DataFrame:
    filtered = reviews.copy()

    if categories:
        filtered = filtered[filtered["topic_category"].isin(categories)]
    if communities:
        filtered = filtered[filtered["community"].isin(communities)]
    if sentiments:
        filtered = filtered[filtered["sentiment_bucket"].isin(sentiments)]
    if date_window is not None:
        start_date, end_date = date_window
        filtered = filtered[
            filtered["created_date"].notna()
            & (filtered["created_date"] >= start_date)
            & (filtered["created_date"] <= end_date)
        ]
    if min_length > 0:
        filtered = filtered[filtered["text_length"] >= min_length]
    if query.strip():
        filtered = filtered[
            build_search_mask(
                filtered,
                ["title", "linked_book_title", "query_term", "content", "author", "community", "topic_category"],
                query,
            )
        ]
    return filtered


def compute_sentiment_delta(reviews: pd.DataFrame) -> Tuple[float | None, int | None]:
    dated = reviews.dropna(subset=["created_date", "sentiment_score"]).copy()
    if dated.empty or len(dated) < 10:
        return None, None

    span_days = max(int((dated["created_date"].max() - dated["created_date"].min()).days), 1)
    window_days = 30 if span_days < 120 else 90 if span_days < 540 else 180

    recent_end = dated["created_date"].max().normalize()
    recent_start = recent_end - pd.Timedelta(days=window_days - 1)
    prior_end = recent_start - pd.Timedelta(days=1)
    prior_start = prior_end - pd.Timedelta(days=window_days - 1)

    recent = dated[(dated["created_date"] >= recent_start) & (dated["created_date"] <= recent_end)]
    prior = dated[(dated["created_date"] >= prior_start) & (dated["created_date"] <= prior_end)]

    if recent.empty or prior.empty:
        return None, None
    return round(float(recent["sentiment_score"].mean() - prior["sentiment_score"].mean()), 3), window_days


def summarize_dimension(reviews: pd.DataFrame, column: str) -> pd.DataFrame:
    if reviews.empty:
        return pd.DataFrame(columns=[column, "volume", "avg_sentiment", "positive_share", "negative_share"])

    rows = []
    for value, group in reviews.groupby(column):
        scores = group["sentiment_score"].dropna()
        if scores.empty:
            continue
        rows.append(
            {
                column: value,
                "volume": int(len(group)),
                "avg_sentiment": round(float(scores.mean()), 3),
                "positive_share": round(float((scores >= 0.2).mean()), 3),
                "negative_share": round(float((scores <= -0.2).mean()), 3),
                "latest_signal": group["created_date"].max(),
            }
        )
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    return summary.sort_values(["volume", "avg_sentiment"], ascending=[False, False]).reset_index(drop=True)


def build_trend_frame(reviews: pd.DataFrame, frequency: str) -> pd.DataFrame:
    dated = reviews.dropna(subset=["created_date", "sentiment_score"]).copy()
    if dated.empty:
        return pd.DataFrame(columns=["period", "community", "avg_sentiment", "volume"])

    trend = (
        dated.groupby([pd.Grouper(key="created_date", freq=frequency), "community"])
        .agg(avg_sentiment=("sentiment_score", "mean"), volume=("review_id", "count"))
        .reset_index()
        .rename(columns={"created_date": "period"})
    )
    trend["avg_sentiment"] = trend["avg_sentiment"].round(3)
    return trend


def pick_book_highlights(books: pd.DataFrame) -> Dict[str, pd.Series | None]:
    if books.empty:
        return {"top_rated": None, "most_rated": None, "hidden_gem": None}

    rated = books[books["avg_rating"].notna()].copy()
    top_rated_pool = rated[rated["ratings_count"] >= 25]
    top_rated = (
        top_rated_pool.sort_values(["avg_rating", "ratings_count"], ascending=[False, False]).iloc[0]
        if not top_rated_pool.empty
        else rated.sort_values(["avg_rating", "ratings_count"], ascending=[False, False]).iloc[0]
        if not rated.empty
        else None
    )

    most_rated = (
        books.sort_values(["ratings_count", "avg_rating"], ascending=[False, False]).iloc[0]
        if not books.empty
        else None
    )

    hidden_pool = rated[(rated["ratings_count"] >= 5) & (rated["ratings_count"] <= 250)]
    hidden_gem = (
        hidden_pool.sort_values(["avg_rating", "ratings_count"], ascending=[False, False]).iloc[0]
        if not hidden_pool.empty
        else None
    )

    return {
        "top_rated": top_rated,
        "most_rated": most_rated,
        "hidden_gem": hidden_gem,
    }


def build_term_network(reviews: pd.DataFrame, max_terms: int = 14) -> Tuple[go.Figure | None, pd.DataFrame]:
    scored = reviews.dropna(subset=["sentiment_score"]).copy()
    if scored.empty:
        return None, pd.DataFrame(columns=["term", "mentions", "avg_sentiment"])

    term_counts: Counter[str] = Counter()
    term_sentiments: defaultdict[str, List[float]] = defaultdict(list)
    review_terms: List[List[str]] = []

    for row in scored.itertuples():
        unique_terms = list(dict.fromkeys(tokenize_terms(row.content)))[:16]
        if not unique_terms:
            continue
        review_terms.append(unique_terms)
        for term in set(unique_terms):
            term_counts[term] += 1
            term_sentiments[term].append(float(row.sentiment_score))

    top_terms = [term for term, _ in term_counts.most_common(max_terms)]
    if len(top_terms) < 4:
        return None, pd.DataFrame(columns=["term", "mentions", "avg_sentiment"])

    index_map = {term: idx for idx, term in enumerate(top_terms)}
    adjacency = np.zeros((len(top_terms), len(top_terms)))

    for terms in review_terms:
        present = sorted({term for term in terms if term in index_map})
        for left, right in combinations(present, 2):
            left_idx = index_map[left]
            right_idx = index_map[right]
            adjacency[left_idx, right_idx] += 1
            adjacency[right_idx, left_idx] += 1

    if float(adjacency.sum()) == 0:
        return None, pd.DataFrame(columns=["term", "mentions", "avg_sentiment"])

    degrees = np.diag(adjacency.sum(axis=1))
    laplacian = degrees - adjacency
    eigenvalues, eigenvectors = np.linalg.eigh(laplacian)

    if len(top_terms) >= 3 and len(eigenvalues) >= 3:
        x_coords = eigenvectors[:, 1]
        y_coords = eigenvectors[:, 2]
    else:
        angles = np.linspace(0, 2 * np.pi, len(top_terms), endpoint=False)
        x_coords = np.cos(angles)
        y_coords = np.sin(angles)

    if np.allclose(x_coords, x_coords[0]) or np.allclose(y_coords, y_coords[0]):
        angles = np.linspace(0, 2 * np.pi, len(top_terms), endpoint=False)
        x_coords = np.cos(angles)
        y_coords = np.sin(angles)

    node_frame = pd.DataFrame(
        {
            "term": top_terms,
            "x": x_coords,
            "y": y_coords,
            "mentions": [term_counts[term] for term in top_terms],
            "avg_sentiment": [round(float(np.mean(term_sentiments[term])), 3) for term in top_terms],
        }
    )

    edges = []
    for left_idx in range(len(top_terms)):
        for right_idx in range(left_idx + 1, len(top_terms)):
            weight = adjacency[left_idx, right_idx]
            if weight >= 3:
                edges.append((left_idx, right_idx, weight))
    edges = sorted(edges, key=lambda item: item[2], reverse=True)[:28]

    edge_traces = []
    for left_idx, right_idx, weight in edges:
        edge_traces.append(
            go.Scatter(
                x=[node_frame.at[left_idx, "x"], node_frame.at[right_idx, "x"], None],
                y=[node_frame.at[left_idx, "y"], node_frame.at[right_idx, "y"], None],
                mode="lines",
                line=dict(width=0.6 + (weight * 0.22), color="rgba(159, 177, 191, 0.34)"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    node_trace = go.Scatter(
        x=node_frame["x"],
        y=node_frame["y"],
        mode="markers+text",
        text=node_frame["term"].str.title(),
        textposition="top center",
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Mentions: %{customdata[0]}<br>"
            "Avg sentiment: %{customdata[1]:.2f}<extra></extra>"
        ),
        customdata=np.column_stack([node_frame["mentions"], node_frame["avg_sentiment"]]),
        marker=dict(
            size=14 + (node_frame["mentions"] / node_frame["mentions"].max()) * 24,
            color=node_frame["avg_sentiment"],
            colorscale=[
                [0.0, COLORS["coral"]],
                [0.5, COLORS["gold"]],
                [1.0, COLORS["teal"]],
            ],
            cmin=-0.4,
            cmax=0.6,
            line=dict(width=1.4, color="rgba(6, 19, 31, 0.95)"),
            colorbar=dict(title="Sentiment", thickness=14),
        ),
        showlegend=False,
    )

    figure = go.Figure(data=edge_traces + [node_trace])
    figure.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        dragmode=False,
    )
    style_figure(figure, height=620)
    return figure, node_frame.sort_values(["mentions", "avg_sentiment"], ascending=[False, False]).reset_index(drop=True)


def render_filter_pills(pills: Sequence[str]) -> None:
    if not pills:
        pills = ["All books and reader conversations"]
    markup = "".join(f"<span class='filter-pill'>{html.escape(pill)}</span>" for pill in pills)
    st.markdown(markup, unsafe_allow_html=True)


def render_signal_card(kicker: str, title: str, value: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="signal-card">
            <div class="signal-kicker">{html.escape(kicker)}</div>
            <h4>{html.escape(title)}</h4>
            <div class="signal-value">{html.escape(value)}</div>
            <div class="signal-copy">{html.escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_review_card(review: pd.Series) -> None:
    raw_score = review.get("sentiment_score")
    has_score = pd.notna(raw_score)
    score = float(raw_score) if has_score else 0.0
    bucket = review.get("sentiment_bucket", "unknown" if not has_score else "neutral")
    score_color = SENTIMENT_COLORS.get(bucket, COLORS["muted"])
    source = review.get("community", "Unknown")
    query_term = review.get("query_term", "")
    date_value = review.get("created_date")
    date_label = date_value.strftime("%d %b %Y") if pd.notna(date_value) else "Unknown date"
    headline = review.get("title") or review.get("linked_book_title") or review.get("topic_category") or "Reader note"
    body = (review.get("content") or "").strip()
    body = body[:380] + ("..." if len(body) > 380 else "")
    score_label = f"{score:+.2f}" if has_score else "n/a"
    header_bits = [str(source)]
    if query_term and query_term != review.get("topic_category"):
        header_bits.append(str(query_term))
    header_bits.append(str(date_label))

    st.markdown(
        f"""
        <div class="snippet-card">
            <div class="snippet-header">
                <span>{html.escape(" · ".join(header_bits))}</span>
                <span class="snippet-score" style="color: {score_color};">{score_label}</span>
            </div>
            <div class="book-title">{html.escape(str(headline))}</div>
            <div class="snippet-body">{html.escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_reading_snapshot(
    reviews: pd.DataFrame,
    books: pd.DataFrame,
    selected_categories: Sequence[str],
    selected_communities: Sequence[str],
    selected_sentiments: Sequence[str],
    search_query: str,
) -> str:
    scored = reviews["sentiment_score"].dropna()
    avg_sentiment = round(float(scored.mean()), 3) if not scored.empty else 0.0
    topic_summary = summarize_dimension(reviews, "topic_category")
    community_summary = summarize_dimension(reviews, "community")
    highlights = pick_book_highlights(books)

    lines = [
        "# Book Sentiment Snapshot",
        "",
        "## Current View",
        f"- Reviews in view: {len(reviews):,}",
        f"- Books in view: {len(books):,}",
        f"- Average sentiment: {avg_sentiment:+.3f}",
        f"- Search query: {search_query or 'None'}",
        f"- Category filter: {', '.join(selected_categories) if selected_categories else 'All categories'}",
        f"- Community filter: {', '.join(selected_communities) if selected_communities else 'All communities'}",
        f"- Sentiment filter: {', '.join(selected_sentiments) if selected_sentiments else 'All tones'}",
        "",
        "## Community Snapshot",
    ]

    if community_summary.empty:
        lines.append("- No community-level summary available in the current filters.")
    else:
        for row in community_summary.head(5).itertuples():
            lines.append(
                f"- {row.community}: {row.volume} reviews, avg sentiment {row.avg_sentiment:+.3f}, positive share {row.positive_share:.0%}"
            )

    lines.extend(["", "## Category Snapshot"])
    if topic_summary.empty:
        lines.append("- No category-level summary available in the current filters.")
    else:
        for row in topic_summary.head(5).itertuples():
            lines.append(
                f"- {row.topic_category}: {row.volume} reviews, avg sentiment {row.avg_sentiment:+.3f}, positive share {row.positive_share:.0%}"
            )

    lines.extend(["", "## Reader Picks"])
    if highlights["top_rated"] is not None:
        top_pick = highlights["top_rated"]
        lines.append(
            f"- Highest-rated standout: {top_pick['title']} by {top_pick['author']} ({top_pick['avg_rating']:.1f} stars)"
        )
    if highlights["most_rated"] is not None:
        popular_pick = highlights["most_rated"]
        lines.append(
            f"- Most-rated title: {popular_pick['title']} by {popular_pick['author']} ({int(popular_pick['ratings_count']):,} ratings)"
        )
    if highlights["hidden_gem"] is not None:
        gem_pick = highlights["hidden_gem"]
        lines.append(
            f"- Hidden gem: {gem_pick['title']} by {gem_pick['author']} ({gem_pick['avg_rating']:.1f} stars)"
        )

    return "\n".join(lines)


def main() -> None:
    data = load_data()
    books = data["books"]
    reviews = data["reviews"]
    stats = data["stats"]

    if books.empty and reviews.empty:
        st.warning("No processed data is available yet. Run the scraper and sentiment pipeline first.")
        st.code("python3 scripts/scrape_books.py\npython3 scripts/analyze_sentiment.py")
        return

    available_categories = sorted(
        {
            value
            for value in pd.concat(
                [
                    books["category"] if "category" in books.columns else pd.Series(dtype=str),
                    reviews["topic_category"] if "topic_category" in reviews.columns else pd.Series(dtype=str),
                ],
                ignore_index=True,
            ).fillna("")
            if value and value != "Unmapped"
        }
    )
    available_communities = sorted([value for value in reviews["community"].dropna().unique().tolist() if value])
    available_sentiments = ["positive", "neutral", "negative"]

    min_date = stats.get("min_date")
    max_date = stats.get("max_date")

    with st.sidebar:
        st.markdown("## Browse Filters")
        if st.button("Refresh data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        if st.button("Reset filters", use_container_width=True):
            for key in [
                "lens_search",
                "lens_categories",
                "lens_communities",
                "lens_sentiments",
                "lens_min_length",
                "lens_dates",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

        search_query = st.text_input(
            "Search books and reader discussions",
            key="lens_search",
            placeholder="atomic habits, stoicism, investing...",
        )

        selected_categories = st.multiselect(
            "Categories",
            available_categories,
            key="lens_categories",
            help="Applies across the book library and the reader discussion views.",
        )

        selected_communities = st.multiselect(
            "Discussion sources",
            available_communities,
            key="lens_communities",
        )

        selected_sentiments = st.multiselect(
            "Review mood",
            available_sentiments,
            key="lens_sentiments",
        )

        if min_date and max_date:
            date_selection = st.date_input(
                "Date window",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="lens_dates",
            )
            if isinstance(date_selection, tuple) and len(date_selection) == 2:
                start_date = pd.Timestamp(date_selection[0])
                end_date = pd.Timestamp(date_selection[1]) + pd.Timedelta(hours=23, minutes=59, seconds=59)
                date_window = (start_date, end_date)
            else:
                single_date = pd.Timestamp(date_selection)
                date_window = (single_date, single_date + pd.Timedelta(hours=23, minutes=59, seconds=59))
        else:
            date_window = None

        min_length = st.slider(
            "Minimum discussion length",
            min_value=0,
            max_value=500,
            value=60,
            step=20,
            key="lens_min_length",
            help="Raise this to reduce short posts and surface fuller reader comments.",
        )

        st.markdown("---")
        st.markdown("### Dataset Notes")
        if min_date and max_date:
            st.caption(f"Current review snapshot spans {min_date.strftime('%d %b %Y')} to {max_date.strftime('%d %b %Y')}.")
        st.caption(
            "The dashboard combines the book catalog with public reader discussions so people can discover books, compare categories, and skim real audience reactions."
        )

    filtered_books = apply_book_filters(books, search_query, selected_categories)
    filtered_reviews = apply_review_filters(
        reviews,
        search_query,
        selected_categories,
        selected_communities,
        selected_sentiments,
        date_window,
        min_length,
    )

    scored_reviews = filtered_reviews["sentiment_score"].dropna()
    avg_sentiment = round(float(scored_reviews.mean()), 3) if not scored_reviews.empty else 0.0
    delta_value, delta_window = compute_sentiment_delta(filtered_reviews)
    community_summary = summarize_dimension(filtered_reviews, "community")
    topic_summary = summarize_dimension(filtered_reviews, "topic_category")
    highlights = pick_book_highlights(filtered_books)
    date_label = "Date coverage unavailable"
    if min_date and max_date:
        date_label = f"{min_date.strftime('%b %Y')} to {max_date.strftime('%b %Y')}"

    st.markdown(
        f"""
        <div class="hero-shell">
            <div class="eyebrow">Book Sentiment Intelligence</div>
            <div class="hero-title">Discover books readers talk about with real enthusiasm</div>
            <div class="hero-copy">
                Explore how readers feel about books across Mind, Wealth, Health, Skills, and related themes.
                Use the filters to compare categories, browse community discussions, surface recurring ideas,
                and shortlist titles worth your attention.
            </div>
            <div class="hero-meta">
                Current corpus: {stats.get("total_books", 0):,} books · {stats.get("total_reviews", 0):,} reader discussions · {date_label}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    active_pills = []
    if search_query:
        active_pills.append(f"Search: {search_query}")
    if selected_categories:
        active_pills.append("Categories: " + ", ".join(selected_categories))
    if selected_communities:
        active_pills.append("Sources: " + ", ".join(selected_communities))
    if selected_sentiments:
        active_pills.append("Mood: " + ", ".join(selected_sentiments))
    if min_length:
        active_pills.append(f"Min discussion length: {min_length}+ chars")
    render_filter_pills(active_pills)

    st.markdown("")
    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric(
            "Books in view",
            f"{len(filtered_books):,}",
            delta=f"{(len(filtered_books) / len(books) * 100):.0f}% of library" if len(books) else None,
        )
    with metric_cols[1]:
        st.metric(
            "Reader discussions",
            f"{len(filtered_reviews):,}",
            delta=f"{(len(filtered_reviews) / len(reviews) * 100):.0f}% of corpus" if len(reviews) else None,
        )
    with metric_cols[2]:
        st.metric(
            "Average sentiment",
            f"{avg_sentiment:+.2f}",
            delta=f"{delta_value:+.2f} vs prior {delta_window}d" if delta_value is not None and delta_window else None,
        )
    with metric_cols[3]:
        st.metric(
            "Categories covered",
            f"{filtered_reviews['topic_category'].nunique():,}" if not filtered_reviews.empty else "0",
            delta=f"{filtered_reviews['community'].nunique():,} discussion sources" if not filtered_reviews.empty else None,
        )

    brief = build_reading_snapshot(
        filtered_reviews,
        filtered_books,
        selected_categories,
        selected_communities,
        selected_sentiments,
        search_query,
    )
    st.download_button(
        "Download reading snapshot",
        data=brief,
        file_name="book-sentiment-snapshot.md",
        mime="text/markdown",
    )

    if filtered_reviews.empty:
        st.info("No reader discussions match the current filters. Relax one of the filters to reopen the dashboard.")
        return

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Overview", "Reading Trends", "Theme Explorer", "Library"]
    )

    with tab1:
        strongest_category = (
            topic_summary.sort_values(["avg_sentiment", "volume"], ascending=[False, False]).iloc[0]
            if not topic_summary.empty
            else None
        )
        busiest_community = (
            community_summary.sort_values(["volume", "avg_sentiment"], ascending=[False, False]).iloc[0]
            if not community_summary.empty
            else None
        )
        featured_book = highlights["top_rated"] if highlights["top_rated"] is not None else highlights["most_rated"]

        signal_cols = st.columns(3)
        with signal_cols[0]:
            if strongest_category is not None:
                render_signal_card(
                    "Most loved shelf",
                    str(strongest_category["topic_category"]),
                    f"{strongest_category['avg_sentiment']:+.2f}",
                    "Highest average reader sentiment in the current view.",
                )
        with signal_cols[1]:
            if busiest_community is not None:
                render_signal_card(
                    "Most active source",
                    str(busiest_community["community"]),
                    f"{int(busiest_community['volume']):,} posts",
                    "The discussion source with the most reader activity in this filter.",
                )
        with signal_cols[2]:
            if featured_book is not None:
                featured_rating = featured_book.get("avg_rating")
                featured_ratings_raw = featured_book.get("ratings_count")
                featured_ratings_count = int(featured_ratings_raw) if pd.notna(featured_ratings_raw) else 0
                render_signal_card(
                    "Reader favorite",
                    str(featured_book["title"]),
                    (
                        f"{featured_rating:.1f}★"
                        if pd.notna(featured_rating)
                        else f"{featured_ratings_count:,} ratings"
                    ),
                    f"{featured_book.get('author', 'Unknown author')} · {featured_book.get('category', 'Unmapped')}",
                )

        upper_left, upper_right = st.columns([1.05, 1])
        with upper_left:
            st.markdown("### How Readers Feel")
            dist_fig = px.histogram(
                filtered_reviews.dropna(subset=["sentiment_score"]),
                x="sentiment_score",
                color="sentiment_bucket",
                nbins=28,
                opacity=0.82,
                color_discrete_map=SENTIMENT_COLORS,
            )
            dist_fig.update_layout(bargap=0.06, xaxis_title="Sentiment score", yaxis_title="Reader discussions")
            style_figure(dist_fig, height=410)
            st.plotly_chart(dist_fig, use_container_width=True)

        with upper_right:
            st.markdown("### Discussion Sources")
            if not community_summary.empty:
                community_fig = px.bar(
                    community_summary.head(8).sort_values("volume"),
                    x="volume",
                    y="community",
                    color="avg_sentiment",
                    orientation="h",
                    color_continuous_scale=[
                        (0.0, COLORS["coral"]),
                        (0.5, COLORS["gold"]),
                        (1.0, COLORS["teal"]),
                    ],
                )
                community_fig.update_layout(xaxis_title="Discussion volume", yaxis_title="")
                style_figure(community_fig, height=410)
                st.plotly_chart(community_fig, use_container_width=True)
            else:
                st.info("Not enough source variation for a comparison chart.")

        lower_left, lower_right = st.columns([1, 1])
        with lower_left:
            st.markdown("### Category Mood")
            if not topic_summary.empty:
                topic_fig = px.bar(
                    topic_summary.head(8).sort_values("avg_sentiment"),
                    x="avg_sentiment",
                    y="topic_category",
                    color="volume",
                    orientation="h",
                    color_continuous_scale="cividis",
                )
                topic_fig.update_layout(xaxis_title="Average sentiment", yaxis_title="")
                topic_fig.add_vline(x=0, line_dash="dash", line_color="rgba(159, 177, 191, 0.4)")
                style_figure(topic_fig, height=390)
                st.plotly_chart(topic_fig, use_container_width=True)
            else:
                st.info("No topic breakdown available for the current filters.")

        with lower_right:
            st.markdown("### Reader Voices")
            positive_samples = filtered_reviews.dropna(subset=["sentiment_score"]).nlargest(2, "sentiment_score")
            negative_samples = filtered_reviews.dropna(subset=["sentiment_score"]).nsmallest(2, "sentiment_score")

            for _, sample in positive_samples.iterrows():
                render_review_card(sample)
            for _, sample in negative_samples.iterrows():
                render_review_card(sample)

    with tab2:
        st.markdown("### Reader Sentiment Over Time")
        granularity = st.radio(
            "Trend granularity",
            ["Monthly", "Weekly"],
            horizontal=True,
        )
        frequency = "MS" if granularity == "Monthly" else "W-MON"
        trend = build_trend_frame(filtered_reviews, frequency)

        trend_left, trend_right = st.columns([1.2, 0.8])
        with trend_left:
            if not trend.empty:
                sentiment_trend = px.line(
                    trend,
                    x="period",
                    y="avg_sentiment",
                    color="community",
                    markers=True,
                )
                sentiment_trend.update_layout(xaxis_title="", yaxis_title="Average sentiment")
                sentiment_trend.add_hline(y=0, line_dash="dash", line_color="rgba(159, 177, 191, 0.35)")
                style_figure(sentiment_trend, height=460)
                st.plotly_chart(sentiment_trend, use_container_width=True)
            else:
                st.info("Not enough dated reviews for a trend chart.")

        with trend_right:
            if not trend.empty:
                volume_trend = px.area(
                    trend,
                    x="period",
                    y="volume",
                    color="community",
                )
                volume_trend.update_layout(xaxis_title="", yaxis_title="Discussion volume")
                style_figure(volume_trend, height=460)
                st.plotly_chart(volume_trend, use_container_width=True)

        st.markdown("### Source Snapshot")
        if not community_summary.empty:
            table = community_summary.copy()
            table["latest_signal"] = table["latest_signal"].dt.strftime("%d %b %Y")
            st.dataframe(
                table.rename(
                    columns={
                        "community": "Community",
                        "volume": "Volume",
                        "avg_sentiment": "Avg Sentiment",
                        "positive_share": "Positive Share",
                        "negative_share": "Negative Share",
                        "latest_signal": "Latest Signal",
                    }
                )[["Community", "Volume", "Avg Sentiment", "Positive Share", "Negative Share", "Latest Signal"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("The current filters are too narrow to build a source table.")

    with tab3:
        st.markdown("### Reader Theme Map")
        network_fig, term_frame = build_term_network(filtered_reviews)

        map_left, map_right = st.columns([1.35, 0.65])
        with map_left:
            if network_fig is not None:
                st.plotly_chart(network_fig, use_container_width=True)
            else:
                st.info("There are not enough repeated terms in the current filters to render a theme network.")

        with map_right:
            st.markdown("### Common Reader Terms")
            if not term_frame.empty:
                term_bar = px.bar(
                    term_frame.head(10).sort_values("mentions"),
                    x="mentions",
                    y="term",
                    orientation="h",
                    color="avg_sentiment",
                    color_continuous_scale=[
                        (0.0, COLORS["coral"]),
                        (0.5, COLORS["gold"]),
                        (1.0, COLORS["teal"]),
                    ],
                )
                term_bar.update_layout(xaxis_title="Mentions", yaxis_title="")
                style_figure(term_bar, height=620)
                st.plotly_chart(term_bar, use_container_width=True)
            else:
                st.info("Term-level statistics are unavailable for the current filters.")

        st.markdown("### Vocabulary Cloud")
        cloud = generate_wordcloud(filtered_reviews["content"].dropna().tolist())
        if cloud is not None:
            fig, axis = plt.subplots(figsize=(14, 6))
            axis.imshow(cloud, interpolation="bilinear")
            axis.axis("off")
            fig.patch.set_facecolor(COLORS["bg"])
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
        else:
            st.info("No word cloud could be generated from the current slice.")

    with tab4:
        explore_reviews, explore_books = st.tabs(["Reader Discussions", "Book Library"])

        with explore_reviews:
            sort_reviews = st.selectbox(
                "Sort discussions by",
                ["Most recent", "Most positive", "Most negative", "Highest upvotes"],
            )
            review_table = filtered_reviews.copy()
            if sort_reviews == "Most positive":
                review_table = review_table.sort_values("sentiment_score", ascending=False, na_position="last")
            elif sort_reviews == "Most negative":
                review_table = review_table.sort_values("sentiment_score", ascending=True, na_position="last")
            elif sort_reviews == "Highest upvotes":
                review_table = review_table.sort_values("upvotes", ascending=False, na_position="last")
            else:
                review_table = review_table.sort_values("created_date", ascending=False, na_position="last")

            st.caption(f"{len(review_table):,} reader discussions match the current filters.")
            for _, review in review_table.head(18).iterrows():
                render_review_card(review)

        with explore_books:
            sort_books = st.selectbox(
                "Sort books by",
                ["Most rated", "Highest rating", "Newest", "A-Z"],
            )
            book_table = filtered_books.copy()
            if sort_books == "Highest rating":
                book_table = book_table.sort_values(["avg_rating", "ratings_count"], ascending=[False, False], na_position="last")
            elif sort_books == "Newest":
                book_table = book_table.sort_values("published_year", ascending=False, na_position="last")
            elif sort_books == "A-Z":
                book_table = book_table.sort_values("title", ascending=True)
            else:
                book_table = book_table.sort_values(["ratings_count", "avg_rating"], ascending=[False, False], na_position="last")

            st.caption(f"{len(book_table):,} books match the current catalog filters.")
            if book_table.empty:
                st.info("No books match the current topic or search filters.")
            else:
                for _, book in book_table.head(20).iterrows():
                    title = book.get("title") or "Untitled"
                    author = book.get("author") or "Unknown author"
                    category = book.get("category") or "Unmapped"
                    rating = book.get("avg_rating")
                    ratings_raw = book.get("ratings_count")
                    ratings_count = int(ratings_raw) if pd.notna(ratings_raw) else 0
                    year = int(book["published_year"]) if pd.notna(book.get("published_year")) else None
                    description = (book.get("description") or "").strip()
                    description = description[:280] + ("..." if len(description) > 280 else "")

                    st.markdown(
                        f"""
                        <div class="book-card">
                            <div class="book-title">{html.escape(str(title))}</div>
                            <div class="book-meta">
                                {html.escape(str(author))} · {html.escape(str(category))}
                                {' · ' + str(year) if year else ''}
                                {' · Rating ' + format(rating, '.1f') if pd.notna(rating) else ''}
                                {' (' + format(ratings_count, ',') + ' ratings)' if ratings_count else ''}
                                {' · Topic ' + html.escape(str(book.get("subcategory"))) if book.get("subcategory") else ''}
                            </div>
                            <div class="snippet-body">{html.escape(description or 'No description available.')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    with st.expander("How to use this dashboard"):
        st.markdown(
            """
            Use the sidebar filters to narrow the library and the reader discussion stream at the same time.

            The dashboard is most useful for:
            1. Finding categories that readers respond to positively.
            2. Browsing recurring terms and themes before picking a book.
            3. Comparing discussion sources to see where a topic is getting the most attention.
            4. Shortlisting books with strong ratings, active discussion, and relevant themes.
            """
        )


if __name__ == "__main__":
    main()
