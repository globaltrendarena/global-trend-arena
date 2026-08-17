def parse_user_intent_with_gemini(user_text):
    api_key = os.getenv("GEMINI_API_KEY_1")
    if not api_key:
        raise ValueError("GEMINI_API_KEY_1 missing in Environment Variables!")

    client = genai.Client(api_key=api_key.strip())
    
    prompt = f"""
    Analyze the user text (which can be in ANY language): "{user_text}".
    Determine the intent:
    1. If asking to analyze store/website products trend (e.g., "check store trends", "my product trends in USA"), set intent to "store_trends".
    2. If asking for general Google Trends/Keywords in a location, set intent to "trends".
    3. Otherwise, set intent to "product" to generate a WooCommerce product entry.

    IMPORTANT: Translate extracted values (keywords, product titles, descriptions) into English.

    Return JSON ONLY with structure:
    If intent is "store_trends":
    {{"intent": "store_trends", "country": "extracted country in English like USA, UK, Canada (default to USA)"}}

    If intent is "trends":
    {{"intent": "trends", "keyword": "extracted keyword in English", "country": "extracted country in English (default to USA)"}}

    If intent is "product":
    {{"intent": "product", "name": "Title in English", "regular_price": "Numeric string", "short_description": "Summary in English", "description": "SEO Description in English"}}
    """

    # 3.5 Flash-Lite এর জন্য model='gemini-3.5-flash-lite'
    # 3.6 Flash এর জন্য model='gemini-3.6-flash'
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite', 
        contents=prompt
    )
    return response.text
