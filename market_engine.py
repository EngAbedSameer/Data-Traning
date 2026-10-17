"""Google Play competitor discovery, review analysis, storage, and exports."""

import csv
import logging
import os
import sqlite3

import pandas as pd
from google_play_scraper import Sort, app as play_app, reviews, search


LOG = logging.getLogger(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "competitor_intelligence.db")
REVIEW_COLUMNS = ["app_id", "app_title", "developer", "rating", "review", "review_date", "sentiment", "thumbs_up"]
COMMON_STOP_WORDS = {
    "the", "and", "for", "you", "your", "are", "was", "were", "with", "this", "that", "have", "has",
    "had", "but", "not", "all", "can", "cannot", "very", "too", "from", "they", "them", "their", "its",
    "our", "out", "get", "got", "use", "using", "just", "when", "what", "why", "how", "who", "there",
    "here", "been", "would", "could", "should", "will", "only", "app", "التطبيق", "التطبيقات", "هذا",
    "هذه", "ذلك", "على", "في", "من", "الى", "إلى", "عن", "مع", "كان", "كانت", "يكون", "يجب", "بعد",
    "قبل", "كل", "ما", "لا", "لم", "لن", "هو", "هي", "هم", "انا", "أنا", "انت", "أنت", "نحن", "وهو",
    "وهي", "لكن", "حتى", "اذا", "إذا", "انه", "أن", "إن", "او", "أو", "ثم", "قد", "تم", "شيء", "جدا",
}


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def discover_apps(query, limit=20, lang="en", country="us", progress_callback=None):
    """Search a selected Play Store country and return its result cards."""
    query = str(query).strip()
    if not query:
        return pd.DataFrame()
    if progress_callback:
        progress_callback("search")
    try:
        rows = search(query, lang=lang, country=country, n_hits=max(1, min(int(limit), 50)))
    except Exception:
        LOG.exception("Google Play search failed for %r", query)
        raise
    frame = pd.DataFrame(rows)
    if progress_callback:
        progress_callback("prepare")
    if frame.empty:
        if progress_callback:
            progress_callback("complete")
        return frame
    for column in ["title", "developer", "appId", "score", "icon"]:
        if column not in frame:
            frame[column] = ""
    frame = frame.rename(columns={"appId": "app_id", "score": "rating"})
    frame["store_country"] = country.lower()
    if progress_callback:
        progress_callback("complete")
    return frame


def get_country_app_rating(app_id, lang="en", country="us", fallback=None):
    """Resolve one selected app's rating from the chosen Play Store country."""
    try:
        details = play_app(str(app_id), lang=lang, country=country)
        return details.get("score", fallback)
    except Exception:
        LOG.warning("Could not refresh country-specific rating for %s (%s)", app_id, country, exc_info=True)
        return fallback


def _sentiment(rating, text):
    """Transparent lightweight sentiment label; rating takes precedence."""
    try:
        score = float(rating)
    except (TypeError, ValueError):
        score = 0
    if score >= 4:
        return "Positive"
    if score <= 2:
        return "Negative"
    # Neutral star ratings can still reveal clear polarity in text.
    words = str(text).lower().split()
    positive = {"great", "love", "excellent", "easy", "helpful", "perfect", "good", "amazing", "thanks"}
    negative = {"bad", "hate", "crash", "bug", "broken", "slow", "poor", "terrible", "wrong", "issue", "error"}
    pos = sum(1 for word in words if word.strip(".,!?()") in positive)
    neg = sum(1 for word in words if word.strip(".,!?()") in negative)
    return "Positive" if pos > neg else "Negative" if neg > pos else "Neutral"


def _clean_review_text(value):
    # pandas' vectorized string operations handle whitespace normalization.
    return pd.Series([value]).fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip().iloc[0]


def common_review_words(reviews_frame, sentiment="All", limit=20):
    """Return the most frequent meaningful English or Arabic review words."""
    if reviews_frame.empty or "review" not in reviews_frame:
        return pd.DataFrame(columns=["word", "count"])
    selected = reviews_frame
    if sentiment != "All" and "sentiment" in selected:
        selected = selected[selected["sentiment"] == sentiment]
    tokens = (selected["review"].fillna("").astype(str).str.lower()
              .str.replace(r"[^\w\s]", " ", regex=True).str.split().explode())
    tokens = tokens[tokens.notna() & tokens.str.len().ge(3) & ~tokens.isin(COMMON_STOP_WORDS)]
    if tokens.empty:
        return pd.DataFrame(columns=["word", "count"])
    return (tokens.value_counts().head(max(1, int(limit))).rename_axis("word")
            .reset_index(name="count"))


