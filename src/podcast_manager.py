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

    def get_episode_by_title(self, title):
        """Returns the episode record if it exists, searching by title."""
        res = self.supabase.table("episodes").select("*").eq("title", title.strip()).execute()
        return res.data[0] if res.data else None

    def add_episode(self, episode_data):
        """Inserts a new episode into the Supabase database."""
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
        
        if episode_data.get('pubDate'):
            data["pub_date"] = episode_data['pubDate']

        self.supabase.table("episodes").insert(data).execute()
        
        # Return the Edge Function URL as the feed link
        return f"{self.url}/functions/v1/rss"

    def update_episode_metadata(self, episode_id, metadata):
        """Updates metadata for an existing episode identified by ID."""
        import email.utils

        # Map keys to DB columns
        db_data = {}
        mapping = {
            "description": "description",
            "url": "audio_url",
            "image": "image_url",
            "duration": "duration",
            "pubDate": "pub_date"
        }
        
        for key, db_col in mapping.items():
            if key in metadata and metadata[key]:
                value = metadata[key]
                if key == "pubDate":
                    try:
                        parsed_date = email.utils.parsedate_to_datetime(value)
                        value = parsed_date.isoformat()
                    except Exception as e:
                        print(f"  ⚠️ Could not parse date '{value}': {e}")
                
                db_data[db_col] = value

        if not db_data:
            return False

        res = self.supabase.table("episodes").update(db_data).eq("id", episode_id).execute()
        return bool(hasattr(res, 'data') and res.data)
