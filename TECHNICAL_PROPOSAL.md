# Technical Proposal: Google Play Market Intelligence Tool

## Objective

I propose an end-to-end research dashboard that helps product teams compare two to four Google Play competitors using recent customer feedback. It turns discovery, collection, normalization, sentiment segmentation, storage, and executive reporting into one repeatable workflow.

## Proposed architecture

The bilingual Streamlit interface supports Arabic and English display, including right-to-left page alignment for Arabic. It accepts a niche keyword, category, or app name and presents Google Play search results with title, developer, rating, and icon. Stakeholders select two to four competitors and choose a bounded review sample of 150–300 reviews per app. Collection runs one competitor at a time, reports failures independently, and avoids loading unbounded review histories. The dashboard separates the overview, all reviews, negative reviews, positive reviews, frequent-word analysis, market-gap brief, and export controls into dedicated tabs. Interface labels and summaries follow the chosen language; app names and raw review/comment text stay as supplied by the store.

The data engine normalizes review text and timestamps, retains rating and helpful-vote counts, and assigns transparent sentiment labels. Users can collect Arabic reviews, English reviews, or a combined Arabic-and-English sample from the selected country; combined batches are deduplicated and capped at the requested per-app count. Ratings of 4–5 are Positive and 1–2 are Negative. Three-star reviews use a small vocabulary check to distinguish clearly positive or negative language, with Neutral as the default. This simple baseline is explainable and can be replaced with a validated model if the product later requires stronger multilingual accuracy.

Normalized app metadata and review records are stored in SQLite. A relational `apps` table is linked to `reviews` through a foreign key; a uniqueness constraint reduces duplicate inserts and indexes support common app, date, and sentiment queries. Plotly charts compare sentiment counts and rating distributions. A bilingual word-frequency analysis removes common English and Arabic stop words and can be filtered by sentiment. A multi-sheet Excel workbook packages competitor metadata, normalized reviews, and sentiment totals for offline analysis.

For market-gap analysis, only one- and two-star reviews are considered. When a Gemini API key is configured, the system asks the model for recurring complaints, requested features, recommendations, and confidence limits, while instructing it to stay grounded in supplied reviews. Without an API key, a local keyword-based summary keeps the application usable. API use is optional and can incur provider charges.

## Reliability and responsible use

Collection is bounded per app and per run. Exceptions are logged and surfaced so a single competitor failure does not hide successful results for the others. Data is locally queryable and exports are generated on demand. Google Play availability and rate limits can change; the tool is intended for responsible market research and not for bypassing access controls. Review samples are directional and should be validated with interviews or surveys.

## Deployment and operations

The application runs with `streamlit run app.py` and can be deployed to Streamlit Community Cloud from a GitHub repository. Streamlit secrets can hold the optional Gemini key. The shipped SQLite file provides the requested schema and is initialized automatically. Community Cloud local storage may not persist through restarts or redeployments, so production use requiring durable history should connect a managed database.

## Deliverables

- Modular Python implementation: `app.py`, `market_engine.py`, and `market_ai.py`.
- `requirements.txt` with bounded package versions.
- `competitor_intelligence.db` with the normalized SQLite schema.
- Streamlit dashboard, Plotly visualizations, and multi-sheet Excel export.
- This technical proposal and setup instructions in `README.md`.
