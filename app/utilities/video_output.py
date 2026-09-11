"""Video-only FFmpeg output with recoverable MP4 fragments and bounded cleanup."""
import subprocess
import os
import select
import threading
import time
from collections import deque
from utilities import diagnostics

from picamera2.outputs import FfmpegOutput
from picamera2.outputs.output import Output


class RecordingOutput(FfmpegOutput):
    MAX_BYTES = 8 * 1024 * 1024
    MAX_FRAMES = 64
    WRITE_TIMEOUT = 3.0

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        if audio:
            raise RuntimeError("Audio packets are not supported")
        if not self.recording:
            return
        diagnostics.progress("encoder:received")
        with self._condition:
            if self._closing or self._error is not None:
                return
            if len(self._queue) >= self.MAX_FRAMES or self._bytes + len(frame) > self.MAX_BYTES:
                self._error = RuntimeError("FFmpeg output queue capacity exceeded")
            else:
                self._queue.append((bytes(frame), timestamp))
                self._bytes += len(frame)
            self._condition.notify()

    def _write_frame(self, frame):
        fd = self._process.stdin.fileno()
        remaining = memoryview(frame)
        deadline = time.monotonic() + self.WRITE_TIMEOUT
        while remaining:
            if self._abort.is_set():
                raise RuntimeError("FFmpeg output drain deadline exceeded")
            if time.monotonic() >= deadline:
                raise TimeoutError("FFmpeg pipe write stalled for 3 seconds")
            try:
                written = os.write(fd, remaining)
                if not written:
                    raise BrokenPipeError("FFmpeg pipe closed")
                remaining = remaining[written:]
            except BlockingIOError:
                select.select([], [fd], [], min(0.1, max(0, deadline - time.monotonic())))

    def _writer(self):
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._queue or self._closing or self._error)
                    if self._error:
                        raise self._error
                    if not self._queue:
                        return
                    frame, timestamp = self._queue.popleft()
                if not getattr(self, "_first_frame_written", False):
                    diagnostics.event("first encoded frame write starting")
                self._write_frame(frame)
                if not getattr(self, "_first_frame_written", False):
                    diagnostics.event("first encoded frame written")
                    self._first_frame_written = True
                diagnostics.progress("encoder:written")
                self.outputtimestamp(timestamp)
                with self._condition:
                    self._bytes -= len(frame)
        except Exception as error:
            with self._condition:
                self._error = error
                self._queue.clear()
                self._bytes = 0
            diagnostics.process_snapshot(self._process.pid)
            diagnostics.incident(f"FFmpeg writer failed: {error}")
            if self.error_callback:
                self.error_callback(error)
        finally:
            self._process.stdin.close()

    def start(self):
        self._first_frame_written = False
        self._queue = deque()
        self._bytes = 0
        self._condition = threading.Condition()
        self._closing = False
        self._error = None
        self._abort = threading.Event()
        # Pass the filename as one argument (including spaces). Do not install
        # Picamera2's parent-death SIGKILL: pipe EOF lets FFmpeg finish the file
        # even if the camera process has to be killed by the watchdog.
        command = [
            "ffmpeg", "-loglevel", "warning", "-y",
            "-use_wallclock_as_timestamps", "1", "-thread_queue_size", "64",
            "-i", "-", "-c:v", "copy",
        ]
        if self.output_filename.lower().endswith(".mp4"):
            command += ["-movflags", "+frag_keyframe+empty_moov+default_base_moof",
                        "-flush_packets", "1"]
        command.append(self.output_filename)
        self.ffmpeg = subprocess.Popen(command, stdin=subprocess.PIPE, bufsize=0, start_new_session=True)
        self._process = self.ffmpeg
        diagnostics.event(f"FFmpeg started pid={self.ffmpeg.pid} output={self.output_filename}")
        os.set_blocking(self._process.stdin.fileno(), False)
        Output.start(self)
        self._thread = threading.Thread(target=self._writer, name="ffmpeg-writer", daemon=True)
        self._thread.start()

    def stop(self):
        Output.stop(self)
        process = getattr(self, "_process", None)
        if process is None:
            return
        try:
            with self._condition:
                self._closing = True
                self._condition.notify()
            self._thread.join(timeout=4)
            if self._thread.is_alive():
                self._abort.set()
                self._thread.join(timeout=1)
            if self._thread.is_alive():
                raise RuntimeError("FFmpeg writer failed to stop")
            try:
                returncode = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                returncode = process.returncode
                if self._error is None:
                    raise RuntimeError("FFmpeg did not finish within 5 seconds")
            diagnostics.event(f"FFmpeg exited status={returncode}")
            if returncode and self._error is None:
                raise RuntimeError(f"FFmpeg exited with status {returncode}")
        finally:
            self.ffmpeg = None
            self._process = None
