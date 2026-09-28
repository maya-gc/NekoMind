from threading import Event
from time import monotonic

from app.mac.partials import PartialTranscriber


class FakeASR:
    def transcribe_pcm(self, pcm):
        assert len(pcm) <= 16000 * 2 * 6
        return "As plantas usam luz e agua."


def test_provisional_window_is_bounded_and_stops_without_disk(tmp_path):
    arrived = Event()
    observed = []
    worker = PartialTranscriber(
        FakeASR(),
        lambda text, latency: (observed.append((text, latency)), arrived.set()),
        interval_seconds=0,
        window_seconds=6,
    )
    worker.start()
    worker.offer(b"\x00\x00" * 16000 * 3)
    assert arrived.wait(2)
    assert observed[0][0] == "As plantas usam luz e agua."
    assert observed[0][1] >= 0
    worker.stop()
    assert not list(tmp_path.iterdir())


def test_backpressure_discards_old_audio_and_stop_is_nonblocking():
    worker = PartialTranscriber(FakeASR(), lambda *_: None, interval_seconds=30)
    for _ in range(80):
        worker.offer(b"\x00\x00" * 480)
    assert worker.dropped_windows > 0
    started = monotonic()
    worker.stop()
    assert monotonic() - started < 0.1
