"""A spoken prompt must never overlap a newly started microphone capture."""

from app.mac.bridge import MacBridge
from app.mac.speaker import KokoroSpeaker
from tests.test_mac_bridge import Backend, Recorder, command


class Speaker:
    def __init__(self):
        self.active = False
        self.lines = []
        self.stops = 0
        self.closed = False

    def speak(self, text):
        self.lines.append(text)
        self.active = True

    def stop(self):
        self.stops += 1
        self.active = False

    def close(self):
        self.closed = True


class GuardedRecorder(Recorder):
    def __init__(self, path, speaker):
        super().__init__(path)
        self.speaker = speaker

    def start(self, sid):
        assert not self.speaker.active, "speaker still audible when capture starts"
        super().start(sid)

    def resume(self):
        assert not self.speaker.active, "speaker still audible when capture resumes"
        super().resume()


def test_voice_prompts_follow_capture_boundaries_and_result_is_spoken_once(tmp_path):
    speaker = Speaker()
    recorder = GuardedRecorder(tmp_path / "capture.raw", speaker)
    bridge = MacBridge(Backend(), recorder, tmp_path / "journal.db", speaker=speaker)

    bridge.handle(command("diagnose", "diagnose"))
    bridge.wait_for_operations()
    assert speaker.active and "começar" in speaker.lines[-1]

    sid = bridge.handle(command("start", "start"))["session_id"]
    assert not speaker.active
    bridge.handle(command("pause", "pause", sid))
    assert speaker.active and "continuar" in speaker.lines[-1]
    bridge.handle(command("resume", "resume", sid))
    assert not speaker.active

    bridge.handle(command("finish", "finish", sid))
    assert speaker.active and "organizar" in speaker.lines[-1]
    bridge.wait_for_analysis()
    bridge.handle(command("status", "status", sid))
    result_lines = [line for line in speaker.lines if "demonstração terminou" in line]
    assert len(result_lines) == 1
    bridge.handle(command("status", "status-again", sid))
    assert sum("demonstração terminou" in line for line in speaker.lines) == 1

    bridge.handle(command("retry", "retry", sid))
    assert not speaker.active
    bridge.close()
    assert speaker.closed


def test_player_is_gone_before_capture_can_resume(tmp_path):
    class Playback:
        def __init__(self):
            self.terminated = False
            self.waited = False

        def poll(self):
            return None if not self.terminated else -15

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            self.waited = True
            return -15

    speaker = KokoroSpeaker(tmp_path)
    playback = Playback()
    speaker.playback = playback
    speaker.stop()
    assert playback.terminated and playback.waited
    speaker.close()
