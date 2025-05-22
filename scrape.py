import time
import csv
import os
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import re
from collections import Counter

# SETTINGS
KEYWORD = "Spain Incorporation"
COUNTRY_CODE = "India"
NUM_SCROLLS = 3
OUTPUT_FILE = "meta_ads_ranked.csv"
MEDIA_FOLDER = "ad_media"

def init_driver():
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.7031.114 Safari/537.36")
    driver = uc.Chrome(options=options, version_main=136)
    driver.set_page_load_timeout(30)
    return driver

def parse_active_time(active_time_text):
    """Parse active time text and calculate days active."""
    try:
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
            return max(days_active, 0)
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
            return max(days_active, 0)
        else:
            print(f"⚠️ Invalid active time format: '{active_time_text}'. Treating as 0 days.")
            return 0
    except Exception as e:
        print(f"⚠️ Error parsing active time '{active_time_text}': {e}. Treating as 0 days.")
        return 0

def extract_page_id(ad_link):
    """Extract the page_id from a Facebook Ad Link if possible."""
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
    """Determine file extension based on Content-Type header."""
    mime_to_ext = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "video/mp4": "mp4",
        "video/webm": "webm",
        "video/ogg": "ogv"
    }
    content_type = content_type.lower()
    for mime, ext in mime_to_ext.items():
        if mime in content_type:
            return ext
    print(f"⚠️ Unknown Content-Type '{content_type}'. Defaulting to 'bin'.")
    return "bin"  # Default extension for unknown types

def download_media(url, folder, filename_base, media_type="image"):
    """Download media (image or video) from URL and save to folder with correct extension."""
    try:
        # Create media folder if it doesn't exist
        if not os.path.exists(folder):
            os.makedirs(folder)

        # Download the media and get the Content-Type
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Failed to download media from {url}: Status code {response.status_code}")
            return False

        # Determine the correct extension based on Content-Type
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        ext = get_extension_from_content_type(content_type)

        # Sanitize the filename base (without extension)
        filename_base = "".join(c for c in filename_base if c.isalnum() or c in (' ', '_', '-')).strip()
        filename = f"{filename_base}.{ext}"
        filepath = os.path.join(folder, filename)

        # Save the file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"📥 Saved media: {filepath} (Content-Type: {content_type})")
        return True

    except Exception as e:
        print(f"⚠️ Error downloading media from {url}: {e}")
        return False

