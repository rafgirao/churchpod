import os
import boto3
from botocore.config import Config
from pathlib import Path


class R2Storage:
    """Handles file uploads to Cloudflare R2 (S3-compatible)."""

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
