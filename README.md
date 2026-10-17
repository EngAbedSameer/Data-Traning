# Market Intelligence & Competitor Scraping Tool

A bilingual Streamlit dashboard for researching Google Play competitors. Choose Arabic or English for the interface and choose Arabic, English, or all supported review languages. The all-languages option collects Arabic and English review batches from the selected country and combines them within the selected per-app review limit. The supported Google Play countries are Palestine, Israel, Egypt, Saudi Arabia, and the United Arab Emirates. Search by app name, product niche, or category, select two to four apps, collect a bounded sample of recent reviews, classify review sentiment, and save the results to SQLite. Separate tabs show the overview, all reviews, negative reviews, positive reviews, frequent words, market-gap findings, and Excel export. Arabic mode displays localized labels and right-to-left page alignment. App names and review/comment text remain in their original form; the interface language only changes labels, controls, and analysis summaries.

## Architecture

- `app.py` contains the Streamlit workflow and Plotly charts.
- `market_engine.py` discovers apps, collects up to 300 newest reviews per app, normalizes review data, assigns transparent rating-led sentiment labels, stores records in SQLite, and exports reports.
- `market_ai.py` summarizes low-rated review themes with Gemini when configured. Without a Gemini key it provides a local, rule-based evidence summary.
- `market_engine.py` also counts frequent English and Arabic review words while excluding common stop words; the dashboard can filter this analysis by sentiment.
- `competitor_intelligence.db` is created automatically beside `market_engine.py`, regardless of the app's launch directory. The included empty database is a ready-to-use schema; app and review records are added after a collection run.

The database has `apps` and `reviews` tables, a foreign key, a duplicate guard, and indexes for app/date and sentiment queries. A failed app scrape is reported while the remaining selected apps continue.

## Requirements

Python 3.10 or later and Streamlit 1.64 or later are required. The search field commits after a short pause in typing so the Search button activates without pressing Enter. Install packages with:

```bash
python -m pip install -r requirements.txt
```

`openpyxl` is an explicit additional dependency because pandas needs an Excel writer engine for `.xlsx` reports. Gemini is optional; install its separate dependency only if you want the hosted AI summary:

```bash
python -m pip install -r requirements-ai.txt
```

Without `google-genai` or a configured key, local market-gap analysis remains available. Set `GEMINI_API_KEY` in the environment or configure it in Streamlit secrets to use Gemini. Review text is sent to Gemini only when that feature is enabled.

## Run locally

```bash
streamlit run app.py
```

Use the search field, select two to four results, and click **Collect reviews and analyze**. The request size is limited to 150–300 reviews per competitor. Use **Prepare multi-sheet Excel report** to create a workbook with Competitors, Reviews, and Sentiment Summary sheets.

For Streamlit Community Cloud, publish this folder to a GitHub repository, set `app.py` as the entry point, and configure `GEMINI_API_KEY` under **App settings → Secrets** if Gemini is desired. GitHub Actions secrets are available only to Actions workflows; they do not automatically reach a separately hosted Streamlit app. If Gemini is required in Community Cloud, add `google-genai` to the deployed `requirements.txt` (it is currently kept in the optional `requirements-ai.txt`). The database is local to the running app instance; cloud filesystems may reset on redeploy or restart, so persistent production storage should be configured separately.

## Data and analysis notes

The Google Play scraper depends on access to the public Play Store and may be affected by rate limits, store changes, country, or language. Use it responsibly. The sentiment model is intentionally lightweight: ratings of 4–5 are Positive, 1–2 are Negative, and rating 3 is refined using a small transparent vocabulary. It is not a trained language model and is best treated as directional. Market-gap insights should be validated with customer research.

If Streamlit reports a missing `common_review_words` import or an unexpected `output_language` argument, the project modules came from different versions. The current app has compatibility fallbacks for both cases. For a consistent installation, replace `app.py`, `market_engine.py`, and `market_ai.py` together with the matching versions from this project, then restart Streamlit.

The included Excel workbook requires `openpyxl`; no extra NLP model or service is required for local analysis. Gemini calls are optional and may incur provider charges under the user's API account.
