import os
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from woocommerce import API

# Import module safely
try:
    from scripts.google_trends import get_google_trends, analyze_store_trends
except ModuleNotFoundError:
    try:
        from google_trends import get_google_trends, analyze_store_trends
    except ModuleNotFoundError:
        logging.error("Could not import google_trends module!")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Dummy Server for Render Health Check
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

def parse_user_intent_with_gemini(user_text):
    api_key = os.getenv("GEMINI_API_KEY_1")
    if not api_key:
        raise ValueError("GEMINI_API_KEY_1 is missing in Render Environment Variables!")

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

    # Updated to model gemini-3.5-flash-lite
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=prompt
    )
    return response.text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "👋 **Welcome to AI Assistant Bot!**\n\n"
        "Send prompts in any language:\n"
        "• **General Trends:** 'USA te finance er obostha kemon?'\n"
        "• **Store Trends:** 'Check trends for my store products in UK'\n"
        "• **Post Product:** 'Silk Saree price 4500 BDT'"
    )
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is online & running.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    chat_id = update.effective_chat.id
    
    await context.bot.send_message(chat_id=chat_id, text="⏳ Analyzing your request with Gemini AI...")

    try:
        raw_response = parse_user_intent_with_gemini(user_prompt)
        clean_json = raw_response.replace("```json", "").replace("
