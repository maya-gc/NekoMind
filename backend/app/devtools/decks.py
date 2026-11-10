"""Ready-made study decks (simple and advanced) for the content library.

    python -m app.devtools.decks            # importa os que ainda nao existem
    python -m app.devtools.decks --listar

After importing they appear in /presenter to be selected for the next session.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DECKS = Path(__file__).resolve().parents[1] / "data" / "decks.json"


def load() -> list[dict]:
    return json.loads(DECKS.read_text(encoding="utf-8"))


def import_decks(client) -> list[str]:
    existing = {row["title"] for row in client.get("/api/v1/contents").json()}
    created = []
    for deck in load():
        if deck["title"] in existing:
            continue
        response = client.post("/api/v1/contents", json={
            "title": deck["title"], "text": deck["text"], "points": deck["points"]})
        response.raise_for_status()
        created.append(deck["title"])
    return created


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Decks prontos do NekoMind")
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.listar:
        for deck in load():
            print(f"[{deck['nivel']}] {deck['title']}: {len(deck['points'])} missões")
        return 0
    from fastapi.testclient import TestClient

    from app.main import app
    from app.security import operator_token

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {operator_token()}"
        created = import_decks(client)
    print("Importados:", ", ".join(created) if created else "nenhum (já existiam)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
