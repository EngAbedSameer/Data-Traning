"""Streamlit dashboard for Google Play competitor intelligence."""
import logging
import os
import pandas as pd
import plotly.express as px
import streamlit as st

from market_ai import generate_market_gap_insights
import market_engine
from market_engine import DB_PATH, discover_apps, export_excel, get_country_app_rating, initialize_database, load_saved_reviews, save_competitor_data, scrape_app_reviews


def _common_review_words_compat(reviews_frame, sentiment="All", limit=20):
    """Compatibility fallback for installations with an older market_engine.py."""
    if reviews_frame.empty or "review" not in reviews_frame:
        return pd.DataFrame(columns=["word", "count"])
    selected = reviews_frame
    if sentiment != "All" and "sentiment" in selected:
        selected = selected[selected["sentiment"] == sentiment]
    tokens = (selected["review"].fillna("").astype(str).str.lower()
              .str.replace(r"[^\w\s]", " ", regex=True).str.split().explode())
    stop_words = {"the", "and", "for", "you", "your", "are", "was", "were", "with", "this", "that", "have", "has", "had", "but", "not", "all", "can", "from", "they", "them", "their", "our", "out", "get", "got", "use", "using", "just", "when", "what", "why", "how", "who", "there", "here", "been", "would", "could", "should", "will", "only", "app", "التطبيق", "التطبيقات", "هذا", "هذه", "ذلك", "على", "في", "من", "الى", "إلى", "عن", "مع", "كان", "كانت", "يكون", "يجب", "بعد", "قبل", "كل", "ما", "لا", "لم", "لن", "هو", "هي", "هم", "انا", "أنا", "انت", "أنت", "نحن", "لكن", "حتى", "اذا", "إذا", "انه", "أن", "إن", "او", "أو", "ثم", "قد", "تم", "شيء", "جدا"}
    tokens = tokens[tokens.notna() & tokens.str.len().ge(3) & ~tokens.isin(stop_words)]
    if tokens.empty:
        return pd.DataFrame(columns=["word", "count"])
    return tokens.value_counts().head(max(1, int(limit))).rename_axis("word").reset_index(name="count")


common_review_words = getattr(market_engine, "common_review_words", _common_review_words_compat)


def _generate_market_gap_compat(reviews_frame, api_key, output_language):
    """Support older market_ai modules that predate the output_language option."""
    try:
        return generate_market_gap_insights(reviews_frame, api_key, output_language=output_language)
    except TypeError as error:
        if "unexpected keyword argument" not in str(error) or "output_language" not in str(error):
            raise
        return generate_market_gap_insights(reviews_frame, api_key)

