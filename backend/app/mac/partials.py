"""Optional bounded provisional ASR; no partial is written to disk or logs."""

from __future__ import annotations

from collections import deque
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic

BYTES_PER_SECOND = 16000 * 2


class PartialTranscriber:
    def __init__(self, adapter, callback, *, interval_seconds=6.0, window_seconds=12.0):
        self.adapter, self.callback = adapter, callback
        self.interval = interval_seconds
        self.window_bytes = int(window_seconds * BYTES_PER_SECOND)
        self.queue = Queue(maxsize=64)
        self.stop_event = Event()
        self.thread = Thread(target=self._run, name="nekomind-partial-asr", daemon=True)
        self.dropped_windows = 0
        self.latency_seconds = None
        self._started = None

    def start(self):
        self._started = monotonic()
        self.thread.start()

    def offer(self, pcm: bytes):
        if self.stop_event.is_set():
            return
        try:
            self.queue.put_nowait(pcm)
        except Full:
            try:
                self.queue.get_nowait()
                self.dropped_windows += 1
                self.queue.put_nowait(pcm)
            except (Empty, Full):
                pass

    def stop(self):
        self.stop_event.set()
        # The ASR native call cannot be cancelled. It may complete in the
        # background, but no result is emitted once stop is set.

    def _run(self):
        chunks = deque()
        size = 0
        last = monotonic()
        while not self.stop_event.is_set():
            try:
                pcm = self.queue.get(timeout=0.1)
            except Empty:
                continue
            chunks.append(pcm)
            size += len(pcm)
            while size > self.window_bytes and chunks:
                first = chunks[0]
                excess = size - self.window_bytes
                if len(first) <= excess:
                    chunks.popleft()
                    size -= len(first)
                else:
                    chunks[0] = first[excess:]
                    size -= excess
            if size < BYTES_PER_SECOND * 3 or monotonic() - last < self.interval:
                continue
            # Coalesce backlog before the next expensive native ASR call.
            while True:
                try:
                    extra = self.queue.get_nowait()
                    chunks.append(extra)
                    size += len(extra)
                    self.dropped_windows += 1
                except Empty:
                    break
            data = b"".join(chunks)[-self.window_bytes :]
            last = monotonic()
            try:
                text = self.adapter.transcribe_pcm(data)
            except Exception:  # noqa: BLE001 - native ASR boundary; degrade feedback
                if not self.stop_event.is_set():
                    self.callback(None, None)
                continue
            if not self.stop_event.is_set():
                self.latency_seconds = monotonic() - last
                self.callback(text, self.latency_seconds)
