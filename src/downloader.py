import os
import re
import json
import glob
import shutil
import subprocess
import yt_dlp
from pathlib import Path
from src.paths import PROJECT_ROOT
from youtube_transcript_api import YouTubeTranscriptApi


class Downloader:
    """Handles video downloading and transcript fetching for YouTube videos."""

    SUPPORTED_EXTENSIONS = ['mp4', 'mkv', 'webm']

    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "downloads"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def extract_video_id(url):
        """Extract YouTube video ID from URL without making network requests."""
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"be\/([0-9A-Za-z_-]{11}).*",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _find_existing_video(self, video_id):
        """Check if a video file already exists for the given ID. Returns path or None."""
        for ext in self.SUPPORTED_EXTENSIONS:
            video_path = self.output_dir / f"{video_id}.{ext}"
            if video_path.exists():
                return video_path
        return None

    @staticmethod
    def _get_video_resolution(video_path):
        """Get resolution string (e.g. '1920x1080') via ffprobe. Returns empty string on failure."""
        try:
            cmd = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height', '-of', 'json', str(video_path)
            ]
            probe = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8')
            probe_data = json.loads(probe)
            streams = probe_data.get('streams', [])
            if streams:
                w = streams[0].get('width')
                h = streams[0].get('height')
                if w and h:
                    return f"{w}x{h}"
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
            pass
        return ""

    def _build_base_opts(self):
        """Build the base yt-dlp options dict with cookie and JS runtime configuration."""
        # Cookie strategy: manual file > Chrome browser
        manual_cookies = PROJECT_ROOT / "cookies.txt"
        cookie_opts = {}
        if manual_cookies.exists():
            print("  [🔓] Using manual cookies.txt for authentication.")
            cookie_opts['cookiefile'] = str(manual_cookies)
        else:
            print("  [🍪] Using Chrome cookies for authentication.")
            cookie_opts['cookiesfrombrowser'] = ('chrome',)

        # Node.js runtime for YouTube JS challenge solving
        node_path = shutil.which('node')
        js_opts = {}
        if node_path:
            os.environ['PATH'] = os.path.dirname(node_path) + os.pathsep + os.environ.get('PATH', '')
            js_opts['js_runtimes'] = {'node': {'path': node_path}}
            print(f"  [✓] Node.js found at: {node_path}")
        else:
            print("  [⚠️] Node.js not found! 1080p may not be available.")

        return {
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'remote_components': ['ejs:github'],
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/121.0.0.0 Safari/537.36'
                ),
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'tv', 'ios', 'android'],
                }
            },
            **cookie_opts,
            **js_opts,
        }

    @staticmethod
    def _clear_ytdlp_cache():
        """Clear yt-dlp's internal cache to avoid stale 'Sign in' blocks."""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                ydl.cache.remove()
        except Exception:
            pass

    # ── Core Methods ─────────────────────────────────────────

    def download_video(self, url):
        """Downloads the video in the best available format (up to 1080p).

        Returns:
            tuple: (video_path: str, video_id: str)
        """
        video_id = self.extract_video_id(url)
        base_opts = self._build_base_opts()

        # 1. Quick check: skip if already downloaded
        if video_id:
            existing = self._find_existing_video(video_id)
            if existing:
                res = self._get_video_resolution(existing)
                res_label = f" ({res})" if res else ""
                print(f"Video {video_id} already exists in downloads{res_label}. Skipping download.")
                return str(existing), video_id

        # 2. Extract metadata (without downloading) to learn the official ID and resolution
        info = None
        try:
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    video_id = info.get('id', video_id)
        except Exception as e:
            print(f"Warning: Info extraction failed ({e}). Retrying without cookies...")
            no_cookie_opts = {k: v for k, v in base_opts.items()
                             if k not in ('cookiefile', 'cookiesfrombrowser')}
            try:
                with yt_dlp.YoutubeDL(no_cookie_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        video_id = info.get('id', video_id)
            except Exception as e2:
                print(f"Warning: Could not extract video info without cookies either: {e2}")

        if not video_id:
            raise Exception("Could not determine video ID from URL or YouTube API.")

        # 3. Check again with the official ID (may differ from regex)
        existing = self._find_existing_video(video_id)
        if existing:
            res = self._get_video_resolution(existing)
            res_label = f" ({res})" if res else ""
            print(f"Video {video_id} already exists in downloads{res_label}. Skipping download.")
            return str(existing), video_id

        # 4. Prepare download options
        import copy
        download_opts = copy.deepcopy(base_opts)
        download_opts.update({
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'outtmpl': str(self.output_dir / '%(id)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'youtube_include_dash_manifest': True,
            'youtube_include_hls_manifest': True,
        })

        self._clear_ytdlp_cache()

        # 5. Log resolution info before downloading
        if info:
            width = info.get('width', 0)
            height = info.get('height', 0)
            print(f"\n[🚀] Preparing Download:")
            print(f"     Resolution: {width}x{height} ({info.get('format_note', 'N/A')})")
            if height and height < 720:
                formats = info.get('formats', [])
                heights = sorted(set(f.get('height') for f in formats if f.get('height')))
                print(f"     ⚠️  Only {height}p detected. Others visible: {', '.join(f'{h}p' for h in heights)}")
            print("--- Starting Download ---\n")
        else:
            print("\n[⚠️] Downloading without metadata (bot detection may be active).")
            print("--- Starting Download ---\n")

        # 6. Download
        try:
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"Detailed Error in download_video: {e}")
            raise

        # 7. Find the downloaded file
        video_path = self._find_existing_video(video_id)
        if not video_path:
            raise Exception(
                f"Download finished but file not found for {video_id} in {self.output_dir}. "
                "Bot detection likely blocked the download."
            )

        res = self._get_video_resolution(video_path)
        if res:
            print(f"  [✓] Downloaded: {video_id} at {res}")

        return str(video_path), video_id

    def get_transcript(self, video_id):
        """Fetches the transcript for the given video ID and saves it to a file."""
        transcript_path = self.output_dir / f"{video_id}.json"

        # 1. Return cached transcript if available
        if transcript_path.exists() and transcript_path.stat().st_size > 0:
            print(f"Transcript for {video_id} already exists. Loading from file.")
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Transcript file {transcript_path} is corrupted: {e}. Deleting and refetching.")
                transcript_path.unlink()

        # 2. Try fetching with Chrome cookies (loaded directly, no yt-dlp call)
        try:
            import requests
            import browser_cookie3

            session = requests.Session()
            try:
                cj = browser_cookie3.chrome(domain_name='.youtube.com')
                session.cookies = cj
                print("  [🍪] Loaded Chrome cookies for transcript fetch.")
            except Exception as e:
                print(f"  [⚠️] Could not load Chrome cookies: {e}")

            api = YouTubeTranscriptApi(http_client=session)
            transcript_obj = api.fetch(video_id, languages=['pt', 'en'])
            transcript = transcript_obj.to_raw_data()

            self._save_transcript(video_id, transcript)
            return transcript
        except Exception as e:
            print(f"Transcript API blocked: {type(e).__name__}")
            print("  [🔄] Falling back to yt-dlp subtitle extraction...")
            return self._get_transcript_via_ytdlp(video_id)

    def _get_transcript_via_ytdlp(self, video_id):
        """Fallback: use yt-dlp to download subtitles when the transcript API is IP-blocked."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        sub_dir = self.output_dir / "subs"
        sub_dir.mkdir(exist_ok=True)

        base_opts = self._build_base_opts()
        sub_opts = {
            **{k: v for k, v in base_opts.items()},
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['pt', 'en'],
            'subtitlesformat': 'json3',
            'outtmpl': str(sub_dir / '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
        }

        try:
            with yt_dlp.YoutubeDL(sub_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"  [❌] yt-dlp subtitle download failed: {e}")
            return None

        # Find the subtitle file (json3 format)
        transcript = None
        for lang in ['pt', 'en']:
            for pattern in [f"{video_id}.{lang}.json3", f"{video_id}.{lang}*.json3"]:
                matches = glob.glob(str(sub_dir / f"{video_id}*{lang}*json3"))
                if matches:
                    transcript = self._parse_json3_subtitles(matches[0])
                    if transcript:
                        print(f"  [✓] Loaded subtitles via yt-dlp ({lang})")
                        self._save_transcript(video_id, transcript)
                        # Cleanup subtitle files
                        for f in sub_dir.iterdir():
                            f.unlink()
                        sub_dir.rmdir()
                        return transcript

        # Try VTT format as fallback
        for lang in ['pt', 'en']:
            matches = glob.glob(str(sub_dir / f"{video_id}*{lang}*vtt"))
            if matches:
                transcript = self._parse_vtt_subtitles(matches[0])
                if transcript:
                    print(f"  [✓] Loaded subtitles via yt-dlp ({lang}, VTT)")
                    self._save_transcript(video_id, transcript)
                    for f in sub_dir.iterdir():
                        f.unlink()
                    sub_dir.rmdir()
                    return transcript

        print("  [❌] No subtitle files found via yt-dlp.")
        # Cleanup
        for f in sub_dir.iterdir():
            f.unlink()
        sub_dir.rmdir()
        return None

    @staticmethod
    def _parse_json3_subtitles(filepath):
        """Parses yt-dlp's json3 subtitle format into our transcript format."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            events = data.get('events', [])
            transcript = []
            for event in events:
                if 'segs' not in event:
                    continue
                text = ''.join(seg.get('utf8', '') for seg in event['segs']).strip()
                if not text or text == '\n':
                    continue
                start_ms = event.get('tStartMs', 0)
                duration_ms = event.get('dDurationMs', 0)
                transcript.append({
                    'text': text,
                    'start': start_ms / 1000.0,
                    'duration': duration_ms / 1000.0,
                })
            return transcript if transcript else None
        except Exception as e:
            print(f"  Error parsing json3 subtitles: {e}")
            return None

    @staticmethod
    def _parse_vtt_subtitles(filepath):
        """Parses a VTT subtitle file into our transcript format."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            transcript = []
            blocks = content.split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                # Find timestamp line (HH:MM:SS.mmm --> HH:MM:SS.mmm)
                for i, line in enumerate(lines):
                    if '-->' in line:
                        times = line.split('-->')
                        start = Downloader._vtt_time_to_seconds(times[0].strip())
                        end = Downloader._vtt_time_to_seconds(times[1].strip().split(' ')[0])
                        text = ' '.join(lines[i+1:]).strip()
                        # Remove VTT formatting tags
                        text = re.sub(r'<[^>]+>', '', text)
                        if text:
                            transcript.append({
                                'text': text,
                                'start': start,
                                'duration': end - start,
                            })
                        break
            return transcript if transcript else None
        except Exception as e:
            print(f"  Error parsing VTT subtitles: {e}")
            return None

    @staticmethod
    def _vtt_time_to_seconds(time_str):
        """Converts VTT timestamp (HH:MM:SS.mmm) to seconds."""
        parts = time_str.replace(',', '.').split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])

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
