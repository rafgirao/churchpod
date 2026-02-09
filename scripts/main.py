import sys
import os
import argparse
import yt_dlp
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

def parse_time_to_seconds(time_str):
    """Parses time in seconds or MM:SS format to seconds."""
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

def main():
    parser = argparse.ArgumentParser(description="YouTube Preaching Cutter")
    parser.add_argument("url", help="YouTube URL of the church service")
    parser.add_argument("--no-upload", action="store_true", help="Only cut the video locally, do not upload to YouTube")
    parser.add_argument("--title", help="Title for the uploaded video")
    parser.add_argument("--desc", help="Description for the uploaded video")
    
    args = parser.parse_args()

    # 1. Get Video ID and Transcript
    print(f"--- Step 1: Fetching metadata and transcript ---")
    
    # Fast Extraction: Try to get ID from URL without loading heavy tools
    import re
    video_id = None
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"be\/([0-9A-Za-z_-]{11}).*"
    ]
    for pattern in patterns:
        match = re.search(pattern, args.url)
        if match:
            video_id = match.group(1)
            break
            
    if not video_id:
        # Fallback to heavy tool only if regex fails
        print("Could not parse ID from URL string. Falling back to yt-dlp...")
        ydl_opts_fallback = {
            'quiet': True, 
            'nocheckcertificate': True, 
            'cookiesfrombrowser': ('chrome',), 
            'remote_components': ['ejs:github']
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                info = ydl.extract_info(args.url, download=False)
                video_id = info.get('id')
        except Exception as e:
            print(f"Warning: Failed to extract info with cookies ({e}). Retrying without cookies...")
            ydl_opts_fallback.pop('cookiesfrombrowser', None)
            with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                info = ydl.extract_info(args.url, download=False)
                video_id = info.get('id')
    
    print(f"Video ID: {video_id}")
    dl = Downloader()
    transcript = dl.get_transcript(video_id)
    
    start_time, end_time = None, None
    metadata = {}

    if not transcript:
        print("\n[!] Could not retrieve transcript. Entering MANUAL FALLBACK.")
        print("Please enter the times for the preaching segment:")
        
        while start_time is None:
            raw_start = input("Start time (MM:SS or seconds): ").strip()
            start_time = parse_time_to_seconds(raw_start)
            if start_time is None:
                print("Invalid format. Use MM:SS (e.g., 30:00) or total seconds (e.g., 1800).")
        
        while end_time is None:
            raw_end = input("End time (MM:SS or seconds): ").strip()
            end_time = parse_time_to_seconds(raw_end)
            if end_time is None:
                print("Invalid format.")
        
        print("\nMetadata (AI cannot generate without transcript):")
        manual_title = input(f"Video Title [Default: Preaching - {video_id}]: ").strip()
        manual_desc = input(f"Description [Default: Segment extracted from {args.url}]: ").strip()
        
        metadata = {
            "title": manual_title or f"Preaching - {video_id}",
            "description": manual_desc or f"Segment extracted from original video: {args.url}",
            "tags": ["church", "preaching", video_id]
        }
    else:
        print(f"Transcript fetched successfully.")

        # 2. Segment
        print(f"\n--- Step 2: Detecting preaching segment ---")
        seg = Segmenter()
        start_time, end_time = seg.detect_preaching_segment(transcript)
        
        if start_time is None or end_time is None:
            print("Could not identify preaching segment automatically.")
            # Fallback within fallback if AI fails even with transcript
            while start_time is None:
                start_time = parse_time_to_seconds(input("Enter start time manually (MM:SS or seconds): "))
            while end_time is None:
                end_time = parse_time_to_seconds(input("Enter end time manually (MM:SS or seconds): "))
            
        print(f"Found preaching segment: {start_time}s to {end_time}s")
        print(f"Duration: {(end_time - start_time) / 60:.2f} minutes")

        # 3. Generate Metadata (OpenAI)
        print(f"\n--- Step 3: Generating optimized metadata ---")
        metadata = seg.generate_metadata(transcript, start_time, end_time)
        if metadata:
            print(f"Title: {metadata.get('title')}")
            print(f"Tags: {', '.join(metadata.get('tags', []))}")
        else:
            print("Failed to generate metadata with OpenAI. Using defaults.")
            metadata = {
                "title": f"Preaching - {video_id}",
                "description": f"Segment extracted from original video: {args.url}",
                "tags": ["church", "preaching", video_id]
            }

    # 4. Download Video
    print(f"\n--- Step 4: Downloading video (Maximum Quality) ---")
    video_path, _ = dl.download_video(args.url)
    print(f"Video downloaded to: {video_path}")


    # Optional Custom Thumbnail Prompts
    print("\n--- Custom Thumbnails (Optional) ---")
    thumb_podcast = input("[?] SQUARE Thumbnail (Podcast/Spotify) - drag the file here: ").strip().strip("'").strip('"')
    thumb_youtube = input("[?] 16:9 Thumbnail (YouTube) - drag the file here: ").strip().strip("'").strip('"')

    custom_thumb_podcast = thumb_podcast if thumb_podcast and os.path.exists(thumb_podcast) else None
    custom_thumb_youtube = thumb_youtube if thumb_youtube and os.path.exists(thumb_youtube) else None

    if thumb_podcast and not custom_thumb_podcast: print(f"  ⚠️ Podcast Thumb not found: {thumb_podcast}")
    if thumb_youtube and not custom_thumb_youtube: print(f"  ⚠️ YouTube Thumb not found: {thumb_youtube}")

    # 5. Cut
    print(f"\n--- Step 5: Cutting video ---")
    cutter = Cutter()
    output_name = f"{video_id}.mp4"
    # The cutter now handles skip_existing=True by default
    cut_path = cutter.cut_video(video_path, start_time, end_time, output_name)
    
    if not cut_path:
        print("Failed to cut video.")
        return
    print(f"Cut video path: {cut_path}")

    # 5.5 Extract MP3 (New)
    print(f"\n--- Step 5.5: Extracting MP3 for Spotify ---")
    mp3_name = f"{video_id}.mp3"
    # The cutter now handles skip_existing=True by default
    mp3_path = cutter.extract_audio(cut_path, mp3_name)
    if mp3_path:
        print(f"MP3 path: {mp3_path}")
    else:
        print("Failed to extract MP3.")

    # 5.7 Storage & RSS (Hybrid: R2 for Files, Supabase for DB)
    if mp3_path:
        print(f"\n--- Step 5.7: Uploading to R2 & Updating Supabase DB ---")
        try:
            from src.podcast_manager import PodcastManager
            manager = PodcastManager()
            
            # 1. Upload Square Thumbnail to R2
            r2_thumb_url = None
            if custom_thumb_podcast:
                print("Uploading Square Thumbnail to Cloudflare R2...")
                ext = custom_thumb_podcast.split('.')[-1]
                r2_thumb_url = manager.upload_file(custom_thumb_podcast, object_name=f"{video_id}.{ext}", content_type=f'image/{ext}')

            # 2. Upload MP3 to R2
            print("Uploading MP3 to Cloudflare R2...")
            episode_url = manager.upload_file(mp3_path, content_type='audio/mpeg')
            
            if episode_url:
                print(f"MP3 uploaded to R2: {episode_url}")
                
                episode_data = {
                    "title": metadata.get("title"),
                    "description": metadata.get("description"),
                    "url": episode_url,
                    "duration": f"{(end_time - start_time) // 60}:{(end_time - start_time) % 60:02d}",
                    "image": r2_thumb_url 
                }
                
                # 3. Save metadata to Supabase DB (Dynamic RSS)
                feed_url = manager.add_episode(episode_data)
                print(f"✅ Supabase Database updated!")
                print(f"👉 Your Dynamic RSS Feed: {feed_url}")
            else:
                print("❌ R2 upload failed.")

        except Exception as e:
            print(f"Error during Hybrid Storage update: {e}")

    # 6. Upload (Default behavior, skipped if --no-upload is used)
    if not args.no_upload:
        print(f"\n--- Step 6: Uploading to YouTube (Unlisted) ---")
        try:
            up = Uploader()
            title = args.title or metadata.get("title")
            description = args.desc or metadata.get("description")
            tags = metadata.get("tags")
            
            new_video_id = up.upload_video(
                cut_path, 
                title, 
                description, 
                tags=tags,
                privacy_status="unlisted"
            )
            
            if new_video_id and custom_thumb_youtube:
                print(f"Setting custom 16:9 thumbnail for YouTube...")
                up.set_thumbnail(new_video_id, custom_thumb_youtube)

            print(f"Successfully uploaded: https://www.youtube.com/watch?v={new_video_id}")
        except Exception as e:
            print(f"Error during upload: {e}")
            print("To fix upload, ensure 'client_secrets.json' is present.")
    else:
        print("\nSkipping upload step as requested.")

if __name__ == "__main__":
    main()