def scrape_app_reviews(app_id, app_title, developer="", rating=None, count=200, lang="en", country="us"):
    """Fetch newest reviews in the selected language(s) from one Play country."""
    count = max(150, min(int(count), 300))
    languages = ["ar", "en"] if lang == "all" else [lang]
    language_rows = {}
    failures = []
    for language in languages:
        try:
            rows, _ = reviews(app_id, lang=language, country=country, sort=Sort.NEWEST, count=count)
            language_rows[language] = rows
        except Exception as error:
            LOG.exception("Review scrape failed for %s in %s (%s)", app_id, language, country)
            failures.append(error)
    if not language_rows:
        raise failures[0]

    # Interleave language batches so the combined result represents both
    # supported languages while staying within the requested per-app limit.
    rows = []
    seen = set()
    positions = {language: 0 for language in languages}
    while len(rows) < count:
        added = False
        for language in languages:
            batch = language_rows.get(language, [])
            while positions[language] < len(batch):
                item = batch[positions[language]]
                positions[language] += 1
                identity = item.get("reviewId") or (
                    item.get("content", ""), item.get("score"), str(item.get("at", "")),
                    item.get("userName", ""),
                )
                if identity in seen:
                    continue
                seen.add(identity)
                rows.append(item)
                added = True
                break
            if len(rows) >= count:
                break
        if not added:
            break

    result = []
    for row in rows:
        content = _clean_review_text(row.get("content", ""))
        date = row.get("at")
        result.append({
            "app_id": app_id,
            "app_title": app_title,
            "developer": developer,
            "rating": row.get("score"),
            "review": content,
            "review_date": pd.to_datetime(date, errors="coerce", utc=True),
            "sentiment": _sentiment(row.get("score"), content),
            "thumbs_up": row.get("thumbsUpCount", 0),
        })
    frame = pd.DataFrame(result, columns=REVIEW_COLUMNS)
    if not frame.empty:
        frame["review_date"] = pd.to_datetime(frame["review_date"], errors="coerce", utc=True)
    return frame


def initialize_database(path=DB_PATH):
    """Create relational tables and indexes without overwriting existing data."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("""CREATE TABLE IF NOT EXISTS apps (
                app_id TEXT PRIMARY KEY, title TEXT NOT NULL, developer TEXT, store_rating REAL,
                icon_url TEXT, collected_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT NOT NULL,
                rating INTEGER, review TEXT, review_date TEXT, sentiment TEXT,
                thumbs_up INTEGER DEFAULT 0, collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(app_id, rating, review_date, review),
                FOREIGN KEY(app_id) REFERENCES apps(app_id) ON DELETE CASCADE)""")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reviews_app_date ON reviews(app_id, review_date)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews(sentiment)")
    finally:
        connection.close()
    return path


def save_competitor_data(apps_frame, reviews_frame, path=DB_PATH):
    initialize_database(path)
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            for _, row in apps_frame.iterrows():
                connection.execute("""INSERT INTO apps(app_id,title,developer,store_rating,icon_url)
                    VALUES(?,?,?,?,?) ON CONFLICT(app_id) DO UPDATE SET title=excluded.title,
                    developer=excluded.developer,store_rating=excluded.store_rating,icon_url=excluded.icon_url""",
                    (str(row.get("app_id", "")), str(row.get("title", "Unknown")), str(row.get("developer", "")),
                     _number_or_none(row.get("rating")), str(row.get("icon", ""))))
            for _, row in reviews_frame.iterrows():
                date = row.get("review_date")
                date_value = date.isoformat() if hasattr(date, "isoformat") and not pd.isna(date) else None
                connection.execute("""INSERT OR IGNORE INTO reviews
                    (app_id,rating,review,review_date,sentiment,thumbs_up) VALUES(?,?,?,?,?,?)""",
                    (str(row.get("app_id", "")), _number_or_none(row.get("rating")), str(row.get("review", "")),
                     date_value, str(row.get("sentiment", "Neutral")), int(row.get("thumbs_up", 0) or 0)))
    finally:
        connection.close()


def _number_or_none(value):
    try:
        return float(value) if not pd.isna(value) else None
    except (TypeError, ValueError):
        return None


def load_saved_reviews(path=DB_PATH):
    initialize_database(path)
    connection = sqlite3.connect(path)
    try:
        return pd.read_sql_query("""SELECT a.title AS app_title,a.developer,a.store_rating AS app_rating,
            r.app_id,r.rating,r.review,r.review_date,r.sentiment,r.thumbs_up
            FROM reviews r JOIN apps a ON a.app_id=r.app_id ORDER BY r.review_date DESC""", connection)
    finally:
        connection.close()


def export_excel(apps_frame, reviews_frame, output_path="competitor_report.xlsx"):
    """Write a multi-sheet workbook; openpyxl is the explicit Excel writer dependency."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    export_reviews = reviews_frame.copy()
    if "review_date" in export_reviews:
        dates = pd.to_datetime(export_reviews["review_date"], errors="coerce", utc=True)
        export_reviews["review_date"] = dates.dt.tz_localize(None)
    summary = export_reviews.groupby(["app_title", "sentiment"], dropna=False).size().unstack(fill_value=0).reset_index() if not export_reviews.empty else pd.DataFrame()
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        apps_frame.to_excel(writer, sheet_name="Competitors", index=False)
        export_reviews.to_excel(writer, sheet_name="Reviews", index=False)
        summary.to_excel(writer, sheet_name="Sentiment Summary", index=False)
    return output_path


def export_reviews_csv(reviews_frame, output_path="reviews_export.csv"):
    reviews_frame.to_csv(output_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    return output_path
