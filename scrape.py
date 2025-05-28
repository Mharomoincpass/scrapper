import time
import csv
import os
import requests
import re
import shutil
import glob
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from estimate_metrics import run_estimation, DEFAULT_ACTIVE_DAYS

# SETTINGS
KEYWORD = "Odint Consulting Services"
COUNTRY_CODE = "ALL"
NUM_SCROLLS = 3  # Increased to ensure more ads load
OUTPUT_FILE = "meta_ads_ranked.csv"
MEDIA_FOLDER = "ad_media"
DEBUG_LOG = "scrape_errors.csv"

def init_driver():
    """Initialize undetected Chrome driver with specified options."""
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--headless")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.7031.114 Safari/537.36")
    try:
        driver = uc.Chrome(options=options, version_main=136)
        driver.set_page_load_timeout(30)
        print("✅ Chrome driver initialized successfully.")
        return driver
    except Exception as e:
        print(f"⚠️ Error initializing Chrome driver: {e}")
        raise

def parse_active_time(active_time_text):
    """Parse active time text and return days active, defaulting to 1 day for invalid formats."""
    if not active_time_text or active_time_text == "Unknown":
        print(f"⚠️ Empty or unknown active time. Defaulting to 1 day.")
        return 1
    try:
        active_time_text = re.sub(r'http[s]?://\S+|www\.\S+', '', active_time_text).strip()
        if " - " in active_time_text:
            start_date_str, end_date_str = active_time_text.split(" - ")
            start_date = datetime.strptime(start_date_str.strip(), "%d %b %Y")
            end_date = datetime.strptime(end_date_str.split(" · ")[0].strip(), "%d %b %Y")
            days_active = (end_date - start_date).days
            if "Total active time" in active_time_text:
                time_part = active_time_text.split("·")[1].replace("Total active time", "").strip()
                if "hr" in time_part:
                    hours = int(time_part.split()[0])
                    days_active += hours / 24
            return max(days_active, 1)
        elif "Started running on" in active_time_text:
            parts = active_time_text.split("·")
            start_date_str = parts[0].replace("Started running on", "").strip()
            start_date = datetime.strptime(start_date_str, "%d %b %Y")
            current_date = datetime.now()
            days_active = (current_date - start_date).days
            if len(parts) > 1:
                time_part = parts[1].replace("Total active time", "").strip()
                if "hr" in time_part:
                    hours = int(time_part.split()[0])
                    days_active += hours / 24
            return max(days_active, 1)
        else:
            print(f"⚠️ Invalid active time format: '{active_time_text[:50]}...'. Defaulting to 1 day.")
            return 1
    except Exception as e:
        print(f"⚠️ Error parsing active time '{active_time_text[:50]}...': {e}. Defaulting to 1 day.")
        return 1

def extract_page_id(ad_link):
    """Extract page ID from ad link."""
    if not ad_link:
        return "N/A"
    match = re.search(r'facebook\.com/(\d+)/', ad_link)
    if match:
        return match.group(1)
    match = re.search(r'facebook\.com/([^/?]+)', ad_link)
    if match:
        return match.group(1)
    return "N/A"

def get_extension_from_content_type(content_type):
    """Map content type to file extension."""
    mime_to_ext = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "video/mp4": "mp4",
        "video/webm": "webm",
        "video/ogg": "ogv",
        "application/octet-stream": "bin"
    }
    content_type = content_type.lower()
    for mime, ext in mime_to_ext.items():
        if mime in content_type:
            return ext
    print(f"⚠️ Unknown Content-Type '{content_type}'. Defaulting to 'bin'.")
    return "bin"

def download_media(url, folder, filename_base, media_type="image"):
    """Download media (image/video) and save to folder."""
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Failed to download media from {url}: Status code {response.status_code}")
            return False
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        ext = get_extension_from_content_type(content_type)
        filename_base = "".join(c for c in filename_base if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        filename = f"{filename_base}.{ext}"
        filepath = os.path.join(folder, filename)
        counter = 1
        while os.path.exists(filepath):
            filename = f"{filename_base}_{counter}.{ext}"
            filepath = os.path.join(folder, filename)
            counter += 1
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"📥 Saved media: {filepath} (Content-Type: {content_type})")
        return True
    except Exception as e:
        print(f"⚠️ Error downloading media from {url}: {e}")
        return False

