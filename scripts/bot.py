import os
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from woocommerce import API

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Dummy Server to pass Render Health Check
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is live!")

def run_dummy_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WOO_URL = os.getenv("WOO_SITE_URL")
WOO_KEY = os.getenv("WOO_CONSUMER_KEY")
WOO_SECRET = os.getenv("WOO_CONSUMER_SECRET")

# WooCommerce API Setup
wcapi = API(
    url=WOO_URL,
    consumer_key=WOO_KEY,
    consumer_secret=WOO_SECRET,
    version="wc/v3"
)

# Gemini API Fallback Engine (Robust Version)
def generate_with_gemini_fallback(prompt_text):
    api_keys = [
        os.getenv("GEMINI_API_KEY_1"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3")
    ]
    api_keys = [k.strip() for k in api_keys if k and k.strip()]

    if not api_keys:
        raise ValueError("❌ No valid Gemini API Keys found in Environment Variables!")

    for index, key in enumerate(api_keys, start=1):
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt_text)
            logging.info(f"Successfully generated using Gemini Key #{index}")
            return response.text
        except Exception as e:
            logging.warning(f"Gemini Key #{index} failed: {e}")
            
    raise Exception("❌ All Gemini API Keys failed or invalid. Please check Google AI Studio keys.")

# /start Command Handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 Welcome to Inaaya's Mart AI Control Center!\n\n"
        "Available Commands:\n"
        "1. Send product idea/text: Auto-generates & posts to WooCommerce as draft.\n"
        "2. /status - Check system connectivity."
    )
    await update.message.reply_text(welcome_text)

# System Status Check Command
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is online & connected to GitHub Secrets and WooCommerce!")

# Main Message Processing Routine
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    chat_id = update.effective_chat.id
    
    await context.bot.send_message(chat_id=chat_id, text="⏳ Processing your request with Gemini AI...")

    try:
        ai_prompt = f"""
        Create a product entry for an e-commerce store based on this instruction: "{user_prompt}".
        Provide output ONLY in valid JSON format without markdown ticks with keys:
        "name" (product title),
        "regular_price" (estimated numeric price string e.g. "3500"),
        "short_description" (2-3 lines catchy description),
        "description" (detailed SEO-friendly description)
        """

        raw_ai_response = generate_with_gemini_fallback(ai_prompt)

        clean_json_str = raw_ai_response.replace("```json", "").replace("```", "").strip()
        product_data = json.loads(clean_json_str)

        await context.bot.send_message(chat_id=chat_id, text="🔄 Uploading product to Inaaya's Mart via WooCommerce API...")

        woo_payload = {
            "name": product_data.get("name", "New Product"),
            "type": "simple",
            "regular_price": str(product_data.get("regular_price", "0")),
            "description": product_data.get("description", ""),
            "short_description": product_data.get("short_description", ""),
            "status": "draft"
        }

        res = wcapi.post("products", woo_payload)

        if res.status_code in [200, 201]:
            created_prod = res.json()
            prod_id = created_prod.get("id")
            prod_name = created_prod.get("name")
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"✅ **Successfully Done!**\n\nProduct **{prod_name}** (ID: {prod_id}) has been created as a Draft in WooCommerce."
            )
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ WooCommerce API Error: Status Code {res.status_code}")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Task Failed: {str(e)}")

# Application Startup
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
