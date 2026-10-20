"""Publicador oficial Instagram API with Instagram Login.

Publicação real somente após aprovação no queue.json + confirmação no workflow,
ou agendamento explicitamente habilitado. Mantém trava persistente em state.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from social_manager import read_queue

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "publications.json"
API_BASE = "https://graph.instagram.com"
GRAPH_VERSION = "v24.0"
TARGET_USERNAME = "bestcreations011"


def git_commit_state(post_id, label):
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True, cwd=ROOT)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True, cwd=ROOT)
    subprocess.run(["git", "add", str(LEDGER.relative_to(ROOT))], check=True, cwd=ROOT)
    subprocess.run(["git", "commit", "-m", f"instagram: {label} {post_id} [skip ci]"], check=True, cwd=ROOT)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True, cwd=ROOT)


def read_ledger():
    if not LEDGER.exists():
        raise RuntimeError("Histórico de publicação ausente. Interrompendo por segurança.")
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Histórico inválido.")
    return data


def record_attempt(post_id, fields, label):
    ledger = read_ledger()
    entry = ledger.get(post_id, {})
    entry.update(fields)
    ledger[post_id] = entry
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git_commit_state(post_id, label)


def graph_request(token, method, path, fields):
    url = f"{API_BASE}/{GRAPH_VERSION}/{path.lstrip('/')}"
    query = urllib.parse.urlencode(fields)
    if method == "GET":
        url = url + "?" + query
        data = None
    else:
        data = query.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Não exibir corpo do erro: em alguns ambientes há dados sensíveis.
        raise RuntimeError(f"Erro Instagram API HTTP {exc.code} em {method} {path.split('/')[-1]}") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Falha de rede com a Meta API; NÃO repita automaticamente a publicação.") from None


def ensure_verified_account(token):
    # Instagram Login: /me devolve conta vinculada ao token.
    info = graph_request(token, "GET", "me", {"fields": "id,username"})
    if str(info.get("username", "")).lower() != TARGET_USERNAME or not info.get("id"):
        raise RuntimeError("Conta vinculada diferente de @bestcreations011. Publicação bloqueada.")
    return str(info["id"])


def validate_for_publication(item, now):
    if item["status"] != "approved" or item.get("approved_by") != "owner":
        raise RuntimeError("Post não aprovado pelo proprietário.")
    if item["type"] != "IMAGE":
        raise RuntimeError("Nesta versão, apenas imagem única no feed é suportada.")
    when = datetime.fromisoformat(item["scheduled_at"].replace("Z", "+00:00"))
    if when > now:
        raise RuntimeError("Agendamento ainda não chegou.")
    url = item["media_urls"][0]
    ext = urllib.parse.urlparse(url).path.lower()
    if not ext.endswith((".jpg", ".jpeg")):
        raise RuntimeError("Instagram exige JPEG para foto do feed. Envie URL HTTPS pública de .jpg/.jpeg.")
    if len(item.get("caption", "")) > 2200:
        raise RuntimeError("Legenda excede 2200 caracteres.")


def publish_one(post_id, token, mode, confirm):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", post_id):
        raise RuntimeError("ID inválido.")
    if mode == "manual" and confirm != f"PUBLICAR:{post_id}":
        raise RuntimeError("Confirmação inválida. Use PUBLICAR:<id>.")
    if mode == "schedule" and os.environ.get("AUTO_PUBLISH_ENABLED") != "true":
        print("Agendamento automático permanece PAUSADO.")
        return
    if mode not in ("manual", "schedule"):
        raise RuntimeError("Modo desconhecido.")

    items = read_queue()
    matches = [p for p in items if p["id"] == post_id]
    if len(matches) != 1:
        raise RuntimeError("ID não encontrado ou duplicado.")
    item = matches[0]
    validate_for_publication(item, datetime.now(timezone.utc))
    ledger = read_ledger()
    if post_id in ledger:
        raise RuntimeError(
            "Há uma tentativa registrada para este ID. Bloqueado para evitar duplicação. "
            "Confira o Instagram e o histórico antes de qualquer nova tentativa."
        )
    account_id = ensure_verified_account(token)
    # Registrar TRAVA antes de criar qualquer mídia e antes de publicar.
    record_attempt(post_id, {
        "status": "attempt_started",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "ig_media_id": None,
    }, "reserve")
    print("Tentativa registrada. Preparando mídia. Nenhuma repetição automática será feita.")
    try:
        container = graph_request(token, "POST", f"{account_id}/media", {
            "image_url": item["media_urls"][0],
            "caption": item["caption"],
        })
        container_id = str(container["id"])
        record_attempt(post_id, {"status": "container_created", "container_id": container_id}, "container")
        ready = False
        for _ in range(10):
            status = graph_request(token, "GET", container_id, {"fields": "status_code"}).get("status_code")
            if status == "FINISHED":
                ready = True
                break
            if status in ("ERROR", "EXPIRED", "PUBLISHED"):
                raise RuntimeError(f"Estado de contêiner não publicável: {status}.")
            time.sleep(3)
        if not ready:
            raise RuntimeError("Mídia não ficou pronta. Tentativa bloqueada até revisão manual.")
        record_attempt(post_id, {"status": "publish_requested"}, "publish-requested")
        # API pode ter publicado mesmo se a resposta cair: nunca dar retry automático.
        published = graph_request(token, "POST", f"{account_id}/media_publish", {
            "creation_id": container_id,
        })
        media_id = str(published["id"])
        record_attempt(post_id, {
            "status": "published",
            "ig_media_id": media_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }, "published")
        print(f"PUBLICADO com sucesso. Post: {post_id}; mídia Instagram ID: {media_id}")
    except Exception:
        print("Tentativa interrompida. NÃO execute novamente sem verificar o histórico e o Instagram.")
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--mode", choices=("manual", "schedule"), default="manual")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("INSTAGRAM_ACCESS_TOKEN ausente.")
    publish_one(args.id, token, args.mode, args.confirm)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("PUBLICAÇÃO NÃO CONFIRMADA:", str(exc), file=sys.stderr)
        sys.exit(1)