def extract_ad_data(ad, index, advertiser_cache):
    """Extract data from a single ad element with retries for dynamic content."""
    try:
        # Wait for ad content to load
        WebDriverWait(ad, 5).until(EC.presence_of_element_located((By.XPATH, './/span')))
        
        # Extract advertiser with broader selectors
        advertiser_elems = ad.find_elements(By.XPATH, './/span[contains(@class, "x1lliihq") or contains(@class, "x193iq5w") or contains(@class, "page")] | .//a[contains(@href, "facebook.com") and not(contains(@href, "fbclid"))] | .//div[contains(@class, "advertiser")]')
        advertiser = "Unknown Advertiser"
        for elem in advertiser_elems:
            text = elem.text.strip()
            if text and len(text) > 2:
                advertiser = text
                break
        
        # Extract ad link
        ad_link_elems = ad.find_elements(By.XPATH, './/a[contains(@href, "facebook.com") or contains(@href, "fbclid")]')
        ad_link = ad_link_elems[0].get_attribute('href') if ad_link_elems else ""
        
        # Extract page ID and update advertiser
        page_id = extract_page_id(ad_link)
        if page_id != "N/A":
            advertiser = page_id
            advertiser_cache[page_id] = advertiser
        
        # Fallback to cached advertiser
        if advertiser == "Unknown Advertiser" and page_id in advertiser_cache:
            advertiser = advertiser_cache[page_id]
        
        # Extract ad text with broader selectors
        ad_text_elems = ad.find_elements(By.XPATH, './/div[contains(@class, "body") or contains(@class, "text") or contains(@class, "content") or contains(@class, "_7jyr") or contains(@class, "description") or contains(@class, "ad-text")]')
        ad_text = ad_text_elems[0].text.replace("\n", " ").strip() if ad_text_elems else "..."
        
        # Extract active time
        active_time_elems = ad.find_elements(By.XPATH, './/span[contains(text(), "Started running on") or contains(text(), " - ")]')
        active_time = active_time_elems[0].text if active_time_elems else "Unknown"
        
        # Extract media with more robust selectors
        image_elems = ad.find_elements(By.XPATH, './/img[@src] | .//div[contains(@style, "background-image")]')
        image_urls = [img.get_attribute('src') for img in image_elems if img.get_attribute('src') and not img.get_attribute('src').endswith('.gif')]
        video_elems = ad.find_elements(By.XPATH, './/video[@src] | .//source[@src]')
        video_urls = [vid.get_attribute('src') for vid in video_elems if vid.get_attribute('src')]
        
        print(f"✔️ Parsed ad #{index}: {advertiser}")
        print(f"   Text: {ad_text[:50]}...")
        print(f"   Link: {ad_link}")
        print(f"   Page ID: {page_id}")
        print(f"   Active Time: {active_time} ({parse_active_time(active_time):.2f} days)")
        print(f"   Images: {len(image_urls)} found")
        print(f"   Videos: {len(video_urls)} found")
        
        return {
            "Advertiser": advertiser,
            "Ad Text": ad_text,
            "Ad Link": ad_link,
            "Active Time": active_time,
            "Image URLs": image_urls,
            "Video URLs": video_urls,
            "Page ID": page_id
        }
    except Exception as e:
        print(f"⚠️ Error collecting raw ad data for ad #{index}: {e}")
        return {
            "Advertiser": "Unknown Advertiser",
            "Ad Text": "...",
            "Ad Link": "",
            "Active Time": "Unknown",
            "Image URLs": [],
            "Video URLs": [],
            "Page ID": "N/A",
            "Error": str(e),
            "Raw HTML": ad.get_attribute("outerHTML")[:500] if ad else "N/A"
        }

