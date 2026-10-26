"""Back-transcribe generated speech to catch gross pronunciation errors."""

import argparse
import time

from faster_whisper import WhisperModel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio")
    parser.add_argument("--model", default="base")
    args = parser.parse_args()

    started = time.perf_counter()
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(args.audio, language="pt", beam_size=3)
    transcription = " ".join(segment.text.strip() for segment in segments)
    print(f"language={info.language} elapsed={time.perf_counter() - started:.1f}s")
    print(transcription)


if __name__ == "__main__":
    main()