def scrape_ads(keyword, country="US"):
    driver = init_driver()
    search_url = (
        f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all"
        f"&country={country}&q={keyword}&sort_data[direction]=desc&sort_data[mode]=relevancy_monthly_grouped&search_type=keyword_unordered"
    )
    print(f"🔍 Searching for ads with keyword: {keyword}")
    driver.get(search_url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("✅ Page loaded successfully.")
    except Exception as e:
        print(f"⚠️ Page load timeout: {e}")
        driver.quit()
        return []

    try:
        cookie_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Allow") or contains(text(), "Accept")]'))
        )
        cookie_btn.click()
        print("🍪 Accepted cookies.")
        time.sleep(2)
    except:
        print("ℹ️ No cookie popup detected.")

    last_ad_count = 0
    for i in range(NUM_SCROLLS):
        driver.execute_script("window.scrollBy(0, 1000);")
        print(f"📜 Scrolling {i+1}/{NUM_SCROLLS}")
        time.sleep(2)

        ad_elements = driver.find_elements(By.XPATH, '//div[.//span[contains(text(), "Sponsored")]]')
        current_ad_count = len(ad_elements)
        print(f"🔎 Found {current_ad_count} ad(s) after scroll {i+1}")
        if current_ad_count == last_ad_count and i > 0:
            print("ℹ️ No new ads loaded. Stopping scroll.")
            break
        last_ad_count = current_ad_count

    with open("page_source.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("📝 Saved page source to 'page_source.html' for debugging.")

    # Collect all ads to count variations and frequency
    raw_ads = []
    for ad in ad_elements:
        try:
            advertiser_elem = ad.find_elements(By.XPATH, './/span[contains(@class, "x1lliihq") or contains(@class, "x193iq5w") or contains(@class, "page")]')
            advertiser = advertiser_elem[0].text if advertiser_elem else "Unknown Advertiser"

            ad_text_elem = ad.find_elements(By.XPATH, './/div[contains(@class, "body") or contains(@class, "text") or contains(@class, "content") or contains(@class, "_7jyr") or contains(@class, "description")]')
            ad_text = ad_text_elem[0].text.replace("\n", " ") if ad_text_elem else ""

            ad_link_elem = ad.find_elements(By.XPATH, './/a[contains(@class, "link") or contains(@href, "fbclid") or contains(@href, "facebook.com")]')
            ad_link = ad_link_elem[0].get_attribute('href') if ad_link_elem else ""

            active_time_elem = ad.find_elements(By.XPATH, './/span[contains(text(), "Started running on") or contains(text(), " - ")]')
            active_time = active_time_elem[0].text if active_time_elem else "Unknown"

            # Extract image URLs
            image_elems = ad.find_elements(By.XPATH, './/img[@src]')
            image_urls = [img.get_attribute('src') for img in image_elems if img.get_attribute('src') and not img.get_attribute('src').endswith('.gif')]

            # Extract video URLs (if any)
            video_elems = ad.find_elements(By.XPATH, './/video[@src]')
            video_urls = [vid.get_attribute('src') for vid in video_elems if vid.get_attribute('src')]

            raw_ads.append({
                "Advertiser": advertiser,
                "Ad Text": ad_text,
                "Ad Link": ad_link,
                "Active Time": active_time,
                "Image URLs": image_urls,
                "Video URLs": video_urls
            })
        except Exception as e:
            print(f"⚠️ Error collecting raw ad data: {e}")

    # Count ad variations and frequency
    ad_text_counts = Counter(ad["Ad Text"] for ad in raw_ads if ad["Ad Text"].strip())
    ad_frequency = {ad_text: count for ad_text, count in ad_text_counts.items()}

    ads = []
    seen_ads = set()  # Track unique ads by (Ad Text, Ad Link)
    for index, ad_data in enumerate(raw_ads, start=1):
        try:
            ad_text = ad_data["Ad Text"]
            ad_link = ad_data["Ad Link"]
            ad_key = (ad_text, ad_link)
            if ad_key in seen_ads:
                continue
            seen_ads.add(ad_key)

            days_active = parse_active_time(ad_data["Active Time"])
            page_id = extract_page_id(ad_link)
            variations = ad_frequency.get(ad_text, 1)  # Number of times this ad text appears

            ads.append({
                "Advertiser": ad_data["Advertiser"],
                "Ad Text": ad_text,
                "Ad Link": ad_link,
                "Page ID": page_id,
                "Active Time": ad_data["Active Time"],
                "Days Active": days_active,
                "Ad Variations": variations,
                "Image URLs": ad_data["Image URLs"],
                "Video URLs": ad_data["Video URLs"]
            })
            print(f"✔️ Parsed ad #{index}: {ad_data['Advertiser']}")
            print(f"   Text: {ad_text[:50]}...")
            print(f"   Link: {ad_link}")
            print(f"   Page ID: {page_id}")
            print(f"   Active Time: {ad_data['Active Time']} ({चेdays_active:.2f} days)")
            print(f"   Ad Variations: {variations} (proxy for testing/optimization)")
            print(f"   Images: {len(ad_data['Image URLs'])} found")
            print(f"   Videos: {len(ad_data['Video URLs'])} found")
            print("⚠️ Note: Direct ad engagement metrics are not available via Meta APIs due to privacy restrictions.")
            print("ℹ️ Use 'Days Active' as primary metric for ad performance.")
        except Exception as e:
            print(f"⚠️ Error parsing ad #{index}: {e}")

    try:
        driver.quit()
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ Error during driver cleanup: {e}")

    return ads

def save_to_csv(data, filename):
    if not data:
        print("⚠️ No data to save.")
        return

    # Remove Image URLs and Video URLs from CSV to avoid clutter
    csv_data = [{k: v for k, v in ad.items() if k not in ["Image URLs", "Video URLs"]} for ad in data]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"📁 Saved {len(data)} ads to {filename}")

def show_top_5_ads(ads):
    if not ads:
        print("⚠️ No ads to rank.")
        return

    filtered_ads = [ad for ad in ads if ad["Ad Text"].strip()]
    if not filtered_ads:
        print("⚠️ No ads with valid text to rank.")
        return

    # Sort by Days Active (descending) only
    sorted_ads = sorted(filtered_ads, key=lambda x: x["Days Active"], reverse=True)

    top_ads = []
    seen_links = set()
    for ad in sorted_ads:
        if ad["Ad Link"] not in seen_links:
            top_ads.append(ad)
            seen_links.add(ad["Ad Link"])
        if len(top_ads) == 5:
            break

    print("\n🏆 Top 5 Ads Based on Active Time in Meta Ad Library:")
    for i, ad in enumerate(top_ads, 1):
        print(f"{i}. Advertiser: {ad['Advertiser']}")
        print(f"   Ad Text: {ad['Ad Text'][:100]}...")
        print(f"   Ad Link: {ad['Ad Link']}")
        print(f"   Page ID: {ad['Page ID']}")
        print(f"   Active Time: {ad['Active Time']} ({ad['Days Active']:.2f} days active)")
        print(f"   Ad Variations: {ad['Ad Variations']} (proxy for testing/optimization)")
        print(f"   Images: {len(ad['Image URLs'])} found")
        print(f"   Videos: {len(ad['Video URLs'])} found")
        print("⚠️ Note: Direct ad engagement metrics are not available; using 'Days Active' as primary metric.\n")

        # Download images
        for j, img_url in enumerate(ad["Image URLs"], 1):
            filename_base = f"ad_{i}_{ad['Advertiser']}_image_{j}"
            download_media(img_url, MEDIA_FOLDER, filename_base, media_type="image")

        # Download videos
        for j, vid_url in enumerate(ad["Video URLs"], 1):
            filename_base = f"ad_{i}_{ad['Advertiser']}_video_{j}"
            download_media(vid_url, MEDIA_FOLDER, filename_base, media_type="video")

if __name__ == "__main__":
    ad_data = scrape_ads(KEYWORD, COUNTRY_CODE)
    save_to_csv(ad_data, OUTPUT_FILE)
    show_top_5_ads(ad_data)