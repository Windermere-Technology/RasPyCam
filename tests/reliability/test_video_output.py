"""Exercise real FFmpeg output without opening the Raspberry Pi camera."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from utilities.video_output import RecordingOutput


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class VideoOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.tmp.name)
        raw = cls.directory / 'sample.h264'
        subprocess.run([
            'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x120:rate=25',
            '-t', '8', '-c:v', 'libx264', '-threads', '1', '-preset', 'ultrafast',
            '-g', '25', '-x264-params', 'aud=1', '-f', 'h264', str(raw),
        ], check=True, timeout=30)
        marker = b'\x00\x00\x00\x01\x09'
        cls.frames = [marker + frame for frame in raw.read_bytes().split(marker)[1:]]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def feed(self, output):
        for frame in self.frames:
            output.outputframe(frame)
            time.sleep(0.04)

    def probe(self, path):
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name',
            '-of', 'json', str(path),
        ], capture_output=True, text=True, timeout=15, check=True)
        self.assertEqual(json.loads(result.stdout)['streams'][0]['codec_name'], 'h264')
        # Decode every retained frame as well as checking the MP4 container.
        subprocess.run(['ffmpeg', '-v', 'error', '-threads', '1', '-i', str(path),
                        '-fps_mode', 'passthrough', '-f', 'null', '-'], check=True, timeout=30)

    def test_normal_stop_is_playable(self):
        path = self.directory / 'normal recording.mp4'
        output = RecordingOutput(str(path))
        output.start()
        try:
            self.feed(output)
        finally:
            output.stop()
        self.probe(path)

    def test_completed_fragments_survive_ffmpeg_sigkill(self):
        path = self.directory / 'interrupted.mp4'
        output = RecordingOutput(str(path))
        output.start()
        try:
            self.feed(output)
            deadline = time.monotonic() + 10
            while not path.exists() or path.stat().st_size < 10000:
                if time.monotonic() > deadline:
                    self.fail('FFmpeg did not flush a fragment')
                time.sleep(0.05)
            output.ffmpeg.kill()
            with self.assertRaises(RuntimeError):
                output.stop()
        finally:
            if output.ffmpeg is not None:
                output.stop()
        self.probe(path)
