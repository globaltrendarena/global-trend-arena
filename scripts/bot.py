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
    api_keys = [
        os.getenv("GEMINI_API_KEY_1"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3")
    ]
    api_keys = [k.strip() for k in api_keys if k and k.strip()]

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
                logging.warning(f"Failed with Model: {model}. Error: {e}")
                continue

    raise Exception("All Gemini API Keys and Fallback models quota exhausted!")

def parse_user_intent_with_gemini(user_text):
    prompt = "Strictly analyze the user input: " + str(user_text) + "\n"
    prompt += "Classify into ONE of 4 categories:\n"
    prompt += "1. seo_advice: If user asks for SEO, keywords, CPC, selection, ranking.\n"
    prompt += "2. where_searched: ONLY if asking WHICH COUNTRY/WHERE searched, or Excel download.\n"
    prompt += "3. list_products: Asking to view or count products.\n"
    prompt += "4. general_ai: Other queries.\n\n"
    prompt += "Return ONLY JSON: {\"intent\": \"seo_advice\" | \"where_searched\" | \"list_products\" | \"general_ai\"}"
    
    return call_gemini_with_fallback(prompt)

async def safe_send_markdown(context, chat_id, text):
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
        
        clean_json = raw_response.strip()
        if "{" in clean_json and "}" in clean_json:
            clean_json = clean_json[clean_json.find("{"):clean_json.rfind("}")+1]
            
        data = json.loads(clean_json)
        intent = data.get("intent", "general_ai")

        if intent == "seo_advice":
            await context.bot.send_message(chat_id=chat_id, text="🔍 Fetching WooCommerce products & generating SEO Keyword strategy...")
            res = wcapi.get("products", params={"per_page": 5, "status": "publish"})
            
            if res.status_code == 200:
                products = res.json()
                product_list = ["- " + str(p.get('name', '')) for p in products]
                products_str = "\n".join(product_list)
                
                seo_trends = get_seo_keywords_for_products([p.get('name', '') for p in products])
                
                seo_prompt = "You are an Expert E-commerce SEO Specialist.\n"
                seo_prompt += "User asked: " + str(user_prompt) + "\n\n"
                seo_prompt += "Products:\n" + products_str + "\n\n"
                seo_prompt += "Trends data: " + json.dumps(seo_trends) + "\n\n"
                seo_prompt += "Generate a complete SEO keyword selection strategy in clear Bangla with High-CPC keywords and buyer-intent search queries."
                
                ai_text = call_gemini_with_fallback(seo_prompt)
                await safe_send_markdown(context, chat_id, ai_text)
            else:
                await context.bot.send_message(chat_id=chat_id, text="❌ Failed to fetch products.")

        elif intent == "where_searched":
            await context.bot.send_message(chat_id=chat_id, text="🌍 Analyzing search locations & generating Excel report...")
            res = wcapi.get("products", params={"per_page": 5, "status": "publish"})
            if res.status_code == 200:
                keywords = [p.get('name', '') for p in res.json()]
                report_text, excel_path = get_top_regions_and_excel(keywords)
                
                await safe_send_markdown(context, chat_id, report_text)
                if excel_path and os.path.exists(excel_path):
                    await context.bot.send_document(
                        chat_id=chat_id, 
                        document=open(excel_path, 'rb'),
                        filename="Google_Trends_Regional_Report.xlsx",
                        caption="📊 Download your detailed Google Trends research Excel sheet."
                    )

        elif intent == "list_products":
            res = wcapi.get("products", params={"per_page": 20, "status": "publish"})
            if res.status_code == 200:
                products = res.json()
                msg = "📊 Total Live Published Products: " + str(len(products)) + "\n\n"
                for idx, p in enumerate(products, 1):
                    p_name = str(p.get('name', 'Product'))
                    p_price = str(p.get('price', '0'))
                    msg += str(idx) + ". " + p_name + " (Price: $" + p_price + ")\n"
                await safe_send_markdown(context, chat_id, msg)

        else:
            ai_text = call_gemini_with_fallback(user_prompt)
            await safe_send_markdown(context, chat_id, ai_text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text="❌ Task Failed: " + str(e))

if __name__ == '__main__':
    threading.Thread(target=run_dummy_server, daemon=True).start()
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.run_polling()