def scrape_ads(keyword, country="US"):
    """Scrape ads from Meta Ad Library."""
    driver = None
    advertiser_cache = {}
    error_log = []
    try:
        driver = init_driver()
        search_url = (
            f"https://www.facebook.com/ads/library/?active_status=&ad_type=all"
            f"&country={country}&q={keyword}&sort_data[direction]=desc&sort_data[mode]=relevancy_monthly_grouped&search_type=keyword_unordered"
        )
        print(f"🔍 Searching for ads with keyword: {keyword}")
        driver.get(search_url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("✅ Page loaded successfully.")
        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Allow") or contains(text(), "Accept")]'))
            )
            cookie_btn.click()
            print("🍪 Accepted cookies.")
            time.sleep(1)
        except:
            print("ℹ️ No cookie popup detected.")
        last_ad_count = 0
        for i in range(NUM_SCROLLS):
            driver.execute_script("window.scrollBy(0, 1000);")
            print(f"📜 Scrolling {i+1}/{NUM_SCROLLS}")
            time.sleep(2)  # Increased delay for dynamic content
            ad_elements = driver.find_elements(By.XPATH, '//div[.//span[contains(text(), "Sponsored")]]')
            current_ad_count = len(ad_elements)
            print(f"🔎 Found {current_ad_count} ad(s) after scroll {i+1}")
            if current_ad_count == last_ad_count and i > 0:
                print("ℹ️ No new ads loaded. Stopping scroll.")
                break
            last_ad_count = current_ad_count
        with ThreadPoolExecutor(max_workers=8) as executor:
            raw_ads = list(filter(None, executor.map(lambda x: extract_ad_data(x[0], x[1], advertiser_cache), 
                                                    [(ad, i) for i, ad in enumerate(ad_elements, 1)])))
        ad_text_counts = Counter(ad["Ad Text"] for ad in raw_ads if ad["Ad Text"].strip() and ad["Ad Text"] != "...")
        ad_frequency = {ad_text: count for ad_text, count in ad_text_counts.items()}
        ads = []
        seen_ads = set()
        for index, ad_data in enumerate(raw_ads, start=1):
            try:
                ad_text = ad_data["Ad Text"].strip().lower()
                ad_link = ad_data["Ad Link"]
                page_id = ad_data["Page ID"]
                # Skip ads with insufficient data
                if not ad_text or ad_text == "..." or not ad_link or not (ad_data["Image URLs"] or ad_data["Video URLs"]):
                    print(f"⚠️ Skipping ad #{index}: Incomplete data (Text: {ad_text[:50]}, Link: {ad_link}, Media: {len(ad_data['Image URLs'])} images, {len(ad_data['Video URLs'])} videos)")
                    error_log.append({
                        "Ad Index": index,
                        "Advertiser": ad_data["Advertiser"],
                        "Ad Text": ad_data["Ad Text"][:100],
                        "Ad Link": ad_link,
                        "Page ID": page_id,
                        "Active Time": ad_data["Active Time"][:100],
                        "Error": ad_data.get("Error", "Incomplete data"),
                        "Raw HTML": ad_data.get("Raw HTML", "N/A")
                    })
                    continue
                ad_key = (page_id, ad_text, ad_link)
                if ad_key in seen_ads:
                    continue
                seen_ads.add(ad_key)
                days_active = parse_active_time(ad_data["Active Time"])
                variations = ad_frequency.get(ad_data["Ad Text"], 1) if ad_data["Ad Text"].strip() and ad_data["Ad Text"] != "..." else 1
                ad_entry = {
                    "Advertiser": ad_data["Advertiser"],
                    "Ad Text": ad_data["Ad Text"],
                    "Ad Link": ad_link,
                    "Page ID": page_id,
                    "Active Time": ad_data["Active Time"],
                    "Days Active": days_active,
                    "Ad Variations": variations,
                    "Image URLs": ad_data["Image URLs"],
                    "Video URLs": ad_data["Video URLs"]
                }
                ads.append(ad_entry)
            except Exception as e:
                print(f"⚠️ Error parsing ad #{index}: {e}")
                error_log.append({
                    "Ad Index": index,
                    "Advertiser": ad_data["Advertiser"],
                    "Ad Text": ad_data["Ad Text"][:100],
                    "Ad Link": ad_link,
                    "Page ID": page_id,
                    "Active Time": ad_data["Active Time"][:100],
                    "Error": str(e),
                    "Raw HTML": ad_data.get("Raw HTML", "N/A")
                })
        if error_log:
            with open(DEBUG_LOG, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["Ad Index", "Advertiser", "Ad Text", "Ad Link", "Page ID", "Active Time", "Error", "Raw HTML"])
                writer.writeheader()
                writer.writerows(error_log)
            print(f"📁 Saved {len(error_log)} problematic ads to {DEBUG_LOG}")
        return ads
    finally:
        if driver is not None:
            try:
                time.sleep(1)
                driver.quit()
                print("✅ Driver closed successfully.")
            except Exception as e:
                print(f"ℹ️ Non-critical error during driver cleanup: {e}. Continuing execution.")

