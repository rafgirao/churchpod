import ffmpeg
import os
from pathlib import Path
from src.paths import PROJECT_ROOT

class Cutter:
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "cuts"
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def cut_video(self, input_path, start_time, end_time, output_name, skip_existing=True):
        """
        Cuts the video using ffmpeg.
        Uses '-c copy' for efficiency if possible.
        """
        output_path = self.output_dir / output_name
        
        if skip_existing and output_path.exists() and output_path.stat().st_size > 0:
            print(f"Cut video {output_name} already exists. Skipping cut.")
            return str(output_path)

        if output_path.exists():
            output_path.unlink()

        try:
            # -ss [start] -to [end] -c copy
            (
                ffmpeg
                .input(input_path, ss=start_time, to=end_time)
                .output(str(output_path), c='copy')
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return str(output_path)
        except ffmpeg.Error as e:
            if e.stderr:
                print(f"FFmpeg copy error: {e.stderr.decode()}")
            else:
                print(f"FFmpeg copy error: {e}")
            
            # Fallback: re-encode if copy fails
            print("Attempting fallback with re-encoding...")
            try:
                (
                    ffmpeg
                    .input(input_path, ss=start_time, to=end_time)
                    .output(str(output_path))
                    .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
                )
                return str(output_path)
            except ffmpeg.Error as e2:
                if e2.stderr:
                    print(f"Fallback FFmpeg error: {e2.stderr.decode()}")
                else:
                    print(f"Fallback FFmpeg error: {e2}")
                return None

    def extract_audio(self, video_path, output_name, skip_existing=True):
        """
        Extracts audio from video and saves as MP3.
        """
        output_path = self.output_dir / output_name
        
        if skip_existing and output_path.exists() and output_path.stat().st_size > 0:
            print(f"MP3 {output_name} already exists. Skipping extraction.")
            return str(output_path)

        if output_path.exists():
            output_path.unlink()

        try:
            (
                ffmpeg
                .input(video_path)
                .output(str(output_path), vn=None, acodec='libmp3lame', ab='192k')
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return str(output_path)
        except ffmpeg.Error as e:
            if e.stderr:
                print(f"FFmpeg audio extraction error: {e.stderr.decode()}")
            else:
                print(f"FFmpeg audio extraction error: {e}")
            return None

if __name__ == "__main__":
    pass
