"""Record your own spoken answers to use in the automated pipeline.

    python -m app.devtools.gravar_voz                 # grava as 4 respostas
    python -m app.devtools.gravar_voz --segundos 10

Files go to backend/storage/voz_real/ (outside git: it is your voice). Then:
    python -m app.devtools.pipeline --asr whisper --cenario voz_real
runs the guided flow with YOUR voice, your microphone and real transcription.
Record each prompt twice in different conditions (quiet room, with noise) by
renaming the folder between rounds if you want both sets.
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[2] / "storage" / "voz_real"
PROMPTS = [
    ("agua_1", "Ciclo da água, 1ª resposta: explique só que a água do mar evapora com o calor do Sol."),
    ("agua_2", "Ciclo da água, 2ª resposta: explique que o vapor sobe, esfria e forma as nuvens."),
    ("quantico_1", "Hamiltoniana, 1ª resposta: diga que ela representa a energia total do sistema."),
    ("quantico_2", ("Hamiltoniana, 2ª resposta: explique que ela faz o estado evoluir no "
                    "tempo pela equação de Schrödinger.")),
]


def record(path: Path, seconds: float) -> None:
    import sounddevice as sd

    frames = sd.rec(int(16000 * seconds), samplerate=16000, channels=1, dtype="int16")
    sd.wait()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(frames.tobytes())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gravar suas respostas para a pipeline")
    parser.add_argument("--segundos", type=float, default=8)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name, prompt in PROMPTS:
        input(f"\n{prompt}\nAperte Enter e fale por {args.segundos:.0f} s...")
        record(FOLDER / f"{name}.wav", args.segundos)
        print(f"Gravado: {FOLDER / (name + '.wav')}")
    print("\nPronto. Rode: python -m app.devtools.pipeline --asr whisper --cenario voz_real")
    return 0


if __name__ == "__main__":
    sys.exit(main())