def save_to_csv(data, filename):
    """Save ad data to CSV."""
    if not data:
        print("⚠️ No data to save.")
        return
    csv_data = [{k: v for k, v in ad.items() if k not in ["Image URLs", "Video URLs"]} for ad in data]
    for row in csv_data:
        for key, value in row.items():
            if isinstance(value, str):
                row[key] = value.replace('\n', ' ').replace('\r', ' ')
    try:
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys(), quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(csv_data)
        print(f"📁 Saved {len(data)} ads to {filename}")
    except Exception as e:
        print(f"⚠️ Error saving to CSV: {e}")

def download_all_media(ad, ad_index):
    """Download all media for an ad."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for j, img_url in enumerate(ad["Image URLs"], 1):
            filename_base = f"ad_{ad_index}_{ad['Advertiser']}_image_{j}"
            futures.append(executor.submit(download_media, img_url, MEDIA_FOLDER, filename_base, "image"))
        for j, vid_url in enumerate(ad["Video URLs"], 1):
            filename_base = f"ad_{ad_index}_{ad['Advertiser']}_video_{j}"
            futures.append(executor.submit(download_media, vid_url, MEDIA_FOLDER, filename_base, "video"))
        for future in futures:
            future.result()

def show_top_5_ads(ads):
    """Display and save media for top 5 ads based on hours active, ensuring all have media."""
    if not ads:
        print("⚠️ No ads to rank.")
        return []

    for ad in ads:
        days_active = ad["Days Active"] if ad["Days Active"] > 0 else DEFAULT_ACTIVE_DAYS
        ad["Hours Active"] = days_active * 24

    sorted_ads = sorted(ads, key=lambda x: x["Hours Active"], reverse=True)
    top_ads = []
    seen_keys = set()

    for ad in sorted_ads:
        ad_key = (ad["Ad Text"][:100], ad["Ad Link"], ad["Active Time"])
        # Only include ads with at least one image or video
        if ad_key not in seen_keys and (ad["Image URLs"] or ad["Video URLs"]):
            top_ads.append(ad)
            seen_keys.add(ad_key)
        if len(top_ads) == 5:
            break

    if not top_ads:
        print("⚠️ No valid ads with media to display after filtering.")
        return []

    print("\n🏆 Top 5 Ads Based on Hours Active in Meta Ad Library:")
    for i, ad in enumerate(top_ads, 1):
        print(f"{i}. Advertiser: {ad['Advertiser']}")
        print(f"   Ad Text: {ad['Ad Text'][:100]}...")
        print(f"   Ad Link: {ad['Ad Link']}")
        print(f"   Page ID: {ad['Page ID']}")
        print(f"   Active Time: {ad['Active Time']} ({ad['Hours Active']:.2f} hours active)")
        print(f"   Ad Variations: {ad['Ad Variations']}")
        print(f"   Images: {len(ad['Image URLs'])} found")
        print(f"   Videos: {len(ad['Video URLs'])} found")
        download_all_media(ad, i)
    
    return top_ads

if __name__ == "__main__":
    if os.path.exists(MEDIA_FOLDER):
        try:
            shutil.rmtree(MEDIA_FOLDER)
            print(f"🗑️ Cleared {MEDIA_FOLDER} folder.")
        except Exception as e:
            print(f"⚠️ Error clearing {MEDIA_FOLDER} folder: {e}")
    os.makedirs(MEDIA_FOLDER, exist_ok=True)
    print(f"📁 Created empty {MEDIA_FOLDER} folder.")

    csv_files = glob.glob("*.csv")
    for csv_file in csv_files:
        try:
            os.remove(csv_file)
            print(f"🗑️ Deleted CSV file: {csv_file}")
        except Exception as e:
            print(f"⚠️ Error deleting CSV file {csv_file}: {e}")

    ad_data = scrape_ads(KEYWORD, COUNTRY_CODE)
    save_to_csv(ad_data, OUTPUT_FILE)
    top_5_ads = show_top_5_ads(ad_data)
    print("\n📊 Running ad metrics estimation...")
    run_estimation(top_5_ads)