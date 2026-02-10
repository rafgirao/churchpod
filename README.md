# ChurchPod 🎙️🏛️

**ChurchPod** is an AI-powered tool that automatically cuts church YouTube videos into podcast episodes. It finds the preaching part, generates titles and descriptions, and uploads to YouTube and Cloudflare R2 for easy podcast distribution.

## What It Does

- Downloads church service videos from YouTube
- Uses AI to detect the preaching segment
- Cuts the video to just the sermon
- Generates optimized metadata (title, description, tags)
- Uploads the cut video to YouTube (unlisted)
- Extracts MP3 for podcast platforms
- Uploads to Cloudflare R2 and generates a Supabase RSS feed for Spotify/Apple Podcasts

## Quick Start

### Step 1: Install Required Software

1. **Python**: Download from https://python.org (version 3.8 or higher) or via Homebrew: `brew install python`
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

### Step 4: Create Virtual Environment

A virtual environment is highly recommended to keep dependencies isolated and allow the auto-update scripts to work correctly:

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 5: Install Dependencies

After activating the environment, install the required packages:

```bash
python3 -m pip install -r config/requirements.txt
```

### Step 6: Get OpenAI API Key

- Go to https://platform.openai.com/api-keys
- Create a new API key
- Add it to `OPENAI_API_KEY` in your `.env` file

### Step 7: Configure YouTube API

- Go to https://console.cloud.google.com/
- Create a new project or select existing
- Enable **YouTube Data API v3**
- In "APIs & Services" > "OAuth consent screen", set it up as "External" and add yourself as a test user.
- In "APIs & Services" > "Credentials", create an **OAuth 2.0 Client ID** (Type: Desktop App).
- Download the JSON file, rename it to `client_secrets.json`, and place it in the `credentials/` folder.

### Step 8: Setup Cloudflare R2

ChurchPod uses **Cloudflare R2** for hosting large media files (MP3/Images).

*   Create a bucket in [Cloudflare R2](https://dash.cloudflare.com/).
*   Enable "Public Access" or set up a Custom Domain for the bucket.
*   Add your `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_PUBLIC_URL` to `.env`.

### Step 9: Setup Supabase (Database & RSS)

1.  Create a project at [supabase.com](https://supabase.com/).
2.  **Database Setup**: Copy the content of `scripts/setup_supabase.sql` and run it in the **SQL Editor** of your Supabase dashboard.
3.  **Install Supabase CLI**: `brew install supabase/tap/supabase`.
4.  **Link Project**:
    ```bash
    supabase login
    supabase link --project-ref <your-project-id>
    ```
5.  **Deploy RSS Function**:
    ```bash
    supabase functions deploy rss
    ```
6.  Your RSS feed URL will be: `https://<your-project-id>.supabase.co/functions/v1/rss`

### Step 10: Run ChurchPod

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
- **R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_URL**: For Cloudflare R2 cloud storage.
- **SUPABASE_URL, SUPABASE_KEY**: For database storage and Edge Functions.
- **SPOTIFY_DRIVE_FOLDER_ID**: (Legacy) Google Drive folder ID for MP3 storage.

Get detailed instructions for each service in the links provided in `config/.env.example`.

## Features in Detail

- **Automatic Download**: Gets the best quality video from YouTube
- **Smart Detection**: Analyzes the transcript to find preaching start/end
- **AI Metadata**: Creates SEO-friendly titles, descriptions, and tags
- **Fast Cutting**: Uses FFmpeg for lossless video cutting
- **YouTube Upload**: Posts as unlisted videos on your channel
- **Podcast Support**: Generates MP3s and RSS feeds for Spotify/Apple Podcasts
- **Hybrid Storage**: Stores files in R2 and metadata in Supabase for high performance
- **Dynamic RSS**: Generates an optimized podcast feed via Supabase Edge Functions

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
