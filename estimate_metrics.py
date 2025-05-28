import csv
import os
import tempfile
import shutil
from transformers import pipeline
from deep_translator import GoogleTranslator
from langdetect import detect

# Benchmark Lookup Table (in INR)
BENCHMARKS = {
    "Apparel": {"CPC": 27.00, "CTR": 0.0184, "ConvRate": 0.039, "AOV": 4500.00},
    "Finance & Insurance": {"CPC": 226.20, "CTR": 0.0111, "ConvRate": 0.0525, "AOV": 51000.00},
    "B2B SaaS": {"CPC": 151.20, "CTR": 0.0078, "ConvRate": 0.028, "AOV": 60000.00},
    "Healthcare": {"CPC": 79.20, "CTR": 0.0098, "ConvRate": 0.035, "AOV": 6600.00},
    "E-commerce": {"CPC": 39.00, "CTR": 0.0145, "ConvRate": 0.042, "AOV": 7200.00},
    "Education": {"CPC": 66.00, "CTR": 0.0085, "ConvRate": 0.03, "AOV": 12000.00},
    "Travel & Hospitality": {"CPC": 57.00, "CTR": 0.013, "ConvRate": 0.038, "AOV": 18000.00},
    "Real Estate": {"CPC": 100.80, "CTR": 0.009, "ConvRate": 0.025, "AOV": 90000.00},
    "Digital Marketing Services": {"CPC": 120.00, "CTR": 0.0100, "ConvRate": 0.035, "AOV": 30000.00},
    "IT Staffing & Recruitment": {"CPC": 90.00, "CTR": 0.0090, "ConvRate": 0.040, "AOV": 24000.00},
    "Software Training": {"CPC": 60.00, "CTR": 0.0090, "ConvRate": 0.035, "AOV": 15000.00},
    "Web Hosting & Domains": {"CPC": 80.00, "CTR": 0.0080, "ConvRate": 0.030, "AOV": 12000.00},
    "Freelance Software Development": {"CPC": 100.00, "CTR": 0.0085, "ConvRate": 0.032, "AOV": 36000.00},
    "Business Consulting & Services": {"CPC": 150.00, "CTR": 0.0090, "ConvRate": 0.025, "AOV": 300000.00},
    "Software Development": {"CPC": 80.00, "CTR": 0.009, "ConvRate": 0.035, "AOV": 30000.00}
}

# Default fallback metrics (in INR)
DEFAULT_CPC = 31.66
DEFAULT_CTR = 0.01
DEFAULT_CONVERSION_RATE = 0.02
DEFAULT_AOV = 60000
OUTPUT_FILE = "ad_metrics_estimates.csv"
CONFIDENCE_THRESHOLD = 0.3
DEFAULT_ACTIVE_DAYS = 1.0
translation_cache = {}

try:
    classifier = pipeline("zero-shot-classification", 
                         model="valhalla/distilbart-mnli-12-3", 
                         tokenizer="valhalla/distilbart-mnli-12-3")
    INDUSTRIES = list(BENCHMARKS.keys())
except Exception as e:
    print(f"⚠️ Error loading HuggingFace model: {e}. Falling back to default metrics.")
    classifier = None

def preprocess_text(text, advertiser=""):
    """Preprocess ad text, translate non-English text, and handle short/empty text."""
    cache_key = (text, advertiser)
    if cache_key in translation_cache:
        return translation_cache[cache_key]
    if not text or text.strip() == "..." or len(text.strip()) < 10:
        result = f"Business consulting ad by {advertiser}" if advertiser and advertiser != "Unknown Advertiser" else "Generic business consulting ad"
    else:
        try:
            lang = detect(text)
            if lang != 'en':
                translated = GoogleTranslator(source='auto', target='en').translate(text)
                result = f"{translated.strip()} by {advertiser}" if advertiser and advertiser != "Unknown Advertiser" else translated.strip()
            else:
                result = f"{text.strip()} by {advertiser}" if advertiser and advertiser != "Unknown Advertiser" else text.strip()
        except Exception as e:
            print(f"⚠️ Translation error for text '{text[:50]}...': {e}")
            result = f"{text.strip()} by {advertiser}" if advertiser and advertiser != "Unknown Advertiser" else text.strip()
    translation_cache[cache_key] = result
    return result

def predict_industry(ad_texts, advertisers):
    """Classify ad texts into industries using zero-shot classification."""
    ad_texts = [preprocess_text(text, adv) for text, adv in zip(ad_texts, advertisers)]
    if classifier is None:
        return [{"Industry": "Software Development", "Confidence": 0.0, "Note": "Manual review needed - No classifier"}] * len(ad_texts)
    try:
        results = classifier(ad_texts, candidate_labels=INDUSTRIES, multi_label=False)
        if isinstance(results, dict):
            results = [results]
        return [{
            "Industry": result["labels"][0], 
            "Confidence": result["scores"][0],
            "Note": f"Low confidence ({result['scores'][0]:.2f}) - Manual review needed" if result["scores"][0] < CONFIDENCE_THRESHOLD else ""
        } for result in results]
    except Exception as e:
        print(f"⚠️ Error classifying ad texts: {e}")
        return [{"Industry": "Software Development", "Confidence": 0.0, "Note": "Manual review needed - Classification error"}] * len(ad_texts)

