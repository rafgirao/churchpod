import ffmpeg
import os

class Cutter:
    def __init__(self, output_dir="cuts"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def cut_video(self, input_path, start_time, end_time, output_name):
        """
        Cuts the video using ffmpeg.
        Uses '-c copy' for efficiency if possible.
        """
        output_path = os.path.join(self.output_dir, output_name)
        
        if os.path.exists(output_path):
            os.remove(output_path)

        try:
            # -ss [start] -to [end] -c copy
            (
                ffmpeg
                .input(input_path, ss=start_time, to=end_time)
                .output(output_path, c='copy')
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return output_path
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
                    .output(output_path)
                    .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
                )
                return output_path
            except ffmpeg.Error as e2:
                if e2.stderr:
                    print(f"Fallback FFmpeg error: {e2.stderr.decode()}")
                else:
                    print(f"Fallback FFmpeg error: {e2}")
                return None

if __name__ == "__main__":
    pass
