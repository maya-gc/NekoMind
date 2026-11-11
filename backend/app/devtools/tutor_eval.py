"""Measure how often the AI tutor judges explanations correctly.

    python -m app.devtools.tutor_eval                     # modelo da configuracao
    python -m app.devtools.tutor_eval --modelo qwen2.5:14b

24 reference explanations (simple and advanced subjects; correct, partial,
misconception and off-point). Reports exact accuracy, a lenient accuracy that
treats correto/parcial as neighbours, the confusion table and the average time.
Run it whenever the model or the tutor prompt changes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "tutor_eval.json"
NEAR = {frozenset({"correto", "parcial"}), frozenset({"parcial", "nao_mencionou"})}


def run(model: str, *, reconcile: bool = True) -> dict:
    from app.services import tutor_ai
    from app.services.content_matching import match_point

    items = json.loads(DATA.read_text(encoding="utf-8"))
    rows, confusion, times = [], Counter(), []
    for item in items:
        started = time.monotonic()
        try:
            out = tutor_ai.first_turn(item["ponto"], item["fala"], model, level="faculdade")
            got = out["assessment"]
            if reconcile:
                got = tutor_ai.reconcile(got, match_point(item["ponto"], item["fala"]).status)
        except Exception as exc:  # noqa: BLE001
            got, out = "erro", {"question": repr(exc)}
        times.append(time.monotonic() - started)
        confusion[(item["esperado"], got)] += 1
        rows.append({**item, "obtido": got, "pergunta": out.get("question", "")})
    exact = sum(r["esperado"] == r["obtido"] for r in rows)
    lenient = sum(r["esperado"] == r["obtido"] or frozenset({r["esperado"], r["obtido"]}) in NEAR
                  for r in rows)
    return {"modelo": model, "total": len(rows), "exato": exact, "tolerante": lenient,
            "segundos_medios": round(sum(times) / len(times), 1),
            "confusao": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())},
            "itens": rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Avaliação do tutor IA")
    parser.add_argument("--modelo", default=None)
    parser.add_argument("--sem-conferencia", action="store_true",
                        help="Não cruza o julgamento da IA com a cobertura por palavras")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--minimo", type=float, default=0.0,
                        help="Falha se a acurácia exata ficar abaixo (0 a 1)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from app.config import get_settings
    from app.services import tutor_ai

    model = args.modelo or get_settings().tutor_model
    if not tutor_ai.available(model):
        print(f"RESULTADO: modelo {model} indisponível no Ollama")
        return 2
    tutor_ai.warm_up(model)
    result = run(model, reconcile=not args.sem_conferencia)
    for r in result["itens"]:
        mark = "OK " if r["esperado"] == r["obtido"] else "-- "
        print(f"{mark}{r['esperado']:<13} -> {r['obtido']:<13} {r['fala'][:60]}")
    total = result["total"]
    print(f"\nExato: {result['exato']}/{total}  Tolerante: {result['tolerante']}/{total}  "
          f"Tempo médio: {result['segundos_medios']} s")
    print("Confusão:", json.dumps(result["confusao"], ensure_ascii=False))
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = result["exato"] / total >= args.minimo
    print("RESULTADO:", "APROVADO" if ok else "ABAIXO DO MÍNIMO")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