def estimate_metrics(ads):
    """Estimate performance metrics for each ad based on industry benchmarks."""
    if not ads:
        print("⚠️ No ads to estimate metrics for.")
        return []
    print(f"ℹ️ Estimating metrics for {len(ads)} unique ads")
    results = []
    low_confidence_ads = []
    seen_ads = set()
    
    ad_texts = [ad.get("Ad Text", "Business consulting ad by {ad['Advertiser']}") for ad in ads]
    advertisers = [ad.get("Advertiser", "Unknown Advertiser") for ad in ads]
    industry_infos = predict_industry(ad_texts, advertisers)
    
    if len(industry_infos) != len(ads):
        print(f"⚠️ Mismatch in industry_infos ({len(industryInfos)}) and ads ({len(ads)}). Using default industry.")
        industry_infos = [{"Industry": "Software Development", "Confidence": 0.0, "Note": "Manual review needed - Classification error"}] * len(ads)
    
    for i, ad in enumerate(ads):
        print(f"Processing ad {i+1}: Advertiser={ad.get('Advertiser', 'Unknown')}, Ad Text={ad.get('Ad Text', '...')[:50]}...")
        if ad.get("Advertiser") == "Unknown Advertiser":
            print(f"Skipping ad {i+1}: Invalid advertiser")
            continue
        
        ad_key = (ad.get("Advertiser"), ad.get("Ad Text", "...")[:100])
        if ad_key in seen_ads:
            print(f"Skipping ad {i+1}: Duplicate ad")
            continue
        seen_ads.add(ad_key)
        
        industry_info = industry_infos[i]
        industry = industry_info["Industry"]
        
        if industry in BENCHMARKS and industry != "Unclassified":
            cpc = BENCHMARKS[industry]["CPC"]
            ctr = BENCHMARKS[industry]["CTR"]
            conv_rate = BENCHMARKS[industry]["ConvRate"]
            aov = BENCHMARKS[industry]["AOV"]
        else:
            cpc = DEFAULT_CPC
            ctr = DEFAULT_CTR
            conv_rate = DEFAULT_CONVERSION_RATE
            aov = DEFAULT_AOV
            low_confidence_ads.append({
                "Advertiser": ad.get("Advertiser"),
                "Ad Text": ad.get("Ad Text", "..."),
                "Confidence": industry_info["Confidence"],
                "Note": industry_info["Note"]
            })
        
        days_active = ad.get("Days Active", DEFAULT_ACTIVE_DAYS)
        impressions = days_active * ad.get("Ad Variations", 1) * 223  # Rule-based estimation
        clicks = impressions * ctr
        spend = clicks * cpc
        conversions = clicks * conv_rate
        revenue = conversions * aov
        roas = revenue / spend if spend > 0 else 0
        
        result = {
            "Advertiser": ad.get("Advertiser"),
            "Industry": industry,
            "CPC": round(cpc, 2),
            "CTR": round(ctr * 100, 2),
            "Conversion Rate": round(conv_rate * 100, 2),
            "Estimated Spend (INR)": round(spend, 2),
            "Estimated Reach": round(impressions, 2),
            "ROAS": round(roas, 2),
            "Note": industry_info.get("Note", "")
        }
        results.append(result)
        print(f"Added result for ad {i+1}: Industry={industry}, Spend=₹{spend:.2f}")
    
    if low_confidence_ads:
        with open("low_confidence_ads.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["Advertiser", "Ad Text", "Confidence", "Note"])
            writer.writeheader()
            writer.writerows(low_confidence_ads)
        print(f"📁 Saved {len(low_confidence_ads)} low-confidence ads to low_confidence_ads.csv")
    
    print(f"ℹ️ Total valid estimates: {len(results)}")
    return results

def save_metrics_to_csv(data, filename):
    """Save enriched ad data to CSV."""
    if not data:
        print("⚠️ No data to save.")
        return
    fieldnames = ["Advertiser", "Industry", "CPC", "CTR", "Conversion Rate", 
                  "Estimated Spend (INR)", "Estimated Reach", "ROAS", "Note"]
    try:
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(data)
        print(f"📁 Saved {len(data)} estimates to {filename}")
    except PermissionError as e:
        print(f"⚠️ Permission denied when writing to {filename}: {e}")
        temp_fd, temp_path = tempfile.mkstemp(suffix=".csv", text=True)
        try:
            with os.fdopen(temp_fd, "w", newline="", encoding="utf-8-sig") as temp_file:
                writer = csv.DictWriter(temp_file, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
                writer.writeheader()
                writer.writerows(data)
            shutil.move(temp_path, filename)
            print(f"📁 Successfully saved to {filename} via temporary file")
        except Exception as temp_error:
            print(f"⚠️ Failed to save via temporary file: {temp_error}")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

def run_estimation(ads):
    """Main function to run estimation and save results."""
    print(f"ℹ️ Running estimation for {len(ads)} ads")
    metrics = estimate_metrics(ads)
    print(f"ℹ️ Metrics calculated: {len(metrics)} entries")
    save_metrics_to_csv(metrics, OUTPUT_FILE)
    print("\n📊 Ad Metrics Estimates:")
    for i, metric in enumerate(metrics, 1):
        try:
            print(f"Ad #{i}:")
            print(f"  Advertiser: {metric['Advertiser']}")
            print(f"  Industry: {metric['Industry']}")
            print(f"  CPC: ₹{metric['CPC']:.2f}")
            print(f"  CTR: {metric['CTR']:.2f}%")
            print(f"  Conversion Rate: {metric['Conversion Rate']:.2f}%")
            print(f"  Estimated Spend: ₹{metric['Estimated Spend (INR)']:.2f}")
            print(f"  Estimated Reach: {metric['Estimated Reach']:.2f}")
            print(f"  ROAS: {metric['ROAS']:.2f}x")
            if metric["Note"]:
                print(f"  Note: {metric['Note']}")
            print()
        except KeyError as e:
            print(f"⚠️ Error displaying metric for Ad #{i}: Missing key {e}")
    return metrics

if __name__ == "__main__":
    from scrape import scrape_ads
    ads = scrape_ads("Fermented durian", "ALL")
    run_estimation(ads)