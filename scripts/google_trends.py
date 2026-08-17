import pandas as pd
import re
import os
from pytrends.request import TrendReq

def clean_keyword(text):
    clean_text = re.sub(r'[^\w\s]', '', text)
    words = clean_text.split()
    return " ".join(words[:2]) if words else "product"

def get_top_regions_and_excel(keywords):
    """ Fetch top searching regions worldwide & generate an Excel file """
    pytrend = TrendReq(hl='en-US', tz=360)
    
    clean_kw_list = [clean_keyword(kw) for kw in keywords[:5]]
    clean_kw_list = list(dict.fromkeys(clean_kw_list))

    try:
        pytrend.build_payload(kw_list=clean_kw_list, timeframe='today 12-m')
        df_region = pytrend.interest_by_region(resolution='COUNTRY', inc_low_vol=True)
        
        # Save Excel File
        excel_path = "google_trends_report.xlsx"
        df_region.to_excel(excel_path)

        report = "🌍 **Worldwide Top Searching Regions:**\n\n"
        for kw in clean_kw_list:
            if kw in df_region.columns:
                top_countries = df_region.sort_values(by=kw, ascending=False).head(3)
                report += f"🔹 **{kw}**:\n"
                for country, row in top_countries.iterrows():
                    if row[kw] > 0:
                        report += f"  • {country}: {row[kw]}/100\n"
                report += "\n"

        return report, excel_path

    except Exception as e:
        return f"⚠️ Error fetching regional data: {str(e)}", None

def analyze_store_trends(keywords, country="USA"):
    if not keywords:
        return "❌ No WooCommerce products found to analyze."

    geo_code = "US" if country.upper() in ["USA", "UNITED STATES"] else ""
    pytrend = TrendReq(hl='en-US', tz=360)
    
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

        return report

    except Exception as e:
        return f"⚠️ Error analyzing store trends: {str(e)}"
