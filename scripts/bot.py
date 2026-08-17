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
    from google_trends import get_google_trends, analyze_store_trends

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Dummy Server for Render Port Check
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
WOO_URL = os.getenv("WOO_SITE_URL")
WOO_KEY = os.getenv("WOO_CONSUMER_KEY")
WOO_SECRET = os.getenv("WOO_CONSUMER_SECRET")

wcapi = API(
    url=WOO_URL,
    consumer_key=WOO_KEY,
    consumer_secret=WOO_SECRET,
    version="wc/v3"
)

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

    # Fixed official Gemini model identifier
    response = client.models.generate_content(
        model='gemini-1.5-flash',
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
        clean_json = raw_response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)

        intent = data.get("intent", "product")

        # 1. Store Product Trends Check
        if intent == "store_trends":
            country = data.get("country", "USA")
            await context.bot.send_message(chat_id=chat_id, text="🛍️ Fetching product list from WooCommerce...")
            
            res = wcapi.get("products", params={"per_page": 5})
            if res.status_code == 200:
                products = res.json()
                keywords = [p['name'] for p in products]

                await context.bot.send_message(chat_id=chat_id, text=f"🔍 Analyzing store keyword trends in **{country}**...")
                report = analyze_store_trends(keywords, country)
                await context.bot.send_message(chat_id=chat_id, text=report, parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=chat_id, text="❌ Failed to fetch products from WooCommerce.")

        # 2. General Trends Check
        elif intent == "trends":
            keyword = data.get("keyword", user_prompt)
            country = data.get("country", "USA")
            await context.bot.send_message(chat_id=chat_id, text=f"🔍 Fetching Google Trends for **{keyword}** in **{country}**...")
            
            report = get_google_trends(keyword, country)
            await context.bot.send_message(chat_id=chat_id, text=report, parse_mode='Markdown')

        # 3. WooCommerce Product Draft Posting
        else:
            await context.bot.send_message(chat_id=chat_id, text="🔄 Generating product details & uploading to WooCommerce...")

            woo_payload = {
                "name": data.get("name", "New Product"),
                "type": "simple",
                "regular_price": str(data.get("regular_price", "0")),
                "description": data.get("description", ""),
                "short_description": data.get("short_description", ""),
                "status": "draft"
            }

            res = wcapi.post("products", woo_payload)

            if res.status_code in [200, 201]:
                created_prod = res.json()
                prod_id = created_prod.get("id")
                prod_name = created_prod.get("name")
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=f"✅ **Success!**\n\nProduct **{prod_name}** (ID: {prod_id}) created as Draft in WooCommerce."
                )
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ WooCommerce API Error: Status Code {res.status_code}")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Task Failed: {str(e)}")

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing!")
    
    threading.Thread(target=run_dummy_server, daemon=True).start()
        
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Telegram Central Bot is running...")
    app.run_polling()