UI_TEXT = {
    "en": {
        "interface_language": "Interface language", "interface_options": {"en": "English", "ar": "Arabic"},
        "title": "Market Intelligence & Competitor Scraping Tool",
        "subtitle": "Explore Google Play competitors, analyze customer feedback, and identify product opportunities.",
        "settings": "Research settings", "country": "Play Store country", "review_language": "Review language",
        "review_count": "Reviews per app", "search_label": "Search by app name, niche, or category",
        "search_placeholder": "e.g. food delivery, fitness tracker", "search": "Search Google Play",
        "searching": "Searching the Google Play Store...", "search_failed": "Search failed: {error}",
        "search_progress": "Search progress",
        "search_steps": {"validate": "Validate the search request", "search": "Search the selected Play Store", "prepare": "Prepare app results", "complete": "Search complete"},
        "results": "Search results", "select_hint": "Choose 2 to 4 competitors, then start review collection.",
        "select_count": "Select between 2 and 4 apps to continue.", "collect": "Collect reviews and analyze",
        "scrape_failed": "Could not collect reviews for {title}: {error}", "no_reviews": "No reviews were collected. Check connectivity and try again.",
        "collected": "Collected {count:,} reviews and saved them to {path}.", "analysis": "Competitor review analysis",
        "tabs": ["Overview", "All Reviews", "Negative Reviews", "Positive Reviews", "Word Frequency", "Market Gap", "Export"],
        "reviews": "Reviews", "competitors": "Competitors", "average_rating": "Average review rating",
        "sentiment_chart": "Sentiment by competitor", "rating_chart": "Review rating distribution", "competitor_details": "Competitor details",
        "all_reviews_count": "All collected reviews ({count:,})", "negative_count": "Negative reviews ({count:,})",
        "positive_count": "Positive reviews ({count:,})", "word_caption": "Most frequent meaningful words across review text. Common English and Arabic stop words are excluded.",
        "review_group": "Review group", "word_groups": ["All", "Negative", "Positive", "Neutral"],
        "word_count": "Number of words", "no_words": "No frequent words to display for this selection.",
        "word_chart": "Most common words — {group} reviews", "mentions": "Mentions", "word": "Word",
        "no_insights": "Collect a new review sample to generate the market-gap brief.",
        "export_description": "Download the competitor metadata, review-level records, and sentiment summary as an Excel workbook.",
        "prepare_report": "Prepare multi-sheet Excel report", "download_report": "Download Excel report",
        "excel_error": "Excel export requires openpyxl. Install it with: pip install openpyxl",
        "footer": "Sentiment labels are a lightweight rating-led heuristic. Treat findings as directional and validate them with customers.",
        "sentiments": {"Positive": "Positive", "Neutral": "Neutral", "Negative": "Negative"},
        "columns": {"app_id": "App ID", "app_title": "App", "title": "App", "developer": "Developer", "app_rating": "Store rating", "rating": "Rating", "review": "Review", "review_date": "Review date", "sentiment": "Sentiment", "thumbs_up": "Helpful votes", "icon": "Icon"},
        "axes": {"app_title": "Competitor", "reviews": "Reviews", "rating": "Rating", "sentiment": "Sentiment"},
        "countries": {"ps": "Palestine", "il": "Israel", "eg": "Egypt", "sa": "Saudi Arabia", "ae": "United Arab Emirates"},
        "review_languages": {"ar": "Arabic", "en": "English", "all": "All languages"},
    },
    "ar": {
        "interface_language": "لغة الواجهة", "interface_options": {"en": "الإنجليزية", "ar": "العربية"},
        "title": "ذكاء السوق وتحليل التطبيقات المنافسة",
        "subtitle": "استكشف التطبيقات المنافسة على Google Play، وحلّل آراء المستخدمين، واكتشف فرص تطوير المنتج.",
        "settings": "إعدادات البحث", "country": "بلد متجر Play", "review_language": "لغة التعليقات",
        "review_count": "عدد التعليقات لكل تطبيق", "search_label": "ابحث باسم التطبيق أو المجال أو الفئة",
        "search_placeholder": "مثال: توصيل الطعام، تطبيق لياقة بدنية", "search": "البحث في Google Play",
        "searching": "جارٍ البحث في Google Play...", "search_failed": "تعذّر البحث: {error}",
        "search_progress": "تقدّم البحث",
        "search_steps": {"validate": "التحقق من عبارة البحث", "search": "البحث في متجر Play للدولة المختارة", "prepare": "تجهيز نتائج التطبيقات", "complete": "اكتمل البحث"},
        "results": "نتائج البحث", "select_hint": "اختر من تطبيقين إلى أربعة تطبيقات، ثم ابدأ جمع التعليقات.",
        "select_count": "اختر من تطبيقين إلى أربعة تطبيقات للمتابعة.", "collect": "جمع التعليقات وتحليلها",
        "scrape_failed": "تعذّر جمع التعليقات لتطبيق {title}: {error}", "no_reviews": "لم يتم جمع أي تعليقات. تحقق من الاتصال ثم حاول مجدداً.",
        "collected": "تم جمع {count:,} تعليقاً وحفظها في {path}.", "analysis": "تحليل تعليقات التطبيقات المنافسة",
        "tabs": ["نظرة عامة", "كل التعليقات", "التعليقات السلبية", "التعليقات الإيجابية", "تكرار الكلمات", "فجوات السوق", "التصدير"],
        "reviews": "التعليقات", "competitors": "التطبيقات المنافسة", "average_rating": "متوسط تقييم التعليقات",
        "sentiment_chart": "المشاعر حسب التطبيق المنافس", "rating_chart": "توزيع تقييمات التعليقات", "competitor_details": "تفاصيل التطبيقات المنافسة",
        "all_reviews_count": "كل التعليقات المجموعة ({count:,})", "negative_count": "التعليقات السلبية ({count:,})",
        "positive_count": "التعليقات الإيجابية ({count:,})", "word_caption": "الكلمات الأكثر تكراراً في التعليقات. تُستبعد كلمات الوقف الشائعة بالعربية والإنجليزية.",
        "review_group": "فئة التعليقات", "word_groups": ["الكل", "السلبية", "الإيجابية", "المحايدة"],
        "word_count": "عدد الكلمات المعروضة", "no_words": "لا توجد كلمات متكررة لعرضها ضمن هذا الاختيار.",
        "word_chart": "الكلمات الأكثر شيوعاً — تعليقات {group}", "mentions": "عدد التكرارات", "word": "الكلمة",
        "no_insights": "اجمع عينة جديدة من التعليقات لإنشاء ملخص فجوات السوق.",
        "export_description": "نزّل بيانات التطبيقات المنافسة والتعليقات وملخص المشاعر في ملف Excel متعدد الأوراق.",
        "prepare_report": "إعداد تقرير Excel متعدد الأوراق", "download_report": "تنزيل تقرير Excel",
        "excel_error": "يتطلب تصدير Excel مكتبة openpyxl. ثبّتها بالأمر: pip install openpyxl",
        "footer": "تصنيف المشاعر تقديري ويعتمد أساساً على التقييم بالنجوم. تحقّق من النتائج عبر أبحاث العملاء.",
        "sentiments": {"Positive": "إيجابي", "Neutral": "محايد", "Negative": "سلبي"},
        "columns": {"app_id": "معرّف التطبيق", "app_title": "التطبيق", "title": "التطبيق", "developer": "المطوّر", "app_rating": "تقييم المتجر", "rating": "التقييم", "review": "التعليق", "review_date": "تاريخ التعليق", "sentiment": "المشاعر", "thumbs_up": "أصوات مفيدة", "icon": "الأيقونة"},
        "axes": {"app_title": "التطبيق المنافس", "reviews": "عدد التعليقات", "rating": "التقييم", "sentiment": "المشاعر"},
        "countries": {"ps": "فلسطين", "il": "إسرائيل", "eg": "مصر", "sa": "السعودية", "ae": "الإمارات العربية المتحدة"},
        "review_languages": {"ar": "العربية", "en": "الإنجليزية", "all": "الجميع"},
    },
}


