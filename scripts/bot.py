import os
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from woocommerce import API

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Dummy Server for Render Web Service Port Check
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

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

def generate_product_with_gemini(prompt_text):
    api_key = os.getenv("GEMINI_API_KEY_1")
    if not api_key:
        raise ValueError("GEMINI_API_KEY_1 missing in Environment Variables!")

    client = genai.Client(api_key=api_key.strip())
    
    ai_prompt = f"""
    Create an e-commerce product entry based on: "{prompt_text}".
    Output MUST be a single raw JSON object without markdown ticks or pre-text.
    JSON structure:
    {{
        "name": "Product title",
        "regular_price": "3500",
        "short_description": "Catchy short description",
        "description": "Detailed SEO description"
    }}
    """

    # Updated model name to gemini-1.5-flash
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=ai_prompt
    )
    return response.text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send product text to auto-post as WooCommerce Draft.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is online & running.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    chat_id = update.effective_chat.id
    
    await context.bot.send_message(chat_id=chat_id, text="⏳ Processing product details with Gemini AI...")

    try:
        raw_response = generate_product_with_gemini(user_prompt)
        
        # Strip potential markdown formatting from AI output
        clean_json = raw_response.replace("```json", "").replace("```", "").strip()
        product_data = json.loads(clean_json)

        await context.bot.send_message(chat_id=chat_id, text="🔄 Uploading product to WooCommerce...")

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
