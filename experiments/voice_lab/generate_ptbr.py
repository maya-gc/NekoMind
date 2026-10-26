"""Generate a short, local Brazilian Portuguese speech sample for NekoMind."""

import argparse
import time
from pathlib import Path

import soundfile as sf
import torch

from chatterbox.tts import ChatterboxTTS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default="Oi! Eu sou a NekoMind. Me conta: como a água vira vapor?")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--second-out", type=Path)
    parser.add_argument("--second-text", default="Que legal! E o que acontece com o vapor quando ele esfria?")
    parser.add_argument("--exaggeration", type=float, default=0.65)
    parser.add_argument("--cfg-weight", type=float, default=0.35)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    args = parser.parse_args()

    torch.manual_seed(7)
    started = time.perf_counter()
    print(f"Loading pt-BR model on {args.device}...", flush=True)
    model = ChatterboxTTS.from_pretrained(torch.device(args.device))
    loaded = time.perf_counter()
    print(f"Model ready in {loaded - started:.1f}s", flush=True)
    for phrase, destination in [(args.text, args.out), (args.second_text, args.second_out)]:
        if destination is None:
            continue
        print(f"Generating: {phrase}", flush=True)
        speech_started = time.perf_counter()
        audio = model.generate(
            phrase,
            audio_prompt_path=str(args.prompt) if args.prompt else None,
            exaggeration=args.exaggeration,
            cfg_weight=args.cfg_weight,
            temperature=args.temperature,
            language_id="pt",
        )
        waveform = audio.squeeze(0).cpu().numpy()
        destination.parent.mkdir(parents=True, exist_ok=True)
        sf.write(destination, waveform, model.sr, subtype="PCM_16")
        print(
            f"Saved {destination} | {len(waveform) / model.sr:.2f}s audio "
            f"| synthesis {time.perf_counter() - speech_started:.1f}s",
            flush=True,
        )


if __name__ == "__main__":
    main()