def _localized_frame(frame):
    display = frame.copy()
    if "sentiment" in display:
        display["sentiment"] = display["sentiment"].map(t["sentiments"]).fillna(display["sentiment"])
    return display.rename(columns=t["columns"])


def _normalize_ui_language(value):
    """Map saved values from older interface selectors to the current language codes."""
    return "ar" if str(value).strip().lower() in {"ar", "arabic", "العربية"} else "en"


def _render_search_progress(placeholder, current_step, language, failed_step=None):
    """Render a localized step list with circular active/completed indicators."""
    steps = ["validate", "search", "prepare", "complete"]
    labels = UI_TEXT[language]["search_steps"]
    current_index = steps.index(failed_step or current_step) if (failed_step or current_step) in steps else 0
    items = []
    for index, step in enumerate(steps):
        if failed_step == step:
            state_class, marker = "failed", "!"
        elif index < current_index:
            state_class, marker = "done", "✓"
        elif failed_step is None and current_step == "complete":
            state_class, marker = "done", "✓"
        elif failed_step is None and index == current_index:
            state_class, marker = "active", str(index + 1)
        else:
            state_class, marker = "pending", str(index + 1)
        items.append(
            f'<div class="flow-step"><span class="flow-ring {state_class}"><span>{marker}</span></span>'
            f'<span>{labels[step]}</span></div>'
        )
    direction = "rtl" if language == "ar" else "ltr"
    html = f"""
    <style>
      @keyframes flow-spin {{ to {{ transform: rotate(360deg); }} }}
      .flow-box {{ direction:{direction}; text-align:{'right' if language == 'ar' else 'left'};
        border:1px solid #d9dee7; border-radius:12px; padding:14px 18px; margin:8px 0 16px;
        background:rgba(128,128,128,.04); }}
      .flow-title {{ font-weight:650; margin-bottom:10px; }}
      .flow-step {{ display:flex; align-items:center; gap:10px; min-height:38px; }}
      .flow-ring {{ width:25px; height:25px; border-radius:50%; box-sizing:border-box;
        display:inline-flex; align-items:center; justify-content:center; flex:0 0 25px;
        font-size:13px; font-weight:700; }}
      .flow-ring span {{ width:19px; height:19px; border-radius:50%; display:flex;
        align-items:center; justify-content:center; background:#fff; }}
      .flow-ring.active {{ border:3px solid #d9e4f5; border-top-color:#2878d0;
        animation:flow-spin .8s linear infinite; color:#2878d0; }}
      .flow-ring.active span {{ animation:flow-spin .8s linear infinite reverse; }}
      .flow-ring.done {{ border:3px solid #279566; color:#18794e; }}
      .flow-ring.failed {{ border:3px solid #d9534f; color:#b42318; }}
      .flow-ring.pending {{ border:2px solid #aab2bf; color:#737b87; }}
    </style>
    <div class="flow-box"><div class="flow-title">{UI_TEXT[language]['search_progress']}</div>
      {''.join(items)}
    </div>
    """
    placeholder.markdown(html, unsafe_allow_html=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
st.set_page_config(page_title="Market Intelligence", page_icon="📊", layout="wide")
initialize_database()

saved_ui = st.session_state.get("interface_language_code", "en")
initial_ui = _normalize_ui_language(saved_ui)
if saved_ui != initial_ui:
    # Normalize saved values from older app versions before creating the widget.
    st.session_state["interface_language_code"] = initial_ui
with st.sidebar:
    interface_language = st.selectbox(UI_TEXT[initial_ui]["interface_language"], ["en", "ar"],
        key="interface_language_code", format_func=lambda code: UI_TEXT[initial_ui]["interface_options"][code])
ui = interface_language
t = UI_TEXT[ui]
if ui == "ar":
    st.markdown("""
    <style>
    .stApp { direction: rtl !important; text-align: right !important; }
    .stApp [data-testid="stSidebar"] * { text-align: right !important; }
    .stApp [data-testid="stTabs"] { direction: rtl !important; }
    .stApp [data-testid="stTabs"] [data-baseweb="tab-list"] {
        direction: rtl !important;
        justify-content: flex-start !important;
    }
    .stApp [data-testid="stTabs"] [data-baseweb="tab"] {
        direction: rtl !important;
        text-align: right !important;
    }
    .stApp [data-testid="stTabs"] [role="tabpanel"] {
        direction: rtl !important;
        text-align: right !important;
    }
    .stApp [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stAlert"],
    .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stMetric"] {
        direction: rtl !important;
        text-align: right !important;
    }
    .stApp [data-testid="stDataFrame"] { direction: rtl !important; }
    </style>
    """, unsafe_allow_html=True)

st.title(t["title"])
st.caption(t["subtitle"])

with st.sidebar:
    st.header(t["settings"])
    country = st.selectbox(t["country"], list(t["countries"]), index=0,
                            format_func=lambda code: t["countries"][code])
    review_language = st.selectbox(t["review_language"], list(t["review_languages"]), index=0,
                                  format_func=lambda code: t["review_languages"][code])
    review_count = st.slider(t["review_count"], min_value=150, max_value=300, value=200, step=50)

query = st.text_input(t["search_label"], placeholder=t["search_placeholder"], type="search", live="300ms")
search_context = (query.strip().casefold(), country, review_language)
search_language = "en" if review_language == "all" else review_language
if st.button(t["search"], type="primary", disabled=not query.strip()):
    progress_box = st.empty()
    progress_state = {"current": "validate"}

    def update_search_progress(step):
        if step == "error":
            _render_search_progress(progress_box, "error", ui, failed_step=progress_state["current"])
            return
        progress_state["current"] = step
        _render_search_progress(progress_box, step, ui)

    update_search_progress("validate")
    with st.spinner(t["searching"]):
        try:
            st.session_state["search_results"] = discover_apps(
                query, lang=search_language, country=country,
                progress_callback=update_search_progress)
            st.session_state["search_context"] = search_context
        except Exception as error:
            update_search_progress("error")
            st.error(t["search_failed"].format(error=error))

results = st.session_state.get("search_results", pd.DataFrame())
if st.session_state.get("search_context") != search_context:
    # Never display results gathered for a previous query, country, or language.
    results = pd.DataFrame()
selected = []
if not results.empty:
    st.subheader(t["results"])
    st.caption(t["select_hint"])
    for index, row in results.iterrows():
        columns = st.columns([1, 8])
        with columns[0]:
            if row.get("icon"):
                st.image(row["icon"], width=56)
        title = str(row.get("title", "Unknown app"))
        developer = str(row.get("developer", "Unknown developer"))
        app_rating = row.get("rating", "N/A")
        app_id = str(row.get("app_id", ""))
        with columns[1]:
            chosen = st.checkbox(f"{title} — {developer} · ★ {app_rating}", key=f"app_{country}_{review_language}_{index}_{app_id}")
            if chosen:
                selected.append(row)
    if selected and not 2 <= len(selected) <= 4:
        st.warning(t["select_count"])
    if st.button(t["collect"], type="primary", disabled=not 2 <= len(selected) <= 4):
        app_rows, review_frames = [], []
        progress = st.progress(0)
        for index, row in enumerate(selected):
            title = str(row.get("title", "Unknown app"))
            app_id = str(row.get("app_id", ""))
            store_rating = get_country_app_rating(
                app_id, lang=search_language, country=country, fallback=row.get("rating"))
            app_rows.append({"app_id": str(row.get("app_id", "")), "title": title,
                             "developer": str(row.get("developer", "")), "rating": store_rating, "icon": str(row.get("icon", ""))})
            try:
                review_frames.append(scrape_app_reviews(app_id, title,
                    developer=str(row.get("developer", "")), rating=store_rating, count=review_count,
                    lang=review_language, country=country))
            except Exception as error:
                st.warning(t["scrape_failed"].format(title=title, error=error))
            progress.progress((index + 1) / len(selected))
        app_frame = pd.DataFrame(app_rows)
        reviews_frame = pd.concat(review_frames, ignore_index=True) if review_frames else pd.DataFrame()
        if reviews_frame.empty:
            st.error(t["no_reviews"])
        else:
            save_competitor_data(app_frame, reviews_frame)
            st.session_state["current_apps"] = app_frame
            st.session_state["current_reviews"] = reviews_frame
            gemini_key = os.environ.get("GEMINI_API_KEY", "")
            try:
                gemini_key = st.secrets.get("GEMINI_API_KEY", gemini_key)
            except Exception:
                pass
            st.session_state["current_insights"] = _generate_market_gap_compat(
                reviews_frame, gemini_key, "Arabic" if ui == "ar" else "English")
            st.success(t["collected"].format(count=len(reviews_frame), path=DB_PATH))

reviews_frame = st.session_state.get("current_reviews", pd.DataFrame())
apps_frame = st.session_state.get("current_apps", pd.DataFrame())
if reviews_frame.empty:
    try:
        reviews_frame = load_saved_reviews()
    except Exception:
        reviews_frame = pd.DataFrame()

if not reviews_frame.empty:
    st.divider()
    st.subheader(t["analysis"])
    summary = reviews_frame.groupby(["app_title", "sentiment"], dropna=False).size().reset_index(name="reviews")
    insights = st.session_state.get("current_insights", "")
    if apps_frame.empty:
        apps_frame = reviews_frame[["app_id", "app_title", "developer", "app_rating"]].drop_duplicates().rename(columns={"app_title": "title", "app_rating": "rating"})
    overview_tab, all_reviews_tab, negative_tab, positive_tab, words_tab, market_gap_tab, export_tab = st.tabs(t["tabs"])
    with overview_tab:
        metric_cols = st.columns(3)
        metric_cols[0].metric(t["reviews"], f"{len(reviews_frame):,}")
        metric_cols[1].metric(t["competitors"], f"{reviews_frame['app_id'].nunique():,}")
        numeric_ratings = pd.to_numeric(reviews_frame["rating"], errors="coerce")
        average_rating = numeric_ratings.mean()
        metric_cols[2].metric(t["average_rating"], f"{average_rating:.2f} / 5" if pd.notna(average_rating) else "N/A")
        left, right = st.columns(2)
        with left:
            display_summary = summary.copy()
            display_summary["sentiment"] = display_summary["sentiment"].map(t["sentiments"])
            st.plotly_chart(px.bar(display_summary, x="app_title", y="reviews", color="sentiment", barmode="stack",
                title=t["sentiment_chart"], labels=t["axes"], color_discrete_map={t["sentiments"]["Positive"]: "#2e8b57", t["sentiments"]["Neutral"]: "#9aa0a6", t["sentiments"]["Negative"]: "#d9534f"}), use_container_width=True)
        with right:
            ratings = reviews_frame.copy()
            ratings["rating"] = pd.to_numeric(ratings["rating"], errors="coerce")
            st.plotly_chart(px.box(ratings, x="app_title", y="rating", color="app_title", title=t["rating_chart"], labels=t["axes"]), use_container_width=True)
        st.subheader(t["competitor_details"])
        display_apps = _localized_frame(apps_frame)
        icon_column = t["columns"]["icon"]
        st.dataframe(display_apps, use_container_width=True, hide_index=True,
            column_config={icon_column: st.column_config.ImageColumn(icon_column, width="small")})
    with all_reviews_tab:
        st.caption(t["all_reviews_count"].format(count=len(reviews_frame)))
        st.dataframe(_localized_frame(reviews_frame), use_container_width=True, hide_index=True)
    with negative_tab:
        negative_reviews = reviews_frame[reviews_frame["sentiment"] == "Negative"]
        st.caption(t["negative_count"].format(count=len(negative_reviews)))
        st.dataframe(_localized_frame(negative_reviews), use_container_width=True, hide_index=True)
    with positive_tab:
        positive_reviews = reviews_frame[reviews_frame["sentiment"] == "Positive"]
        st.caption(t["positive_count"].format(count=len(positive_reviews)))
        st.dataframe(_localized_frame(positive_reviews), use_container_width=True, hide_index=True)
    with words_tab:
        st.caption(t["word_caption"])
        word_groups = dict(zip(t["word_groups"], ["All", "Negative", "Positive", "Neutral"]))
        word_group_label = st.selectbox(t["review_group"], t["word_groups"], key=f"word_sentiment_{ui}")
        word_sentiment = word_groups[word_group_label]
        word_limit = st.slider(t["word_count"], min_value=5, max_value=40, value=20, key="word_limit")
        words = common_review_words(reviews_frame, sentiment=word_sentiment, limit=word_limit)
        if words.empty:
            st.info(t["no_words"])
        else:
            st.plotly_chart(px.bar(words.sort_values("count"), x="count", y="word", orientation="h",
                title=t["word_chart"].format(group=word_group_label.lower()), labels={"count": t["mentions"], "word": t["word"]}), use_container_width=True)
            st.dataframe(words.rename(columns={"word": t["word"], "count": t["mentions"]}), use_container_width=True, hide_index=True)
    with market_gap_tab:
        if insights:
            st.markdown(insights)
        else:
            st.info(t["no_insights"])
    with export_tab:
        st.write(t["export_description"])
        if st.button(t["prepare_report"]):
            try:
                report_path = export_excel(apps_frame, reviews_frame, "competitor_report.xlsx")
                with open(report_path, "rb") as report_file:
                    st.download_button(t["download_report"], data=report_file.read(), file_name="competitor_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except ImportError:
                st.error(t["excel_error"])

st.caption(t["footer"])
