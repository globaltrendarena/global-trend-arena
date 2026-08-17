import os
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from woocommerce import API

try:
    from scripts.google_trends import analyze_store_trends, get_top_regions_and_excel, get_seo_keywords_for_products
except ModuleNotFoundError:
    from google_trends import analyze_store_trends, get_top_regions_and_excel, get_seo_keywords_for_products

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is live!")

def run_dummy_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WOO_URL = os.getenv("WOO_SITE_URL", "")
WOO_KEY = os.getenv("WOO_CONSUMER_KEY", "")
WOO_SECRET = os.getenv("WOO_CONSUMER_SECRET", "")

wcapi = API(
    url=WOO_URL,
    consumer_key=WOO_KEY,
    consumer_secret=WOO_SECRET,
    version="wc/v3"
)

def call_gemini_with_fallback(prompt):
    """ Call Gemini with multi-key and multi-model fallback logic """
    api_keys = [
        os.getenv("GEMINI_API_KEY_1"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3")
    ]
    api_keys = [k.strip() for k in api_keys if k and k.strip()]

    # Corrected Model Priority: 3.5-flash-lite -> 3.6-flash -> 3.1-pro
    models = ['gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-3.1-pro']

    for key in api_keys:
        client = genai.Client(api_key=key)
        for model in models:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                return response.text
            except Exception as e:
                logging.warning(f"Failed with Model: {model} using Key ending in ...{key[-4:]}. Error: {e}")
                continue

    raise Exception("All Gemini API Keys and Fallback models quota exhausted!")

def parse_user_intent_with_gemini(user_text):
    prompt = f"""
    Strictly analyze the user input: "{user_text}".
    You must classify the request into ONLY ONE of the following 4 categories:

    1. "seo_advice": STRICTLY USE THIS if the user asks for SEO keywords, keyword selection, keyword list, high CPC keywords, SEO strategy, ranking tips, or how to target products.
    2. "where_searched": ONLY use this if the user EXPLICITLY asks WHICH COUNTRY / WHERE a product is searched, or explicitly asks for an Excel sheet download.
    3. "list_products": User asks to view, list, or count WooCommerce products.
    4. "general_ai": General open questions, chat, or advice not matching above.

    CRITICAL RULE: If the input contains words like "কিওয়ার্ড", "এসইও", "সিপিসি", "CPC", "তালিকা", "সিলেক্ট", return "seo_advice". DO NOT return "where_searched".

    Return ONLY a JSON response format:
    {{"intent": "seo_advice" | "where_searched" | "list_products" | "general_ai"}}
    """
    return call_gemini_with_fallback(prompt)

async def safe_send_markdown(context, chat_id, text):
    """ Safely send markdown message; fallback to plain text if Telegram fails to parse """
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    chat_id = update.effective_chat.id
    
    await context.bot.send_message(chat_id=chat_id, text="⏳ Processing request with AI...")

    try:
        raw_response = parse_user_intent_with_gemini(user_prompt)
        clean_json = raw_response.replace("```json", "").replace("
