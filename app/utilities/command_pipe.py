"""Read newline-delimited FIFO commands without assuming read boundaries."""
import os
from collections import deque


class CommandReader:
    def __init__(self, max_length=256):
        self.max_length = max_length
        self.buffer = bytearray()
        self.commands = deque()
        self.discarding = False

    def read(self, fd):
        if self.commands:
            return self.commands.popleft()
        try:
            data = os.read(fd, 4096)
        except BlockingIOError:
            return None
        # A writer closing the pipe also terminates a legacy command without LF.
        if not data and self.buffer:
            data = b"\n"
        for byte in data:
            if byte == 10:
                if not self.discarding and self.buffer:
                    try:
                        self.commands.append(self.buffer.decode("utf-8").rstrip())
                    except UnicodeDecodeError:
                        pass  # Reject this command, preserving subsequent commands.
                self.buffer.clear()
                self.discarding = False
            elif not self.discarding:
                self.buffer.append(byte)
                if len(self.buffer) > self.max_length:
                    self.buffer.clear()
                    self.discarding = True
        if not data:
            self.discarding = False
        return self.commands.popleft() if self.commands else None
