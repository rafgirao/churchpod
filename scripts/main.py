import sys
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Bootstrap: Add project root to sys.path before any local imports
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from src.paths import PROJECT_ROOT
from src.downloader import Downloader
from src.segmenter import Segmenter
from src.cutter import Cutter
from src.uploader import Uploader

# Load .env from config
load_dotenv(PROJECT_ROOT / "config" / ".env")


# ── Helpers ──────────────────────────────────────────────

def parse_time_to_seconds(time_str):
    """Parses time in seconds or MM:SS or HH:MM:SS format to seconds."""
    try:
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return int(time_str)
    except (ValueError, TypeError):
        return None


def format_seconds(seconds):
    """Formats seconds into MM:SS or HH:MM:SS."""
    if seconds is None:
        return "N/A"
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def prompt_editable(label, current_value, multiline=False):
    """Shows a value and lets the user press Enter to accept or type a new one."""
    if multiline:
        print(f"\n  {label}:")
        print(f"  ─────────────────────────────")
        for line in str(current_value).split('\n'):
            print(f"  {line}")
        print(f"  ─────────────────────────────")
        new_val = input(f"  [Press Enter to accept or type a new value]: ").strip()
    else:
        new_val = input(f"  {label} [{current_value}]: ").strip()
    return new_val if new_val else current_value


def prompt_editable_list(label, current_list):
    """Shows a list and lets the user press Enter to accept or type new comma-separated values."""
    display = ", ".join(current_list) if current_list else "(none)"
    new_val = input(f"  {label} [{display}]: ").strip()
    if new_val:
        return [t.strip() for t in new_val.split(",") if t.strip()]
    return current_list


def prompt_time(label, current_seconds):
    """Shows a time value and lets the user press Enter to accept or type a new one."""
    display = format_seconds(current_seconds)
    while True:
        new_val = input(f"  {label} [{display}]: ").strip()
        if not new_val:
            return current_seconds
        parsed = parse_time_to_seconds(new_val)
        if parsed is not None:
            return parsed
        print("    ⚠️ Invalid format. Use MM:SS (e.g. 53:02) or seconds (e.g. 3182)")


