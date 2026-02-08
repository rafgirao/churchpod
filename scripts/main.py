import sys
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

def main():
    parser = argparse.ArgumentParser(description="YouTube Preaching Cutter")
    parser.add_argument("url", help="YouTube URL of the church service")
    parser.add_argument("--no-upload", action="store_true", help="Only cut the video locally, do not upload to YouTube")
    parser.add_argument("--title", help="Title for the uploaded video")
    parser.add_argument("--desc", help="Description for the uploaded video")
    
    args = parser.parse_args()

    # 1. Get Video ID and Transcript
    print(f"--- Step 1: Fetching metadata and transcript ---")
    dl = Downloader()
    # Extract video ID from URL
    with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True}) as ydl:
        info = ydl.extract_info(args.url, download=False)
        video_id = info.get('id')
    
    print(f"Video ID: {video_id}")
    transcript = dl.get_transcript(video_id)
    if not transcript:
        print("Could not retrieve transcript. Aborting.")
        return
    print(f"Transcript fetched successfully.")

    # 2. Segment
    print(f"\n--- Step 2: Detecting preaching segment ---")
    seg = Segmenter()
    start_time, end_time = seg.detect_preaching_segment(transcript)
    
    if start_time is None or end_time is None:
        print("Could not identify preaching segment. Aborting.")
        return
        
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
            "title": f"Pregação - {video_id}",
            "description": f"Trecho extraído do vídeo original: {args.url}",
            "tags": ["igreja", "pregação", video_id]
        }

    # 4. Download Video
    print(f"\n--- Step 4: Downloading video (Maximum Quality) ---")
    video_path, _ = dl.download_video(args.url)
    print(f"Video downloaded to: {video_path}")

    # 5. Cut
    print(f"\n--- Step 5: Cutting video ---")
    cutter = Cutter()
    output_name = f"pregação_{video_id}.mp4"
    cut_path = cutter.cut_video(video_path, start_time, end_time, output_name)
    
    if not cut_path:
        print("Failed to cut video.")
        return
    print(f"Cut video saved to: {cut_path}")

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
            print(f"Successfully uploaded: https://www.youtube.com/watch?v={new_video_id}")
        except Exception as e:
            print(f"Error during upload: {e}")
            print("To fix upload, ensure 'client_secrets.json' is present.")
    else:
        print("\nSkipping upload step as requested.")

if __name__ == "__main__":
    main()
