import os
import json
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter

class Downloader:
    def __init__(self, output_dir="downloads"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def download_video(self, url):
        """Downloads the video in the best available format (maximum quality)."""
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(self.output_dir, '%(id)s.%(ext)s'),
            'quiet': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': True,
            'fragment_retries': 10,
            'extractor_args': {'youtube': {'player_client': ['android']}},
            'skip_unavailable_fragments': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise Exception("Failed to extract video info.")
                
                video_id = info.get('id')
                ext = info.get('ext', 'mp4')
                video_path = os.path.join(self.output_dir, f"{video_id}.{ext}")
                
                if not os.path.exists(video_path):
                    video_path = ydl.prepare_filename(info)
                
                return video_path, video_id
        except Exception as e:
            print(f"Detailed Error in download_video: {e}")
            raise

    def get_transcript(self, video_id):
        """Fetches the transcript for the given video ID and saves it to a file."""
        try:
            api = YouTubeTranscriptApi()
            # Try Portuguese first
            transcript = api.fetch(video_id, languages=['pt'])
            data = transcript.to_raw_data()
            self._save_transcript(video_id, data)
            return data
        except Exception as e:
            print(f"Error fetching PT transcript: {e}")
            try:
                # Fallback to any available
                transcript_list = api.list(video_id)
                transcript = transcript_list.find_transcript(['pt', 'en']).fetch()
                data = transcript.to_raw_data()
                self._save_transcript(video_id, data)
                return data
            except Exception as e2:
                print(f"Could not find any transcript: {e2}")
                return None

    def _save_transcript(self, video_id, data):
        """Saves transcript data to a local JSON file."""
        transcript_path = os.path.join(self.output_dir, f"{video_id}_transcript.json")
        with open(transcript_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Transcript saved to: {transcript_path}")

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
