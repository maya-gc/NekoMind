import json

import pytest

from app.devtools.learning_pack import (
    LearningPackError,
    export_jsonl,
    import_pack,
    make_pack,
    validate_pack,
)


def example(source_hash="1" * 64, **changes):
    value = {
        "approved": True,
        "source_hash": source_hash,
        "instruction": "Crie uma pergunta sobre a evaporação para uma criança.",
        "response": "Por que uma poça diminui quando recebe calor?",
        "audience": "crianca",
        "skill": "explain",
    }
    value.update(changes)
    return value


def test_pack_checksum_and_approved_examples_are_strict():
    pack = make_pack([example()], base_model="local", license_name="internal-review")
    assert validate_pack(pack) is pack
    tampered = json.loads(json.dumps(pack))
    tampered["examples"][0]["response"] = "Resposta alterada."
    with pytest.raises(LearningPackError, match="Checksum"):
        validate_pack(tampered)
    with pytest.raises(LearningPackError, match="aprovados"):
        make_pack([example(approved=False)])


@pytest.mark.parametrize("private", [
    {"transcript": "fala privada"},
    {"audio": "bytes"},
    {"token": "segredo"},
    {"session_id": 7},
    {"path": "C:\\Users\\crianca\\audio.wav"},
    {"name": "nome da criança"},
])
def test_private_session_fields_are_rejected(private):
    with pytest.raises(LearningPackError, match="proibido"):
        make_pack([{**example(), **private}])


@pytest.mark.parametrize("response", [
    "Fale com aluno@example.com.",
    "O telefone é (11) 99999-0000.",
    "Leia C:\\Users\\aluno\\arquivo.txt.",
    "Use Bearer segredo-local-nao-portavel.",
])
def test_pii_tokens_and_local_paths_are_rejected(response):
    with pytest.raises(LearningPackError, match="Possível"):
        make_pack([example(response=response)])


def test_import_is_idempotent_and_deduplicates_examples(tmp_path):
    incoming = make_pack([example()], license_name="internal-review")
    store = tmp_path / "learning-pack.json"
    first = import_pack(incoming, store)
    second = import_pack(incoming, store)
    assert len(first["examples"]) == len(second["examples"]) == 1
    assert json.loads(store.read_text(encoding="utf-8"))["checksum"] == second["checksum"]


def test_jsonl_split_is_deterministic_disjoint_and_has_manifest(tmp_path):
    pack = make_pack(
        [
            example("1" * 64),
            example("0" * 64, instruction="Pergunte sobre chuva.", response="Como a chuva se forma?"),
        ],
        base_model="qwen2.5:7b",
        license_name="review-required",
    )
    first = export_jsonl(pack, tmp_path / "first")
    second = export_jsonl(pack, tmp_path / "second")
    assert first == second
    assert first["counts"] == {"train": 1, "validation": 1}
    train = (tmp_path / "first" / "train.jsonl").read_text(encoding="utf-8")
    validation = (tmp_path / "first" / "validation.jsonl").read_text(encoding="utf-8")
    assert "1" * 64 in train and "0" * 64 not in train
    assert "0" * 64 in validation and "1" * 64 not in validation
    assert not any(word in train + validation for word in ("transcript", "audio_path", "session_id"))
    manifest = json.loads((tmp_path / "first" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["trained"] is False
    assert manifest["license"] == "review-required"
