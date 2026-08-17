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
    from scripts.google_trends import analyze_store_trends, get_top_regions_and_excel
except ModuleNotFoundError:
    try:
        from google_trends import analyze_store_trends, get_top_regions_and_excel
    except ModuleNotFoundError:
        logging.error("Could not import google_trends module!")

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

def parse_user_intent_with_gemini(user_text):
    api_key = os.getenv("GEMINI_API_KEY_1")
    if not api_key:
        raise ValueError("GEMINI_API_KEY_1 is missing!")

    client = genai.Client(api_key=api_key.strip())
    
    prompt = f"""
    Analyze the user text: "{user_text}".
    Determine the exact user intent from these 5 categories:
    
    1. "where_searched": Asking WHERE/WHICH REGION/COUNTRY a product is searched the most, or asking for search locations/Excel export (e.g., "কোথায় সবচেয়ে বেশি সার্চ হয়?", "which country searches this most?", "excel sheet dao").
    2. "store_trends": Asking to analyze store product demand in a specific country (e.g., "UK te trend কেমন?", "check store trends in USA").
    3. "list_products": Asking to see/list live store products (e.g., "প্রোডাক্ট লিস্ট দেখাও", "কয়টা প্রোডাক্ট আছে").
    4. "product": ONLY if asking to create/upload a NEW store product entry.

    Return JSON ONLY:
    If intent is "where_searched":
    {{"intent": "where_searched"}}

    If intent is "store_trends":
    {{"intent": "store_trends", "country": "extracted country in English (default to USA)"}}

    If intent is "list_products":
    {{"intent": "list_products"}}

    If intent is "product":
    {{"intent": "product", "name": "Title", "regular_price": "0", "description": "SEO Description"}}
    """

    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt
    )
    return response.text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    chat_id = update.effective_chat.id
    
    await context.bot.send_message(chat_id=chat_id, text="⏳ Analyzing request with Gemini 3.6 Flash...")

    try:
        raw_response = parse_user_intent_with_gemini(user_prompt)
        clean_json = raw_response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)

        intent = data.get("intent")

        # 1. Location & Region Search Analysis + Excel Export
        if intent == "where_searched":
            await context.bot.send_message(chat_id=chat_id, text="🌍 Fetching global top search locations & generating Excel report...")
            
            res = wcapi.get("products", params={"per_page": 5, "status": "publish"})
            if res.status_code == 200:
                products = res.json()
                keywords = [p['name'] for p in products]

                report_text, excel_path = get_top_regions_and_excel(keywords)
                await context.bot.send_message(chat_id=chat_id, text=report_text, parse_mode='Markdown')
                
                # Send Excel File to Telegram Chat
                if excel_path and os.path.exists(excel_path):
                    await context.bot.send_document(
                        chat_id=chat_id, 
                        document=open(excel_path, 'rb'),
                        filename="Google_Trends_Regional_Report.xlsx",
                        caption="📊 Here is your detailed Excel research report."
                    )
            else:
                await context.bot.send_message(chat_id=chat_id, text="❌ Failed to fetch products from WooCommerce.")

        # 2. Country Specific Store Trends
        elif intent == "store_trends":
            country = data.get("country", "USA")
            res = wcapi.get("products", params={"per_page": 5, "status": "publish"})
            if res.status_code == 200:
                keywords = [p['name'] for p in res.json()]
                report = analyze_store_trends(keywords, country)
                await context.bot.send_message(chat_id=chat_id, text=report, parse_mode='Markdown')

        # 3. List Live Store Products
        elif intent == "list_products":
            res = wcapi.get("products", params={"per_page": 20, "status": "publish"})
            if res.status_code == 200:
                products = res.json()
                msg = f"📊 **Total Live Published Products: {len(products)}**\n\n"
                for idx, p in enumerate(products, 1):
                    msg += f"{idx}. **{p['name']}** (Price: ${p.get('price', '0')})\n"
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')

        # 4. Upload Product
        elif intent == "product":
            woo_payload = {
                "name": data.get("name", "New Product"),
                "type": "simple",
                "regular_price": str(data.get("regular_price", "0")),
                "description": data.get("description", ""),
                "status": "draft"
            }
            res = wcapi.post("products", woo_payload)
            if res.status_code in [200, 201]:
                await context.bot.send_message(chat_id=chat_id, text="✅ Product Draft Created Successfully.")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Task Failed: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_dummy_server, daemon=True).start()
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.run_polling()
