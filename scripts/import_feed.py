import sys
import os
import requests
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from dotenv import load_dotenv

# Bootstrap: Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from src.paths import PROJECT_ROOT
from src.r2_storage import R2Storage

# Load configurations
load_dotenv(PROJECT_ROOT / "config" / ".env")

def download_file(url, dest_path):
    """Downloads a file from a URL to a local path."""
    print(f"  Downloading: {url}")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    print(f"  ❌ Failed to download: {response.status_code}")
    return False

def migrate_feed(old_rss_url):
    print(f"--- Starting Migration from: {old_rss_url} ---")
    
    # 1. Fetch the old RSS
    response = requests.get(old_rss_url)
    if response.status_code != 200:
        print(f"Could not fetch original RSS. Status: {response.status_code}")
        return

    old_xml = response.text
    
    # 2. Setup Hybrid Storage (R2 for Files, Supabase for DB)
    try:
        from src.podcast_manager import PodcastManager
        manager = PodcastManager()
    except Exception as e:
        print(f"Error initializing PodcastManager: {e}")
        return

    # 3. Parse items from the old RSS
    # Using regex for items to be more resilient with namespaces
    items = re.findall(r'<item>.*?</item>', old_xml, re.DOTALL)
    print(f"Found {len(items)} episodes to migrate.")

    temp_dir = PROJECT_ROOT / "temp_migration"
    temp_dir.mkdir(exist_ok=True)

    imported_count = 0

    for item_xml in reversed(items):  # Process from oldest to newest
        print(f"\nProcessing episode...")
        
        # Extract metadata
        title_match = re.search(r'<title>(.*?)</title>', item_xml, re.DOTALL)
        # Try different description tags (standard, summary, content)
        desc_match = re.search(r'<description>(.*?)</description>', item_xml, re.DOTALL)
        summary_match = re.search(r'<itunes:summary>(.*?)</itunes:summary>', item_xml, re.DOTALL)
        
        url_match = re.search(r'<enclosure.*?url="(.*?)"', item_xml)
        date_match = re.search(r'<pubDate>(.*?)</pubDate>', item_xml)
        duration_match = re.search(r'<itunes:duration>(.*?)</itunes:duration>', item_xml)
        guid_match = re.search(r'<guid.*?>(.*?)</guid>', item_xml)
        thumb_match = re.search(r'<itunes:image.*?href="(.*?)"', item_xml)

        if not all([title_match, url_match]):
            print("  ⚠️ Incomplete episode data. Skipping.")
            continue

        def clean_cdata(text):
            if not text: return ""
            return text.replace("<![CDATA[", "").replace("]]>", "").strip()

        title = clean_cdata(title_match.group(1))
        
        # --- Duplicate Check ---
        if manager.episode_exists(title):
            print(f"  ⏭️ Skipping: '{title}' (Already exists in database)")
            continue

        old_url = url_match.group(1).replace("&amp;", "&")
        old_thumb_url = thumb_match.group(1).replace("&amp;", "&") if thumb_match else None
        pub_date = date_match.group(1) if date_match else None
        duration = duration_match.group(1) if duration_match else ""
        
        # Priority: Description > Summary > Content
        desc_match = re.search(r'<description>(.*?)</description>', item_xml, re.DOTALL)
        summary_match = re.search(r'<itunes:summary>(.*?)</itunes:summary>', item_xml, re.DOTALL)
        content_match = re.search(r'<content:encoded>(.*?)</content:encoded>', item_xml, re.DOTALL)
        
        raw_description = ""
        if desc_match and desc_match.group(1).strip():
            raw_description = desc_match.group(1)
        elif summary_match and summary_match.group(1).strip():
            raw_description = summary_match.group(1)
        elif content_match and content_match.group(1).strip():
            raw_description = content_match.group(1)

        description = clean_cdata(raw_description)
        desc_preview = (description[:50] + "...") if len(description) > 50 else description
        print(f"  Migrating: {title}")
        print(f"  Description: {desc_preview} ({len(description)} chars)")

        # --- Naming Logic ---
        file_id_match = re.search(r'(?:id=|\/d\/)([a-zA-Z0-9_-]{20,})', old_url)
        if file_id_match:
            file_id = file_id_match.group(1)
        elif guid_match:
            file_id = re.sub(r'[^a-zA-Z0-9_-]', '_', guid_match.group(1))[:30]
        else:
            import hashlib
            file_id = hashlib.md5(title.encode()).hexdigest()[:10]

        local_audio_path = temp_dir / f"{file_id}.mp3"

        # 1. Download and Upload Thumbnail to R2
        new_thumb_url = None
        if old_thumb_url:
            thumb_ext = "jpg"
            if ".png" in old_thumb_url.lower(): thumb_ext = "png"
            local_thumb_path = temp_dir / f"{file_id}.{thumb_ext}"
            
            if download_file(old_thumb_url, local_thumb_path):
                print(f"  Uploading Thumbnail to Cloudflare R2...")
                new_thumb_url = manager.upload_file(local_thumb_path, content_type=f'image/{thumb_ext}')
                local_thumb_path.unlink()

        # 2. Download and Upload Audio to R2
        if download_file(old_url, local_audio_path):
            print(f"  Uploading Audio to Cloudflare R2...")
            new_url = manager.upload_file(local_audio_path, content_type='audio/mpeg')
            
            if new_url:
                print(f"  ✅ Uploaded. Updating Supabase Database...")
                episode_data = {
                    "title": title,
                    "description": description,
                    "url": new_url,
                    "pubDate": pub_date,
                    "duration": duration,
                    "image": new_thumb_url
                }
                manager.add_episode(episode_data)
                imported_count += 1
            
            local_audio_path.unlink()
        else:
            print(f"  ❌ Skipping {title} due to download error.")

    print(f"\n✅ MIGRATION FINISHED! {imported_count} episodes processed.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate a podcast feed to Cloudflare R2")
    parser.add_argument("url", nargs="?", help="URL of the source RSS feed")
    
    args = parser.parse_args()
    
    source_url = args.url
    if not source_url:
        print("\n--- Podcast Feed Migration Tool ---")
        source_url = input("Enter the source RSS feed URL: ").strip()
    
    if source_url:
        migrate_feed(source_url)
    else:
        print("No URL provided. Exiting.")
