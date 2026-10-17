"""Strategic market-gap synthesis with optional Gemini support."""
import logging
import os
import pandas as pd

LOG = logging.getLogger(__name__)

def _local_insights(reviews_frame, output_language="English"):
    low = reviews_frame[pd.to_numeric(reviews_frame["rating"], errors="coerce") <= 2].copy()
    if low.empty:
        return "No 1-star or 2-star feedback was collected. Gather more low-rated reviews to identify evidence-based gaps."
    text = low["review"].fillna("").astype(str).str.lower()
    themes = {
        "Crashes or technical errors": r"crash|error|bug|freeze|broken|fail|تعطل|انهيار|خطأ|عطل|مشكلة",
        "Slow performance": r"slow|loading|lag|wait|بطيء|بطء|تحميل|يتأخر",
        "Payments or pricing": r"payment|charge|price|subscription|refund|billing|دفع|السعر|اشتراك|استرداد|فاتورة",
        "Login or account access": r"login|sign in|account|password|verification|دخول|حساب|كلمة المرور|تسجيل",
        "Missing or hard-to-use features": r"feature|wish|please add|missing|can't|cannot|ميزة|اضيفوا|أضيفوا|ناقص|إضافة",
    }
    findings = sorted([(label, int(text.str.contains(pattern, regex=True).sum())) for label, pattern in themes.items()], key=lambda item: item[1], reverse=True)
    arabic = output_language.lower().startswith("ar")
    title = "ملخص تنفيذي لفجوات السوق (تحليل محلي مستند إلى التعليقات)" if arabic else "Executive market-gap brief (local evidence-based analysis)"
    pain_heading = "أبرز المشكلات المتكررة في تقييمات نجمة أو نجمتين:" if arabic else "Recurring 1-2 star pain points:"
    lines = [title, "", pain_heading]
    matched = [(label, count) for label, count in findings if count]
    if arabic:
        labels = {"Crashes or technical errors": "الأعطال والأخطاء التقنية", "Slow performance": "بطء الأداء",
                  "Payments or pricing": "المدفوعات والأسعار", "Login or account access": "الدخول إلى الحساب",
                  "Missing or hard-to-use features": "الميزات المطلوبة أو صعبة الاستخدام"}
        lines += [f"- {labels[label]}: وردت في {count} من التعليقات منخفضة التقييم." for label, count in matched[:5]] or ["- لم تتكرر موضوعات ضمن الفئات المحددة؛ راجع نصوص التعليقات قبل تحديد الأولويات."]
        lines += ["", "توصيات للمنتج:",
                  "- أعطِ الأولوية للمشكلة الأكثر تكراراً وتحقق منها عبر مقابلات العملاء.",
                  "- حوّل طلبات الميزات إلى فرضيات قابلة للاختبار؛ فالعينة استرشادية وليست ممثلة للسوق.",
                  "- تابع كل موضوع وتطبيق منافس في دورة البحث التالية لمعرفة ما إذا كانت الفجوة مستمرة."]
    else:
        lines += [f"- {label}: mentioned in {count} low-rated review(s)." for label, count in matched[:5]] or ["- No recurring theme matched built-in keyword categories; review the raw feedback before prioritizing."]
        lines += ["", "Product recommendations:",
                  "- Prioritize the highest-frequency pain point and validate it with customer interviews.",
                  "- Turn feature requests into testable product hypotheses; this sample is directional, not representative.",
                  "- Track each theme and competitor in the next research cycle to measure whether the gap persists."]
    return "\n".join(lines)

def generate_market_gap_insights(reviews_frame, api_key=None, model="gemini-2.5-flash", output_language="English"):
    """Use Gemini when configured, otherwise return reproducible local insights."""
    if reviews_frame.empty:
        return "اجمع تعليقات التطبيقات المنافسة قبل إنشاء ملخص فجوات السوق." if output_language.lower().startswith("ar") else "Collect competitor reviews before generating market-gap insights."
    low = reviews_frame[pd.to_numeric(reviews_frame["rating"], errors="coerce") <= 2]
    if low.empty:
        return "لم نعثر على تعليقات بتقييم نجمة أو نجمتين في هذه العينة." if output_language.lower().startswith("ar") else "No 1-star or 2-star reviews were found in this sample."
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        local = _local_insights(reviews_frame, output_language)
        notice = "لم يتم إعداد Gemini. أضف GEMINI_API_KEY إلى أسرار Streamlit أو متغيرات البيئة لتفعيل الملخص بالذكاء الاصطناعي." if output_language.lower().startswith("ar") else "Gemini is not configured. Set GEMINI_API_KEY in Streamlit secrets or the environment to enable AI summaries."
        return local + "\n\n" + notice
    try:
        from google import genai
        client = genai.Client(api_key=key)
        evidence = low[["app_title", "rating", "review"]].fillna("").to_dict(orient="records")[:500]
        prompt = (f"Analyze these competitor Google Play reviews for a product team. Respond in {output_language}. Use only evidence in the data. "
                  "Keep every app name exactly as supplied. Do not translate app names. Do not quote or translate raw review/comment text; summarize themes in your own words. "
                  "Return an executive brief with recurring bugs/complaints, requested or missing features, "
                  "three strategic recommendations, and confidence/limitations. Do not invent competitor features.\n\n"
                  + str(evidence))
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text or _local_insights(reviews_frame, output_language)
    except Exception as error:
        LOG.exception("Gemini analysis failed; using local analysis")
        # Show the API's diagnostic message and status when available. The old
        # message only displayed the exception class (e.g. ClientError), which
        # was not enough to distinguish a bad key from quota/model issues.
        error_detail = getattr(error, "message", None) or str(error)
        error_code = getattr(error, "code", None)
        if error_code:
            error_detail = f"HTTP {error_code}: {error_detail}"
        if key:
            error_detail = error_detail.replace(key, "[hidden]")
        error_detail = " ".join(str(error_detail).split())[:700]
        if output_language.lower().startswith("ar"):
            return _local_insights(reviews_frame, output_language) + f"\n\nتعذّر طلب Gemini ({type(error).__name__}: {error_detail})؛ يعرض التطبيق التحليل المحلي."
        return _local_insights(reviews_frame, output_language) + f"\n\nGemini request failed ({type(error).__name__}: {error_detail}); showing local analysis instead."

