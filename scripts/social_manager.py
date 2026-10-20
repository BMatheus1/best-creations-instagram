"""Best Creations — fila de publicações, começando em modo simulação.

Não realiza chamadas de publicação. Somente valida conteúdo e autorizações.
A publicação real será implementada após aprovação de um teste.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "content" / "queue.json"
ALLOWED_TYPES = {"IMAGE", "CAROUSEL", "REEL", "STORY"}
ALLOWED_STATES = {"draft", "approved", "cancelled", "published"}


def read_queue(path=QUEUE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("A fila precisa ser uma lista JSON.")
    ids = set()
    for item in data:
        validate_item(item)
        if item["id"] in ids:
            raise ValueError("ID duplicado na fila: " + item["id"])
        ids.add(item["id"])
    return data


def validate_item(item):
    if not isinstance(item, dict):
        raise ValueError("Publicação inválida")
    if not isinstance(item.get("id"), str) or not item["id"].strip():
        raise ValueError("Toda publicação precisa de um id.")
    if item.get("type") not in ALLOWED_TYPES:
        raise ValueError("Tipo inválido: " + str(item.get("type")))
    if item.get("status") not in ALLOWED_STATES:
        raise ValueError("Status inválido: " + str(item.get("status")))
    media = item.get("media_urls", [])
    if not isinstance(media, list) or not media:
        raise ValueError("media_urls precisa ter ao menos uma mídia.")
    if any(urlparse(url).scheme != "https" or not urlparse(url).netloc for url in media):
        raise ValueError("As mídias precisam usar URLs HTTPS.")
    if item["type"] != "CAROUSEL" and len(media) != 1:
        raise ValueError("Este formato requer uma única mídia.")
    if item["type"] == "CAROUSEL" and not 2 <= len(media) <= 10:
        raise ValueError("Carrossel requer entre 2 e 10 mídias.")
    if not isinstance(item.get("caption", ""), str):
        raise ValueError("Legenda deve ser texto.")
    if item["status"] == "approved":
        when = item.get("scheduled_at")
        if not isinstance(when, str):
            raise ValueError("Aprovação exige scheduled_at com fuso horário.")
        due = datetime.fromisoformat(when.replace("Z", "+00:00"))
        if due.tzinfo is None or due.utcoffset() is None:
            raise ValueError("scheduled_at precisa informar o fuso horário.")
        if item.get("approved_by") != "owner":
            raise ValueError("Aprovação exige approved_by='owner'.")


def simulate(queue, now=None):
    now = now or datetime.now(timezone.utc)
    pending = []
    for item in queue:
        if item["status"] != "approved":
            print(f"IGNORADO: {item['id']} ({item['status']})")
            continue
        when = datetime.fromisoformat(item["scheduled_at"].replace("Z", "+00:00"))
        if when <= now:
            pending.append(item)
            print(f"SIMULAÇÃO: publicaria {item['id']} ({item['type']})")
        else:
            print(f"AGENDADO: {item['id']} para {item['scheduled_at']}")
    print(f"SIMULAÇÃO FINALIZADA — {len(pending)} publicação(ões) elegível(is).")
    print("Nenhum conteúdo foi publicado. Nenhum token foi utilizado.")
    return pending


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args()
    items = read_queue(args.queue)
    print(f"Fila validada: {len(items)} conteúdo(s).")
    simulate(items)


if __name__ == "__main__":
    main()
