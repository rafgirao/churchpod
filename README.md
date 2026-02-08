# YouTube Preaching Cutter

This tool automates the extraction and re-uploading of preaching segments from YouTube church service videos.

## Features
- **Automatic Download**: Uses `yt-dlp` to fetch the service video in maximum quality.
- **Smart Detection**: Uses OpenAI (GPT-4o-mini) to analyze transcripts and find the preaching start and end.
- **AI Metadata**: Automatically generates optimized Titles, Descriptions, and Tags for YouTube.
- **Fast Cutting**: Uses FFmpeg stream copy to cut the video without losing quality.
- **Automated Upload**: Re-uploads the preaching segment to your YouTube channel as "unlisted".

## Prerequisites

1.  **FFmpeg**: Must be installed on your system.
2.  **OpenAI API Key**: Required for smart detection and metadata generation.
3.  **YouTube API Credentials**:
    - Go to [Google Cloud Console](https://console.cloud.google.com/).
    - Enable **YouTube Data API v3**.
    - Download `client_secrets.json` to the project directory.

## How to Use

### Setup
1. Create a `.env` file from `config/.env.example` (save it as `config/.env`) and add your `OPENAI_API_KEY`.
2. Install dependencies: `pip install -r config/requirements.txt`.
3. Ensure your YouTube credentials are in `credentials/client_secrets.json`.

### 1. Run and Upload (Default)
To automatically cut, generate metadata, and upload as **unlisted**:
```bash
./ytcut https://www.youtube.com/watch?v=dftum0wiBNU
```
*Note: The first time you run this, it will open a browser window for Google Authorization.*

### 2. Local Cut Only
To cut a video and save it locally without uploading:
```bash
./ytcut https://www.youtube.com/watch?v=dftum0wiBNU --no-upload
```
*Note: The first time you run this, it will open a browser window for Google Authorization.*

## Project Structure
- `ytcut`: Executable shortcut for the tool.
- `scripts/main.py`: Main CLI orchestration (entry point).
- `src/`: Core logic modules.
- `config/`: Configuration files and dependencies (`requirements.txt`, `.env`).
- `prompts/`: OpenAI prompt templates.
- `credentials/`: YouTube API secrets and tokens.
- `downloads/`: Raw video and transcript storage.
- `cuts/`: Final output storage.

## Detection Logic
The script uses OpenAI to identify the transition from worship to preaching by analyzing the context of the transcript, looking for biblical citations, opening of the Word, and the concluding appeal/prayer.
