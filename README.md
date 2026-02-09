# ChurchPod 🎙️🏛️

**ChurchPod** is an AI-powered tool that automatically cuts church YouTube videos into podcast episodes. It finds the preaching part, generates titles and descriptions, and uploads to YouTube and Google Drive for easy podcast distribution.

## What It Does

- Downloads church service videos from YouTube
- Uses AI to detect the preaching segment
- Cuts the video to just the sermon
- Generates optimized metadata (title, description, tags)
- Uploads the cut video to YouTube (unlisted)
- Extracts MP3 for podcast platforms
- Uploads to Google Drive and creates RSS feed for Spotify

## Quick Start for Beginners

### Step 1: Install Required Software

1. **Python**: Download from https://python.org (version 3.8 or higher)
2. **FFmpeg**:
   - Windows: Download from https://ffmpeg.org/download.html
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. **Git**: Download from https://git-scm.com

### Step 2: Download ChurchPod

```bash
git clone https://github.com/rafgirao/churchpod.git
cd churchpod
```

### Step 3: Set Up Environment

1. Copy the example config:

   ```bash
   cp config/.env.example config/.env
   ```

2. Edit `config/.env` with your API keys (see explanations below)

### Step 4: Install Dependencies

```bash
pip install -r config/requirements.txt
```

### Step 5: Get API Keys

#### OpenAI API Key

- Go to https://platform.openai.com/api-keys
- Create a new API key
- Add it to `OPENAI_API_KEY` in your `.env` file

#### YouTube API

- Go to https://console.cloud.google.com/
- Create a new project or select existing
- Enable YouTube Data API v3
- Create OAuth credentials (download `client_secrets.json`)
- Place the file in `credentials/client_secrets.json`

#### Google Drive Folder ID (Optional)

- Create a folder in Google Drive for podcast MP3s
- Copy the folder ID from the URL (the long string after `/folders/`)
- Add `SPOTIFY_DRIVE_FOLDER_ID=your_folder_id` to `.env`

### Step 6: Run ChurchPod

To cut a video and upload it:

```bash
./cpcut https://www.youtube.com/watch?v=VIDEO_ID
```

For local testing (no upload):

```bash
./cpcut https://www.youtube.com/watch?v=VIDEO_ID --no-upload
```

## Configuration (.env) Explained

Your `.env` file contains API keys and settings. Here's what each one does:

- **OPENAI_API_KEY**: Used for AI-powered transcript analysis and metadata generation
- **R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_URL**: For Cloudflare R2 cloud storage (optional, for advanced users)
- **SUPABASE_URL, SUPABASE_KEY**: For database storage (optional, for advanced users)
- **SPOTIFY_DRIVE_FOLDER_ID**: Google Drive folder ID for MP3 storage and RSS feed

Get detailed instructions for each service in the links provided in `config/.env.example`.

## Features in Detail

- **Automatic Download**: Gets the best quality video from YouTube
- **Smart Detection**: Analyzes the transcript to find preaching start/end
- **AI Metadata**: Creates SEO-friendly titles, descriptions, and tags
- **Fast Cutting**: Uses FFmpeg for lossless video cutting
- **YouTube Upload**: Posts as unlisted videos on your channel
- **Podcast Support**: Generates MP3s and RSS feeds for Spotify

## Project Structure

- `cpcut`: Main command to run the tool
- `cpimport`: Tool for migrating existing podcast feeds
- `scripts/`: Python scripts for processing
- `src/`: Core application modules
- `config/`: Configuration files
- `prompts/`: AI prompt templates

## Troubleshooting

- **First run**: Will open browser for Google/YouTube authorization
- **No transcript**: Falls back to manual time entry
- **Upload fails**: Check API keys and permissions
- **Git pull issues**: Ensure you're connected to the internet

## Support

For issues or questions, check the GitHub repository or contact the maintainer.
