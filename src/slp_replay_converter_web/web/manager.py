from pathlib import Path
import shutil
import subprocess
import glob
import uuid
import re
from concurrent.futures import ThreadPoolExecutor

def remove_trailing_black(input_file: Path, output_file: Path):
    # Step 1: run ffmpeg with blackdetect and capture stderr
    detect_cmd = ["ffmpeg", "-i", input_file, "-vf", "blackdetect=d=0.5:pic_th=0.98", "-an", "-f", "null", "-"]
    result = subprocess.run(detect_cmd, stderr=subprocess.PIPE, text=True)

    # Step 2: find all black_start timestamps
    matches = re.findall(r"black_start:(\d+(\.\d+)?)", result.stderr)

    if not matches:
        print("No trailing black detected. Copying file as-is.")
        return input_file

    # last black_start (float seconds)
    last_black_start = float(matches[-1][0])
    print(f"Trimming video at {last_black_start:.2f}s")

    # Step 3: run ffmpeg again, trim before black
    trim_cmd = ["ffmpeg", "-i", input_file, "-t", str(last_black_start), "-c", "copy", output_file]
    subprocess.run(trim_cmd, check=True)
    return output_file


def _convert_replay(slp_replay: Path):
    tmpdir = Path(slp_replay).parent / f"{uuid.uuid4()}"
    if tmpdir.exists() and tmpdir.is_dir():
        shutil.rmtree(tmpdir)
    tmpdir.mkdir(parents=True)
    subprocess.run(["slp2mp4", "--output-directory", tmpdir, "single", slp_replay], check=True)
    files = glob.glob(f"{tmpdir}/*", include_hidden=True)
    if len(files) != 1:
        print(files)
        assert len(files) == 1
    converted_filepath = files[0]

    # Trim trailing blackscreen from the video (if necessary)
    trimmed_file = tmpdir / f"{uuid.uuid4()}.mp4"
    converted = remove_trailing_black(converted_filepath, trimmed_file)

    with open(converted, "r+b") as f:
        converted = f.read()
    shutil.rmtree(tmpdir)
    return converted


class Manager:
    def __init__(self, max_queue_size: int = 100):
        self.max_queue_size = max_queue_size
        self.executor = ThreadPoolExecutor(max_workers=1)

    def convert_replay(self, slp_replay: Path) -> bytes:
        res = self.executor.submit(_convert_replay(slp_replay)).result()
        return res

    def get_queue_size(self) -> int:
        # TODO: Implement
        return 0

    def get_task_result(self, task_id: str) -> bytes | None:
        # TODO: Implement
        return None
