import os
from supabase import create_client, Client
from src.r2_storage import R2Storage

class PodcastManager:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY missing in .env")
            
        self.supabase: Client = create_client(self.url, self.key)
        self.r2 = R2Storage()

    def upload_file(self, file_path, object_name=None, content_type=None):
        """Uploads a file to Cloudflare R2 and returns its public URL."""
        return self.r2.upload_file(file_path, object_name=object_name, content_type=content_type)

    def episode_exists(self, title):
        """Checks if an episode with the same title already exists in the database."""
        res = self.supabase.table("episodes").select("id").eq("title", title).execute()
        return len(res.data) > 0

    def add_episode(self, episode_data):
        """Inserts a new episode into the Supabase database. The Edge Function handles the XML generation."""
        # Normalize duration for the feed (HH:MM:SS)
        original_duration = episode_data.get('duration', '00:00:00')
        if ":" in original_duration and len(original_duration.split(":")) == 2:
            duration = f"00:{original_duration}"
        else:
            duration = original_duration

        data = {
            "title": episode_data['title'],
            "description": episode_data['description'],
            "audio_url": episode_data['url'],
            "image_url": episode_data.get('image'),
            "duration": duration,
        }
        
        # Insert into DB
        self.supabase.table("episodes").insert(data).execute()
        
        # Return the Edge Function URL as the feed link
        return f"{self.url}/functions/v1/rss"
