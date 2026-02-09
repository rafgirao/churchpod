import os
import json
import yt_dlp
from pathlib import Path
from src.paths import PROJECT_ROOT
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter

class Downloader:
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "downloads"
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_video(self, url):
        """Downloads the video in the best available format (maximum quality)."""
        # 1. Fast Extraction: Try to get ID from URL without loading heavy tools
        import re
        video_id = None
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"be\/([0-9A-Za-z_-]{11}).*"
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break

        # 2. Pre-check: If we have the ID, check if it already exists
        if video_id:
            for ext in ['mp4', 'mkv', 'webm']:
                video_path = self.output_dir / f"{video_id}.{ext}"
                if video_path.exists():
                    print(f"Video {video_id} already exists in downloads. Skipping download.")
                    return str(video_path), video_id

        # 3. If not found or ID unknown, use yt-dlp to get certain info
        ydl_opts_info = {
            'quiet': True,
            'no_warnings': True,
            'cookiesfrombrowser': ('chrome',),
            'js_runtimes': {'node': {}},
            'remote_components': ['ejs:github'],
        }
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get('id')
            
        # 4. Check again with the official ID (just in case)
        for ext in ['mp4', 'mkv', 'webm']:
            video_path = self.output_dir / f"{video_id}.{ext}"
            if video_path.exists():
                print(f"Video {video_id} already exists in downloads. Skipping download.")
                return str(video_path), video_id

        # 3. Download if not exists
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': str(self.output_dir / '%(id)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'quiet': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': True,
            'fragment_retries': 10,
            'cookiesfrombrowser': ('chrome',),
            'js_runtimes': {'node': {}},
            'remote_components': ['ejs:github'],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.google.com/',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'ios'],
                }
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise Exception("Failed to extract video info.")
                
                video_id = info.get('id')
                ext = info.get('ext', 'mp4')
                video_path = self.output_dir / f"{video_id}.{ext}"
                
                if not video_path.exists():
                    video_path = Path(ydl.prepare_filename(info))
                
                return str(video_path), video_id
        except Exception as e:
            print(f"Detailed Error in download_video: {e}")
            raise

    def get_transcript(self, video_id):
        """Fetches the transcript for the given video ID and saves it to a file."""
        transcript_path = self.output_dir / f"{video_id}.json"

        # 1. Check if transcript already exists and is not empty
        if transcript_path.exists() and transcript_path.stat().st_size > 0:
            print(f"Transcript for {video_id} already exists. Loading from file.")
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Transcript file {transcript_path} is corrupted: {e}. Deleting and refetching.")
                transcript_path.unlink()

        # 2. Try to fetch from YouTubeTranscriptApi with cookies from browser
        try:
            import requests
            from http.cookiejar import MozillaCookieJar
            
            # We use yt-dlp to get the cookies from the browser in Netscape format
            cookies_file = self.output_dir / "temp_cookies.txt"
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiesfrombrowser': ('chrome',),
                'cookiefile': str(cookies_file),
                'js_runtimes': {'node': {}},
                'remote_components': ['ejs:github'],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info to trigger cookie extraction
                ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            
            # Create a session and load the cookies
            session = requests.Session()
            if cookies_file.exists():
                cj = MozillaCookieJar(str(cookies_file))
                try:
                    cj.load(ignore_discard=True, ignore_expires=True)
                    session.cookies = cj
                except Exception as e:
                    print(f"Warning: Could not load cookies from file: {e}")
                finally:
                    # Clean up temp cookies
                    cookies_file.unlink()
            
            # Initialize API with the session
            # Note: fetch() is an instance method
            api = YouTubeTranscriptApi(http_client=session)
            transcript_obj = api.fetch(video_id, languages=['pt', 'en'])
            transcript = transcript_obj.to_raw_data()
            
            self._save_transcript(video_id, transcript)
            return transcript
        except Exception as e:
            print(f"Error fetching transcript via API with cookies: {e}")
            print("Trying one last time without cookies...")
            try:
                api = YouTubeTranscriptApi()
                transcript_obj = api.fetch(video_id, languages=['pt', 'en'])
                transcript = transcript_obj.to_raw_data()
                self._save_transcript(video_id, transcript)
                return transcript
            except Exception as e2:
                print(f"Final transcript fetch attempt failed: {e2}")
                return None

    def _save_transcript(self, video_id, data):
        """Saves transcript data to a local JSON file."""
        transcript_path = self.output_dir / f"{video_id}.json"
        try:
            with open(transcript_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Transcript saved to: {transcript_path}")
        except Exception as e:
            print(f"Error saving transcript to file: {e}")
            if transcript_path.exists():
                transcript_path.unlink()

if __name__ == "__main__":
    # Test with the new video ID provided by the user
    test_url = "https://www.youtube.com/watch?v=dftum0wiBNU"
    dl = Downloader()
    print("Downloading video...")
    path, vid_id = dl.download_video(test_url)
    print(f"Downloaded to: {path}")
    print("Fetching transcript...")
    transcript = dl.get_transcript(vid_id)
    if transcript:
        print(f"Fetched {len(transcript)} lines of transcript.")
    else:
        print("No transcript found.")
