import pandas as pd
import re
from pytrends.request import TrendReq

COUNTRY_CODES = {
    "USA": "US",
    "UNITED STATES": "US",
    "AMERICA": "US",
    "UK": "GB",
    "UNITED KINGDOM": "GB",
    "ENGLAND": "GB",
    "BANGLADESH": "BD",
    "INDIA": "IN",
    "CANADA": "CA",
    "AUSTRALIA": "AU"
}

def clean_keyword(text):
    """ Extract first 1-2 words and remove special characters for Google Trends compatibility """
    clean_text = re.sub(r'[^\w\s]', '', text)
    words = clean_text.split()
    return " ".join(words[:2]) if words else "product"

def get_google_trends(keyword, country="USA"):
    try:
        geo_code = COUNTRY_CODES.get(country.upper(), "US")
        pytrend = TrendReq(hl='en-US', tz=360)
        
        pytrend.build_payload(kw_list=[keyword], timeframe='today 12-m', geo=geo_code)
        
        # Interest by Region
        df_region = pytrend.interest_by_region(resolution='COUNTRY', inc_low_vol=True, inc_geo_code=False)
        top_regions = df_region.sort_values(by=keyword, ascending=False).head(5)
        
        # Related Queries
        related_queries = pytrend.related_queries()
        top_related = []
        if keyword in related_queries and related_queries[keyword]['top'] is not None:
            top_related = related_queries[keyword]['top']['query'].head(5).tolist()

        # Build Response Report
        report = f"📊 **Google Trends Report for '{keyword}' ({country})**\n\n"
        report += "🔥 **Top Interested Regions:**\n"
        if not top_regions.empty:
            for region, row in top_regions.iterrows():
                report += f"• {region}: {row[keyword]}/100\n"
        else:
            report += "No regional data available.\n"
            
        report += "\n💡 **Top Related Search Queries (কীওয়ার্ড):**\n"
        if top_related:
            for q in top_related:
                report += f"• {q}\n"
        else:
            report += "No related queries found.\n"

        return report

    except Exception as e:
        return f"⚠️ Could not fetch Google Trends data: {str(e)}"

def analyze_store_trends(keywords, country="USA"):
    if not keywords:
        return "❌ No WooCommerce products found to analyze."

    geo_code = COUNTRY_CODES.get(country.upper(), "US")
    pytrend = TrendReq(hl='en-US', tz=360)
    
    # Clean keywords to prevent Google 400 error
    clean_kw_list = [clean_keyword(kw) for kw in keywords[:3]]
    clean_kw_list = list(dict.fromkeys(clean_kw_list))
    
    try:
        pytrend.build_payload(kw_list=clean_kw_list, timeframe='now 7-d', geo=geo_code)
        df_interest = pytrend.interest_over_time()
        
        if df_interest.empty:
            return f"⚠️ No trend data available for store products in {country}."

        averages = df_interest[clean_kw_list].mean().sort_values(ascending=False)
        
        report = f"🛍️ **Store Product Trend Analysis ({country})**\n\n"
        report += "📈 **Relative Demand (Out of 100):**\n"
        for kw, score in averages.items():
            report += f"• **{kw}**: {round(score, 1)}/100\n"
            
        top_product = averages.index[0]
        report += f"\n🏆 **Top Demand Product:** {top_product}\n"

        # Fetch Related Search Queries for the Top Product
        try:
            pytrend.build_payload(kw_list=[top_product], timeframe='today 12-m', geo=geo_code)
            related_queries = pytrend.related_queries()
            
            if top_product in related_queries and related_queries[top_product]['top'] is not None:
                top_related = related_queries[top_product]['top']['query'].head(4).tolist()
                report += f"\n🔍 **People also search on Google for '{top_product}':**\n"
                for q in top_related:
                    report += f"• {q}\n"
        except Exception:
            pass # Ignore if related queries fetch fails

        return report

    except Exception as e:
        return f"⚠️ Error analyzing store trends: {str(e)}"
