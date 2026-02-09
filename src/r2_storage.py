import os
import boto3
import re
from botocore.config import Config
from botocore.exceptions import ClientError
from pathlib import Path
from src.paths import PROJECT_ROOT

class R2Storage:
    def __init__(self):
        self.account_id = os.getenv("R2_ACCOUNT_ID")
        self.access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        self.secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("R2_BUCKET_NAME")
        self.public_url = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

        if not all([self.account_id, self.access_key_id, self.secret_access_key, self.bucket_name]):
            raise ValueError("Cloudflare R2 settings are missing in the .env file")

        self.s3_client = boto3.client(
            service_name='s3',
            endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(signature_version='s3v4')
        )

    def upload_file(self, file_path, object_name=None, content_type=None):
        """Uploads a file to R2 and returns the public link."""
        if object_name is None:
            object_name = os.path.basename(file_path)

        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        try:
            self.s3_client.upload_file(
                str(file_path),
                self.bucket_name,
                object_name,
                ExtraArgs=extra_args
            )
            
            if not self.public_url:
                return object_name
                
            return f"{self.public_url}/{object_name}"
        except Exception as e:
            print(f"Error uploading to R2: {e}")
            return None

    def update_rss(self, podcast_meta, episode_data):
        """Fetches existing RSS, updates channel metadata, adds new episode, and uploads."""
        rss_filename = "podcast_feed.xml"
        existing_items = ""
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=rss_filename)
            content = response['Body'].read().decode('utf-8')
            
            import xml.etree.ElementTree as ET
            try:
                ET.fromstring(content)
                items = re.findall(r'<item>.*?</item>', content, re.DOTALL)
                existing_items = "\n".join(items)
                print(f"Existing RSS found. Preserving {len(items)} episodes while updating metadata...")
            except ET.ParseError:
                print("⚠️ Existing RSS is malformed. Recreating from scratch...")
                existing_items = ""

        except ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                print("Starting fresh RSS feed on R2...")
            else:
                print(f"Error fetching RSS: {e}")
        except Exception as e:
            print(f"Unexpected error while reading existing RSS: {e}")

        new_rss_content = self._create_new_rss(podcast_meta, episode_data, existing_items)

        rss_path = PROJECT_ROOT / rss_filename
        with open(rss_path, 'w', encoding='utf-8') as f:
            f.write(new_rss_content)
            
        return self.upload_file(rss_path, rss_filename, content_type='application/xml')

    def _create_new_rss(self, meta, episode, existing_items_xml=""):
        """Creates an RSS feed XML using Spotify/Anchor best practices (CDATA, itunes tags)."""
        title = meta.get('title', 'My Church Podcast')
        description = meta.get('description', 'Church preaching and messages.')
        author = meta.get('author', 'My Church')
        email = meta.get('email', 'podcast@example.com')
        image_url = meta.get('image', '')
        link = meta.get('link', 'https://example.com')
        
        new_item_xml = self._generate_item_xml(episode)
        
        all_items_xml = new_item_xml
        if existing_items_xml.strip():
            all_items_xml += "\n" + existing_items_xml.strip()
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title><![CDATA[{title}]]></title>
    <description><![CDATA[{description}]]></description>
    <link>{link}</link>
    <language>pt-br</language>
    <itunes:author>{author}</itunes:author>
    <itunes:type>episodic</itunes:type>
    <itunes:owner>
      <itunes:name>{author}</itunes:name>
      <itunes:email>{email}</itunes:email>
    </itunes:owner>
    <itunes:image href="{image_url}"/>
    <itunes:category text="Religion &amp; Spirituality">
      <itunes:category text="Christianity"/>
    </itunes:category>
    <itunes:explicit>no</itunes:explicit>
    {all_items_xml}
  </channel>
</rss>"""

    def _generate_item_xml(self, episode):
        """Generates the XML block for a single episode with Premium Spotify tags."""
        from datetime import datetime
        
        pub_date = episode.get('pubDate') or datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
        title = episode['title']
        description = episode['description']
        url = episode['url']
        image_url = episode.get('image') # Individual episode thumbnail
        
        # Format duration to HH:MM:SS
        original_duration = episode.get('duration', '00:00')
        if ":" in original_duration:
            parts = original_duration.split(":")
            if len(parts) == 2:
                duration = f"00:{int(parts[0]):02d}:{int(parts[1]):02d}"
            else:
                duration = original_duration
        else:
            duration = "00:00:00"

        image_tag = f'<itunes:image href="{image_url}"/>' if image_url else ""

        return f"""
    <item>
      <title><![CDATA[{title}]]></title>
      <description><![CDATA[{description}]]></description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{url}" type="audio/mpeg" length="0"/>
      <itunes:duration>{duration}</itunes:duration>
      <itunes:explicit>no</itunes:explicit>
      <itunes:episodeType>full</itunes:episodeType>
      {image_tag}
      <guid isPermaLink="false">{url}</guid>
      <dc:creator><![CDATA[{os.getenv("PODCAST_AUTHOR", "Church")}]]></dc:creator>
    </item>"""
