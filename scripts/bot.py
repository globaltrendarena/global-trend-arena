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

def parse_user_intent_with_gemini(user_text):
    api_key = os.getenv("GEMINI_API_KEY_1")
    if not api_key:
        raise ValueError("GEMINI_API_KEY_1 is missing!")

    client = genai.Client(api_key=api_key.strip())
    
    prompt = f"""
    Strictly analyze the user input: "{user_text}".
    You must classify the request into ONLY ONE of the following 4 categories:

    1. "seo_advice": STRICTLY USE THIS if the user asks for SEO keywords, keyword selection, keyword list, SEO strategy, ranking tips, or how to target products (e.g., "কিওয়ার্ড সিলেক্ট", "SEO তালিকা", "কিওয়ার্ড লিস্ট", "কীভাবে এসইও করব").
    2. "where_searched": ONLY use this if the user EXPLICITLY asks WHICH COUNTRY / WHERE a product is searched, or explicitly asks for an Excel sheet download.
    3. "list_products": User asks to view, list, or count WooCommerce products.
    4. "general_ai": General open questions, chat, or advice not matching above.

    CRITICAL RULE: If the input contains words like "কিওয়ার্ড", "এসইও", "তালিকা", "সিলেক্ট", return "seo_advice". DO NOT return "where_searched".

    Return ONLY a JSON response format:
    {{"intent": "seo_advice" | "where_searched" | "list_products" | "general_ai"}}
    """

    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt
    )
    return response.text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    chat_id = update.effective_chat.id
    
    await context.bot.send_message(chat_id=chat_id, text="⏳ Processing with Gemini 3.6 Flash...")

    try:
        raw_response = parse_user_intent_with_gemini(user_prompt)
        clean_json = raw_response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)

        intent = data.get("intent", "general_ai")

        # 1. SEO Keyword List and Strategy
        if intent == "seo_advice":
            await context.bot.send_message(chat_id=chat_id, text="🔍 WooCommerce প্রোডাক্টের উপর ভিত্তি করে SEO কিওয়ার্ড রিসার্চ করা হচ্ছে...")
            res = wcapi.get("products", params={"per_page": 5, "status": "publish"})
            
            if res.status_code == 200:
                products = res.json()
                product_list = [f"- {p['name']}" for p in products]
                products_str = "\n".join(product_list)
                
                seo_trends = get_seo_keywords_for_products([p['name'] for p in products])
                
                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY_1").strip())
                seo_prompt = f"""
                You are an Expert E-commerce SEO Specialist.
                The user asked: "{user_prompt}"

                Here are the published WooCommerce products from the user's store:
                {products_str}

                Raw Trends Data for related queries:
                {json.dumps(seo_trends)}

                Please generate a complete SEO keyword selection strategy in clear Bangla:
                1. Main Focus Keywords for each product.
                2. Long-tail Keywords for high conversions.
                3. Buyer-intent Search Queries.
                4. Content / Tag suggestions for SEO ranking.
                Use bullet points and bold headers for formatting.
                """
                
                ai_res = client.models.generate_content(model='gemini-3.6-flash', contents=seo_prompt)
                await context.bot.send_message(chat_id=chat_id, text=ai_res.text, parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=chat_id, text="❌ WooCommerce প্রোডাক্ট ফেচ করতে সমস্যা হয়েছে।")

        # 2. Regional Location Search Report & Excel File
        elif intent == "where_searched":
            await context.bot.send_message(chat_id=chat_id, text="🌍 Analyzing search locations & generating Excel report...")
            res = wcapi.get("products", params={"per_page": 5, "status": "publish"})
            if res.status_code == 200:
                keywords = [p['name'] for p in res.json()]
                report_text, excel_path = get_top_regions_and_excel(keywords)
                
                await context.bot.send_message(chat_id=chat_id, text=report_text, parse_mode='Markdown')
                if excel_path and os.path.exists(excel_path):
                    await context.bot.send_document(
                        chat_id=chat_id, 
                        document=open(excel_path, 'rb'),
                        filename="Google_Trends_Regional_Report.xlsx",
                        caption="📊 Download your detailed Google Trends research Excel sheet."
                    )

        # 3. List Published Products
        elif intent == "list_products":
            res = wcapi.get("products", params={"per_page": 20, "status": "publish"})
            if res.status_code == 200:
                products = res.json()
                msg = f"📊 **Total Live Published Products: {len(products)}**\n\n"
                for idx, p in enumerate(products, 1):
                    msg += f"{idx}. **{p['name']}** (Price: ${p.get('price', '0')})\n"
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')

        # 4. General Q&A
        else:
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY_1").strip())
            ai_res = client.models.generate_content(model='gemini-3.6-flash', contents=user_prompt)
            await context.bot.send_message(chat_id=chat_id, text=ai_res.text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Task Failed: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_dummy_server, daemon=True).start()
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.run_polling()
