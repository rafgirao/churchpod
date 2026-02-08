import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from src.paths import PROJECT_ROOT

load_dotenv()

class Segmenter:
    def __init__(self, prompts_dir=None):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("Warning: OPENAI_API_KEY not found in environment. OpenAI detection will fail.")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.prompts_dir = Path(prompts_dir) if prompts_dir else PROJECT_ROOT / "prompts"
        
        # Load prompts
        self.detection_prompt_tpl = self._load_prompt("detection_prompt.txt")
        self.metadata_prompt_tpl = self._load_prompt("metadata_prompt.txt")

    def _load_prompt(self, filename):
        path = self.prompts_dir / filename
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def detect_preaching_segment(self, transcript):
        """
        Uses OpenAI to analyze transcript and find the start and end of the preaching.
        Returns (start_time, end_time) in seconds.
        """
        if not transcript:
            return None, None

        if not self.client or not self.detection_prompt_tpl:
            print("OpenAI client or prompt template missing. Falling back to heuristics.")
            return self._heuristic_fallback(transcript)

        # 1. Prepare a compact version of the transcript for the LLM
        compact_transcript = ""
        last_minute = -1
        for entry in transcript:
            minute = int(entry['start'] // 60)
            if minute != last_minute:
                compact_transcript += f"[{entry['start']:.0f}s] {entry['text']}\n"
                last_minute = minute
            elif len(entry['text']) > 50:
                compact_transcript += f"[{entry['start']:.0f}s] {entry['text']}\n"

        prompt = self.detection_prompt_tpl.format(transcript=compact_transcript)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes church service video transcripts."},
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" }
            )
            
            result = json.loads(response.choices[0].message.content)
            start = result.get("start_seconds")
            end = result.get("end_seconds")
            print(f"OpenAI Detection Reason: {result.get('reason')}")
            return start, end

        except Exception as e:
            print(f"Error calling OpenAI API for detection: {e}")
            return self._heuristic_fallback(transcript)

    def generate_metadata(self, transcript, start_time, end_time):
        """
        Uses OpenAI to generate Title, Description and Tags based on the preaching segment.
        """
        if not self.client or not self.metadata_prompt_tpl:
            return None

        # Extract only the relevant part of the transcript
        relevant_text = ""
        for entry in transcript:
            if start_time <= entry['start'] <= end_time:
                relevant_text += entry['text'] + " "
                if len(relevant_text) > 4000: # Limit context for metadata
                    break

        prompt = self.metadata_prompt_tpl.format(
            start_time=start_time, 
            end_time=end_time, 
            transcript=relevant_text
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a YouTube SEO expert for church channels."},
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" }
            )
            
            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"Error calling OpenAI API for metadata: {e}")
            return None

    def _heuristic_fallback(self, transcript):
        """Old keyword-based logic as a fallback."""
        probable_start = 0
        for entry in transcript:
            if entry['start'] > 600 and ("bible" in entry['text'].lower() or "word" in entry['text'].lower()):
                probable_start = entry['start']
                break
        probable_end = transcript[-1]['start']
        return probable_start, probable_end

if __name__ == "__main__":
    pass
