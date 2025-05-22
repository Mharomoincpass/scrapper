Meta Ad Library Scraper
Overview
This Python script scrapes advertisements from the Meta Ad Library using a specified keyword and country code. It extracts ad details such as the advertiser, ad text, ad link, active time, and media (images and videos), ranks the top 5 ads by their active duration, and saves the results to a CSV file. Additionally, it downloads media files for the top 5 ads to a designated folder.

Features

Scrapes Ads: Fetches ads from the Meta Ad Library based on a keyword and country code.
Extracts Details: Collects ad metadata including advertiser, ad text, ad link, page ID, active time, days active, and ad variations.
Downloads Media: Saves images and videos for the top 5 ads, ranked by active duration.
Saves to CSV: Exports ad metadata to meta_ads_ranked.csv.
Organizes Media: Stores media files in the ad_media folder with proper extensions based on content type.
Handles Interactions: Manages cookie popups and scrolls to load more ads.
Robust Error Handling: Includes error handling for reliable scraping.


Requirements

Python: Version 3.6 or higher.
Dependencies:Install the required packages using pip:pip install undetected-chromedriver requests


Chrome Browser: Ensure Chrome is installed, as undetected_chromedriver requires it. The script targets Chrome version 136 (specified via version_main=136).
Internet Connection: Needed to access the Meta Ad Library and download media.


Setup

Clone or Download the Script:

Save the script as meta_ad_scraper.py (or your preferred name).


Install Dependencies:

Run the following command to install the required packages:pip install undetected-chromedriver requests




Verify Chrome Installation:

Ensure Chrome is installed and compatible with version 136. If Chrome updates cause compatibility issues, adjust the version_main parameter in the init_driver() function.




Usage

Configure Settings:

Open the script and modify the SETTINGS section as needed:KEYWORD = "Spain Incorporation"  # Keyword to search for ads
COUNTRY_CODE = "India"          # Country code for ad search (e.g., "US", "India")
NUM_SCROLLS = 3                 # Number of scrolls to load more ads
OUTPUT_FILE = "meta_ads_ranked.csv"  # Output CSV file for ad metadata
MEDIA_FOLDER = "ad_media"       # Folder to store downloaded media




Run the Script:

Execute the script using Python:python meta_ad_scraper.py




Monitor Output:

The script will print progress messages, including:
Number of ads found after each scroll.
Details of each parsed ad (advertiser, text, link, etc.).
Top 5 ads ranked by active duration.
Paths of saved media files.






Output
CSV File
Ad metadata is saved to meta_ads_ranked.csv with the following columns:

Advertiser: Name of the advertiser.
Ad Text: Text content of the ad.
Ad Link: URL of the ad.
Page ID: Extracted page ID from the ad link.
Active Time: Ad's active duration (e.g., "Started running on 1 Jan 2025").
Days Active: Calculated days the ad has been active.
Ad Variations: Number of variations of the ad (proxy for testing/optimization).

Media Files

Images and videos for the top 5 ads are saved to the ad_media folder.
Filenames follow the format: ad_{rank}_{advertiser}_{media_type}_{index}.{ext}
Example: ad_1_Unknown_Advertiser_image_1.jpg


Extensions are determined dynamically based on the Content-Type header (e.g., .jpg, .png, .mp4).

Debugging
The script saves the page source to page_source.html for debugging purposes.

Example Output
🔍 Searching for ads with keyword: Spain Incorporation
✅ Page loaded successfully.
🍪 Accepted cookies.
📜 Scrolling 1/3
🔎 Found 10 ad(s) after scroll 1
...
✔️ Parsed ad #1: Unknown Advertiser
   Text: Incorporate your business in Spain...
   Link: https://facebook.com/123456789
   Page ID: 123456789
   Active Time: Started running on 1 Jan 2025 (141.67 days)
   Ad Variations: 2
   Images: 2 found
   Videos: 0 found
...
📝 Saved page source to 'page_source.html'
📁 Saved 10 ads to meta_ads_ranked.csv

🏆 Top 5 Ads Based on Active Time in Meta Ad Library:
1. Advertiser: Unknown Advertiser
   Ad Text: Incorporate your business in Spain...
   Ad Link: https://facebook.com/123456789
   Page ID: 123456789
   Active Time: Started running on 1 Jan 2025 (141.67 days active)
   Ad Variations: 2
   Images: 2 found
   Videos: 0 found
📥 Saved media: ad_media/ad_1_Unknown_Advertiser_image_1.jpg (Content-Type: image/jpeg)
📥 Saved media: ad_media/ad_1_Unknown_Advertiser_image_2.png (Content-Type: image/png)
...


Troubleshooting
No Ads Found

Ensure the KEYWORD and COUNTRY_CODE are valid and yield results in the Meta Ad Library.
Check page_source.html to verify if ads are present on the page.
Increase NUM_SCROLLS to load more ads.

Media Not Downloading

Verify the URLs extracted for images and videos are valid (check page_source.html).
Meta might block automated downloads; consider adding delays or rotating user agents.
If files are too small (e.g., 1 KB), they might be thumbnails. Adjust the XPath in scrape_ads() to target full-size media.

Chrome Version Mismatch

If undetected_chromedriver fails, ensure your Chrome version is compatible with version_main=136. Update the version_main parameter if needed.

CAPTCHAs

Meta may detect automation and show CAPTCHAs. undetected_chromedriver helps, but you might need to handle CAPTCHAs manually or use a CAPTCHA-solving service.

File Extension Issues

The script determines extensions based on the Content-Type header. If the extension is incorrect, check the logged Content-Type and adjust get_extension_from_content_type() if needed.


Limitations

Privacy Restrictions: Direct ad engagement metrics (e.g., clicks, impressions) are not available due to Meta's privacy policies. The script uses "Days Active" as a proxy for ad performance.
Dynamic Content: Some ads may load media dynamically via JavaScript, requiring additional handling to extract playable video URLs or high-resolution images.
Rate Limits: Meta may impose rate limits or block automated requests, especially for media downloads.
Media Quality: The script might download thumbnails instead of full-size images. You may need to refine the XPath selectors to target higher-quality media.


License
Owned by Growcliq and Ondemand International
#gang gang
