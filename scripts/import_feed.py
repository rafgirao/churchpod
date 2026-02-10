import sys
import os
import re
import hashlib
import requests
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


def clean_cdata(text):
    """Strips CDATA wrappers from XML text."""
    if not text:
        return ""
    return text.replace("<![CDATA[", "").replace("]]>", "").strip()


def extract_description(item_xml):
    """Extracts the best available description from an RSS item. Priority: description > summary > content."""
    for tag in ['description', 'itunes:summary', 'content:encoded']:
        match = re.search(rf'<{tag}>(.*?)</{tag}>', item_xml, re.DOTALL)
        if match and match.group(1).strip():
            return clean_cdata(match.group(1))
    return ""


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
    items = re.findall(r'<item>.*?</item>', old_xml, re.DOTALL)
    print(f"Found {len(items)} episodes to migrate.")

    temp_dir = PROJECT_ROOT / "temp_migration"
    temp_dir.mkdir(exist_ok=True)

    imported_count = 0

    for item_xml in reversed(items):  # Process from oldest to newest
        print("\nProcessing episode...")
        
        # Extract metadata
        title_match = re.search(r'<title>(.*?)</title>', item_xml, re.DOTALL)
        url_match = re.search(r'<enclosure.*?url="(.*?)"', item_xml)
        date_match = re.search(r'<pubDate>(.*?)</pubDate>', item_xml)
        duration_match = re.search(r'<itunes:duration>(.*?)</itunes:duration>', item_xml)
        guid_match = re.search(r'<guid.*?>(.*?)</guid>', item_xml)
        thumb_match = re.search(r'<itunes:image.*?href="(.*?)"', item_xml)

        if not all([title_match, url_match]):
            print("  ⚠️ Incomplete episode data. Skipping.")
            continue

        title = clean_cdata(title_match.group(1))
        old_url = url_match.group(1).replace("&amp;", "&")
        old_thumb_url = thumb_match.group(1).replace("&amp;", "&") if thumb_match else None
        pub_date = date_match.group(1) if date_match else None
        duration = duration_match.group(1) if duration_match else ""
        description = extract_description(item_xml)

        desc_preview = (description[:50] + "...") if len(description) > 50 else description
        print(f"  Migrating: {title}")
        print(f"  Description: {desc_preview} ({len(description)} chars)")

        # --- Duplicate Check & Metadata Update ---
        existing_episode = manager.get_episode_by_title(title)
        if existing_episode:
            print(f"  🔄 Episode already exists. Updating metadata (including pubDate: {pub_date})...")
            update_data = {
                "description": description,
                "pubDate": pub_date,
                "duration": duration
            }
            if manager.update_episode_metadata(existing_episode['id'], update_data):
                print(f"  ✅ Correctly updated: {title}")
            else:
                print(f"  ❌ Failed to update metadata for: {title}")
            continue

        # --- Naming Logic ---
        file_id_match = re.search(r'(?:id=|\/d\/)([a-zA-Z0-9_-]{20,})', old_url)
        if file_id_match:
            file_id = file_id_match.group(1)
        elif guid_match:
            file_id = re.sub(r'[^a-zA-Z0-9_-]', '_', guid_match.group(1))[:30]
        else:
            file_id = hashlib.md5(title.encode()).hexdigest()[:10]

        local_audio_path = temp_dir / f"{file_id}.mp3"

        # 1. Download and Upload Thumbnail to R2
        new_thumb_url = None
        if old_thumb_url:
            thumb_ext = "png" if ".png" in old_thumb_url.lower() else "jpg"
            local_thumb_path = temp_dir / f"{file_id}.{thumb_ext}"
            
            if download_file(old_thumb_url, local_thumb_path):
                print("  Uploading Thumbnail to Cloudflare R2...")
                new_thumb_url = manager.upload_file(local_thumb_path, content_type=f'image/{thumb_ext}')
                local_thumb_path.unlink()

        # 2. Download and Upload Audio to R2
        if download_file(old_url, local_audio_path):
            print("  Uploading Audio to Cloudflare R2...")
            new_url = manager.upload_file(local_audio_path, content_type='audio/mpeg')
            
            if new_url:
                print("  ✅ Uploaded. Updating Supabase Database...")
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
