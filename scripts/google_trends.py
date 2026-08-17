import pandas as pd
import re
import os
from pytrends.request import TrendReq

def clean_keyword(text):
    clean_text = re.sub(r'[^\w\s]', '', text)
    words = clean_text.split()
    return " ".join(words[:2]) if words else "product"

def get_top_regions_and_excel(keywords):
    pytrend = TrendReq(hl='en-US', tz=360)
    clean_kw_list = [clean_keyword(kw) for kw in keywords[:5]]
    clean_kw_list = list(dict.fromkeys(clean_kw_list))

    try:
        # Low volume regions filter out & global payload
        pytrend.build_payload(kw_list=clean_kw_list, timeframe='today 12-m')
        df_region = pytrend.interest_by_region(resolution='COUNTRY', inc_low_vol=False)
        
        excel_path = "google_trends_report.xlsx"
        df_region.to_excel(excel_path)

        report = "🌍 **Worldwide Top Searching Regions (Sorted by Search Demand):**\n\n"
        for kw in clean_kw_list:
            if kw in df_region.columns:
                # Filter zero values and sort properly by highest search score
                non_zero = df_region[df_region[kw] > 0]
                top_countries = non_zero.sort_values(by=kw, ascending=False).head(5)
                
                report += f"🔹 **{kw}**:\n"
                if not top_countries.empty:
                    for country, row in top_countries.iterrows():
                        report += f"  • {country}: {row[kw]}/100\n"
                else:
                    report += "  • High search volume limited to specific local regions.\n"
                report += "\n"

        return report, excel_path

    except Exception as e:
        return f"⚠️ Error fetching regional data: {str(e)}", None

def get_seo_keywords_for_products(keywords):
    """ Fetch top related keywords for SEO suggestion """
    pytrend = TrendReq(hl='en-US', tz=360)
    clean_kw_list = [clean_keyword(kw) for kw in keywords[:5]]
    
    seo_data = {}
    for kw in clean_kw_list:
        try:
            pytrend.build_payload(kw_list=[kw], timeframe='today 12-m')
            related = pytrend.related_queries()
            if kw in related and related[kw]['top'] is not None:
                queries = related[kw]['top']['query'].head(5).tolist()
                seo_data[kw] = queries
            else:
                seo_data[kw] = [f"best {kw}", f"buy {kw} online", f"affordable {kw}"]
        except Exception:
            seo_data[kw] = [f"best {kw}", f"buy {kw} online", f"trending {kw}"]
            
    return seo_data
