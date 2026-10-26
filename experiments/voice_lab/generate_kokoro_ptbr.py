"""Generate the same NekoMind phrase with compact local pt-BR neural TTS."""

import argparse
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from kokoro import KPipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default="Oi! Eu sou a NekoMind. Me conta: como a água vira vapor?")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--second-out", type=Path)
    parser.add_argument("--second-text", default="Que legal! E o que acontece com o vapor quando ele esfria?")
    parser.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    args = parser.parse_args()

    torch.manual_seed(7)
    started = time.perf_counter()
    print(f"Loading Kokoro pt-BR on {args.device}...", flush=True)
    pipeline = KPipeline(lang_code="p", device=args.device, repo_id="hexgrad/Kokoro-82M")
    loaded = time.perf_counter()
    print(f"Model ready in {loaded - started:.1f}s", flush=True)
    for phrase, destination in [(args.text, args.out), (args.second_text, args.second_out)]:
        if destination is None:
            continue
        print(f"Generating: {phrase}", flush=True)
        speech_started = time.perf_counter()
        chunks = [audio.cpu().numpy() if isinstance(audio, torch.Tensor) else audio
                  for _, _, audio in pipeline(phrase, voice="pf_dora", speed=1.0)]
        if not chunks:
            raise RuntimeError("Kokoro returned no audio")
        waveform = np.concatenate(chunks)
        destination.parent.mkdir(parents=True, exist_ok=True)
        sf.write(destination, waveform, 24000, subtype="PCM_16")
        print(
            f"Saved {destination} | {len(waveform) / 24000:.2f}s audio "
            f"| synthesis {time.perf_counter() - speech_started:.1f}s",
            flush=True,
        )


if __name__ == "__main__":
    main()
