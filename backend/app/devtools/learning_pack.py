"""Validate and move curated pedagogical examples between local computers.

This module does not train a model.  It exports deterministic JSONL that may be
reviewed before a separate, explicit fine-tuning experiment.  Raw sessions are
never accepted by the portable schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = "nekomind-learning-pack-v1"
PROMPT_VERSION = "child-tutor-v1"
FORBIDDEN_KEYS = {
    "audio", "audio_path", "name", "path", "session_id", "token", "transcript",
    "transcription",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[-\s]?\d{4}(?!\d)")
LOCAL_PATH = re.compile(r"(?:[A-Za-z]:\\|/(?:home|Users|tmp|var)/)")
TOKEN_VALUE = re.compile(r"\b(?:bearer\s+|sk-[A-Za-z0-9_-]{12,})", re.IGNORECASE)


class LearningPackError(ValueError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()


def _checksum(payload: dict) -> str:
    clean = {key: value for key, value in payload.items() if key != "checksum"}
    return hashlib.sha256(_canonical(clean)).hexdigest()


def _walk(value: object, path: str = "example"):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in FORBIDDEN_KEYS:
                raise LearningPackError(f"Campo privado proibido: {path}.{key}")
            _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]")
    elif isinstance(value, str) and (
        EMAIL.search(value) or PHONE.search(value) or LOCAL_PATH.search(value)
        or TOKEN_VALUE.search(value)
    ):
        raise LearningPackError(f"Possível dado pessoal, token ou caminho em {path}")


def _example_id(example: dict) -> str:
    identity = {
        "source_hash": example["source_hash"],
        "instruction": " ".join(example["instruction"].split()),
        "response": " ".join(example["response"].split()),
    }
    return hashlib.sha256(_canonical(identity)).hexdigest()


def validate_example(example: object) -> dict:
    if not isinstance(example, dict):
        raise LearningPackError("Exemplo precisa ser um objeto.")
    _walk(example)
    required = {"approved", "source_hash", "instruction", "response"}
    if not required <= example.keys() or set(example) - required - {"audience", "skill"}:
        raise LearningPackError("Campos do exemplo inválidos.")
    if example["approved"] is not True:
        raise LearningPackError("Somente exemplos aprovados podem ser portados.")
    if not isinstance(example["source_hash"], str) or not HEX64.fullmatch(example["source_hash"]):
        raise LearningPackError("source_hash inválido.")
    for field in ("instruction", "response"):
        value = example[field]
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise LearningPackError(f"{field} precisa ter de 1 a 4000 caracteres.")
    if example.get("audience", "crianca") != "crianca":
        raise LearningPackError("Este corpus aceita somente o perfil infantil revisado.")
    skill = example.get("skill", "explain")
    if skill not in {"recall", "identify", "sequence", "compare", "apply", "explain"}:
        raise LearningPackError("Habilidade inválida.")
    return {
        "approved": True,
        "source_hash": example["source_hash"],
        "instruction": " ".join(example["instruction"].split()),
        "response": " ".join(example["response"].split()),
        "audience": "crianca",
        "skill": skill,
    }


def make_pack(
    examples: list[dict], *, base_model: str = "qwen2.5:7b", license_name: str = "review-required",
) -> dict:
    validated = [validate_example(example) for example in examples]
    unique = {_example_id(example): example for example in validated}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "base_model": str(base_model)[:100],
        "license": str(license_name)[:100],
        "examples": [unique[key] for key in sorted(unique)],
    }
    payload["checksum"] = _checksum(payload)
    return payload


def validate_pack(pack: object) -> dict:
    if not isinstance(pack, dict) or pack.get("schema_version") != SCHEMA_VERSION:
        raise LearningPackError("Versão do pacote inválida.")
    if set(pack) != {
        "schema_version", "prompt_version", "base_model", "license", "examples", "checksum",
    }:
        raise LearningPackError("Campos do pacote inválidos.")
    if pack.get("prompt_version") != PROMPT_VERSION:
        raise LearningPackError("Versão do prompt incompatível.")
    if not isinstance(pack.get("base_model"), str) or not pack["base_model"].strip():
        raise LearningPackError("Modelo-base ausente.")
    if not isinstance(pack.get("license"), str) or not pack["license"].strip():
        raise LearningPackError("Licença precisa ser revisada e registrada.")
    if not isinstance(pack.get("examples"), list):
        raise LearningPackError("Lista de exemplos inválida.")
    examples = [validate_example(example) for example in pack["examples"]]
    ids = [_example_id(example) for example in examples]
    if len(ids) != len(set(ids)):
        raise LearningPackError("O pacote contém exemplos duplicados.")
    if not isinstance(pack.get("checksum"), str) or pack["checksum"] != _checksum(pack):
        raise LearningPackError("Checksum do pacote não confere.")
    return pack


def load_pack(path: Path) -> dict:
    try:
        return validate_pack(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise LearningPackError("Não foi possível ler o pacote.") from exc


def import_pack(incoming: dict, store_path: Path) -> dict:
    incoming = validate_pack(incoming)
    if store_path.exists():
        current = load_pack(store_path)
        examples = current["examples"] + incoming["examples"]
        base_model, license_name = current["base_model"], current["license"]
    else:
        examples = incoming["examples"]
        base_model, license_name = incoming["base_model"], incoming["license"]
    merged = make_pack(examples, base_model=base_model, license_name=license_name)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return merged


def _split(source_hash: str) -> str:
    return "validation" if int(source_hash[:8], 16) % 5 == 0 else "train"


def export_jsonl(pack: dict, output_dir: Path) -> dict:
    pack = validate_pack(pack)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = {"train": [], "validation": []}
    for example in sorted(pack["examples"], key=_example_id):
        split = _split(example["source_hash"])
        rows[split].append({
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Você é uma tutora infantil local. Faça perguntas claras, "
                        "ancoradas no conteúdo e sem dar a resposta."
                    ),
                },
                {"role": "user", "content": example["instruction"]},
                {"role": "assistant", "content": example["response"]},
            ],
            "source_hash": example["source_hash"],
            "skill": example["skill"],
        })
    file_hashes = {}
    for split, values in rows.items():
        path = output_dir / f"{split}.jsonl"
        content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values)
        path.write_text(content, encoding="utf-8")
        file_hashes[path.name] = hashlib.sha256(content.encode()).hexdigest()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "base_model": pack["base_model"],
        "license": pack["license"],
        "counts": {key: len(value) for key, value in rows.items()},
        "files": file_hashes,
        "pack_checksum": pack["checksum"],
        "trained": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pacote pedagógico curado; não treina modelos.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("pack", type=Path)
    import_cmd = sub.add_parser("import")
    import_cmd.add_argument("pack", type=Path)
    import_cmd.add_argument("--store", type=Path, required=True)
    export_cmd = sub.add_parser("export-jsonl")
    export_cmd.add_argument("pack", type=Path)
    export_cmd.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        pack = load_pack(args.pack)
        if args.command == "import":
            result = import_pack(pack, args.store)
            print(f"Importado: {len(result['examples'])} exemplo(s) curado(s).")
        elif args.command == "export-jsonl":
            result = export_jsonl(pack, args.out)
            print(f"JSONL validado: {result['counts']}")
        else:
            print(f"Pacote válido: {len(pack['examples'])} exemplo(s) curado(s).")
        return 0
    except LearningPackError as exc:
        print(f"ERRO: {exc}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
