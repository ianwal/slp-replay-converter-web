from pathlib import Path
import shutil
import subprocess
import glob
import uuid
import re
from dataclasses import dataclass
import queue
import threading
import io
import time


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


@dataclass
class ConvertTask:
    task_id: str
    slp_replay: Path
    filename: str  # The resulting filename, e.g., foo.mp4


@dataclass
class ConvertTaskResult:
    task_id: str
    converted_replay: bytes
    filename: str


class Manager:
    def __init__(self, max_queue_size: int = 100):
        self.task_queue = queue.Queue(maxsize=max_queue_size)
        self.finished_tasks: dict[str, ConvertTaskResult] = {}
        self.finished_tasks_lock = threading.Lock()
        self.convert_thread = threading.Thread(target=self._convert_thread_loop)
        self.convert_thread.start()
        # TODO: Periodically cleanup old slp files.

    def convert_replay(self, slp_replay: Path) -> bytes:
        res = _convert_replay(slp_replay)
        return res

    def get_queue_size(self) -> int:
        return self.task_queue.qsize()

    def push_convert_task(self, slp_replay: Path, filename: str) -> int:
        task = ConvertTask(task_id=str(uuid.uuid4()), slp_replay=slp_replay, filename=filename)
        self.task_queue.put(task)
        return task.task_id

    def _convert_thread_loop(self):
        while True:
            task: ConvertTask = self.task_queue.get()
            converted = self.convert_replay(task.slp_replay)
            result = ConvertTaskResult(task_id=task.task_id, converted_replay=converted, filename=task.filename)

            with self.finished_tasks_lock:
                self.finished_tasks[task.task_id] = result

    def get_task_result(self, task_id: str) -> ConvertTaskResult | None:
        # Sanity check
        if not isinstance(task_id, str):
            return None

        try:
            with self.finished_tasks_lock:
                return self.finished_tasks[task_id]
        except KeyError:
            return None