# ── Main ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube Preaching Cutter")
    parser.add_argument("url", help="YouTube URL of the church service")
    parser.add_argument("--no-upload", action="store_true", help="Only cut the video locally, do not upload to YouTube")
    parser.add_argument("--title", help="Title for the uploaded video")
    parser.add_argument("--desc", help="Description for the uploaded video")
    
    args = parser.parse_args()

    # ── Step 1: Initial Recognition ──────────────────────
    print("--- Step 1: Video Identification ---")
    video_id = Downloader.extract_video_id(args.url)
    if not video_id:
        print("Could not parse video ID from URL. It will be resolved during download.")
    else:
        print(f"Video ID: {video_id}")

    dl = Downloader()

    # ── Step 2: Fetch Transcript ─────────────────────────
    print("\n--- Step 2: Fetching transcript ---")
    transcript = dl.get_transcript(video_id)

    # ── Step 3: Download Video (Maximum Quality) ──────────
    print("\n--- Step 3: Downloading video (Maximum Quality) ---")
    video_path, video_id = dl.download_video(args.url)
    print(f"Video downloaded to: {video_path}")

    # ── Step 4: Detect Preaching Segment ─────────────────
    start_time, end_time = None, None

    if transcript:
        print("Transcript fetched successfully.")
        print("\n--- Step 4: Detecting preaching segment ---")
        
        try:
            seg = Segmenter()
            start_time, end_time = seg.detect_preaching_segment(transcript)
        except Exception as e:
            print(f"  [⚠️] AI detection failed: {e}")

        if start_time is not None and end_time is not None:
            duration = (end_time - start_time) / 60
            print(f"  AI detected: {format_seconds(start_time)} → {format_seconds(end_time)} ({duration:.1f} min)")
        else:
            print("  [⚠️] AI could not detect the preaching segment.")
    else:
        print("\n[!] Could not retrieve transcript.")
        print("\n--- Step 4: Manual segment definition ---")

    # Always let user confirm/edit the times
    print("\n  📐 Confirm cut times (Press Enter to accept, or type new):")
    start_time = prompt_time("Start", start_time)
    end_time = prompt_time("End  ", end_time)

    while start_time is None:
        print("    ⚠️ Start time is required!")
        start_time = prompt_time("Start", None)
    while end_time is None:
        print("    ⚠️ End time is required!")
        end_time = prompt_time("End  ", None)

    duration = (end_time - start_time) / 60
    print(f"\n  ✅ Segment: {format_seconds(start_time)} → {format_seconds(end_time)} ({duration:.1f} min)")

    # ── Step 5: Generate / Edit Metadata ─────────────────
    print("\n--- Step 5: Metadata (Title, Description, Tags) ---")

    ai_metadata = None
    if transcript:
        try:
            seg = seg if 'seg' in dir() else Segmenter()
            ai_metadata = seg.generate_metadata(transcript, start_time, end_time)
        except Exception as e:
            print(f"  [⚠️] AI metadata generation failed: {e}")

    # Defaults
    title = f"Preaching - {video_id}"
    description = f"Segment extracted from original video: {args.url}"
    tags = ["church", "preaching", "sermon", video_id]

    if ai_metadata:
        title = ai_metadata.get("title", title)
        description = ai_metadata.get("description", description)
        tags = ai_metadata.get("tags", tags)
        print("  🤖 AI generated metadata. Review and edit if necessary:")
    else:
        print("  ✏️  Enter metadata manually (or Press Enter to accept default):")

    # Let user review/edit each field
    title = args.title or prompt_editable("Title", title)
    description = args.desc or prompt_editable("Description", description, multiline=True)
    tags = prompt_editable_list("Tags (comma-separated)", tags)

    metadata = {
        "title": title,
        "description": description,
        "tags": tags,
    }

    print(f"\n  ✅ Title: {metadata['title']}")
    print(f"  ✅ Tags: {', '.join(metadata['tags'])}")
    print(f"  ✅ Description: {metadata['description'][:80]}...")

    # ── Custom Thumbnails ────────────────────────────────
    print("\n--- Custom Thumbnails (Optional) ---")
    thumb_podcast = input("[?] SQUARE Thumbnail (Podcast/Spotify) - drag the file here: ").strip().strip("'").strip('"')
    thumb_youtube = input("[?] 16:9 Thumbnail (YouTube) - drag the file here: ").strip().strip("'").strip('"')

    custom_thumb_podcast = thumb_podcast if thumb_podcast and os.path.exists(thumb_podcast) else None
    custom_thumb_youtube = thumb_youtube if thumb_youtube and os.path.exists(thumb_youtube) else None

    if thumb_podcast and not custom_thumb_podcast:
        print(f"  ⚠️ Podcast Thumb not found: {thumb_podcast}")
    if thumb_youtube and not custom_thumb_youtube:
        print(f"  ⚠️ YouTube Thumb not found: {thumb_youtube}")

    # ── Step 6: Cut Video ────────────────────────────────
    print("\n--- Step 6: Cutting video ---")
    cutter = Cutter()
    output_name = f"{video_id}.mp4"
    cut_path = cutter.cut_video(video_path, start_time, end_time, output_name)
    
    if not cut_path:
        print("Failed to cut video.")
        return
    print(f"Cut video path: {cut_path}")

    # ── Step 7: Extract MP3 ──────────────────────────────
    print("\n--- Step 7: Extracting MP3 for Spotify ---")
    mp3_name = f"{video_id}.mp3"
    mp3_path = cutter.extract_audio(cut_path, mp3_name)
    if mp3_path:
        print(f"MP3 path: {mp3_path}")
    else:
        print("Failed to extract MP3.")

    # ── Step 8: Upload to R2 + Supabase ──────────────────
    if mp3_path:
        print("\n--- Step 8: Uploading to R2 & Updating Supabase DB ---")
        try:
            from src.podcast_manager import PodcastManager
            manager = PodcastManager()
            
            r2_thumb_url = None
            if custom_thumb_podcast:
                print("Uploading Square Thumbnail to Cloudflare R2...")
                ext = custom_thumb_podcast.split('.')[-1]
                r2_thumb_url = manager.upload_file(custom_thumb_podcast, object_name=f"{video_id}.{ext}", content_type=f'image/{ext}')

            print("Uploading MP3 to Cloudflare R2...")
            episode_url = manager.upload_file(mp3_path, content_type='audio/mpeg')
            
            if episode_url:
                print(f"MP3 uploaded to R2: {episode_url}")
                
                episode_data = {
                    "title": metadata["title"],
                    "description": metadata["description"],
                    "url": episode_url,
                    "duration": f"{(end_time - start_time) // 60}:{(end_time - start_time) % 60:02d}",
                    "image": r2_thumb_url 
                }
                
                feed_url = manager.add_episode(episode_data)
                print(f"✅ Supabase Database updated!")
                print(f"👉 Your Dynamic RSS Feed: {feed_url}")
            else:
                print("❌ R2 upload failed.")

        except Exception as e:
            print(f"Error during Hybrid Storage update: {e}")

    # ── Step 9: Upload to YouTube ────────────────────────
    if not args.no_upload:
        print("\n--- Step 9: Uploading to YouTube (Unlisted) ---")
        try:
            up = Uploader()
            
            new_video_id = up.upload_video(
                cut_path, 
                metadata["title"], 
                metadata["description"], 
                tags=metadata["tags"],
                privacy_status="unlisted"
            )
            
            if new_video_id and custom_thumb_youtube:
                print("Setting custom 16:9 thumbnail for YouTube...")
                up.set_thumbnail(new_video_id, custom_thumb_youtube)

            print(f"Successfully uploaded: https://www.youtube.com/watch?v={new_video_id}")
        except Exception as e:
            print(f"Error during upload: {e}")
            print("To fix upload, ensure 'client_secrets.json' is present.")
    else:
        print("\nSkipping YouTube upload step as requested.")


if __name__ == "__main__":
    main()
