"""Lançamento Instagram: um Story ou foto por execução, sem repetição automática.

Fila: content/launch_queue.json (7 Stories seguidos de 20 fotos).
Variável de agendamento é desligada por padrão. Não cria Destaques.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "content" / "launch_queue.json"
LEDGER_PATH = ROOT / "state" / "launch_publications.json"
API_BASE = "https://graph.instagram.com/v24.0"
ACCOUNT = "bestcreations011"
STORY_COUNT = 7
FEED_COUNT = 20
# Lancamento acelerado: GitHub Actions agenda no minimo a cada 5 minutos.
# Nao elimina validacao de conta, ordem, integridade ou bloqueio de duplicidade.
STORY_GAP = timedelta(minutes=5)
FEED_GAP = timedelta(minutes=5)
FIRST_FEED_GAP = timedelta(minutes=5)
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class Blocked(RuntimeError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def read_queue():
    if not QUEUE_PATH.is_file():
        raise Blocked("O pacote do lançamento ainda não foi importado")
    data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != STORY_COUNT + FEED_COUNT:
        raise Blocked("Fila incompleta: precisamos dos 7 Stories e 20 posts")
    ids = set()
    for n, item in enumerate(data, 1):
        if not isinstance(item, dict) or item.get("sequence") != n or item.get("id") != f"bc-launch-{n:03d}":
            raise Blocked("Sequência ou identificador de publicação inválido")
        if item["id"] in ids:
            raise Blocked("ID duplicado")
        ids.add(item["id"])
        kind = "STORY" if n <= STORY_COUNT else "IMAGE"
        if item.get("media_type") != kind or item.get("channel") != ("story" if n <= STORY_COUNT else "feed"):
            raise Blocked("Ordem de Stories e feed alterada")
        if item.get("status") != "approved" or item.get("approved_by") != "owner":
            raise Blocked(f"Publicação não aprovada: {item['id']}")
        path = item.get("image_path", "")
        if not re.fullmatch(r"media/launch/\d{2}_(story|feed)\.jpg", path):
            raise Blocked("Caminho de arquivo inválido")
        if not item.get("image_url", "").startswith("https://raw.githubusercontent.com/BMatheus1/best-creations-instagram/main/media/launch/"):
            raise Blocked("Endereço de mídia fora do repositório autorizado")
        if item["image_url"].split("/")[-1] != Path(path).name:
            raise Blocked("Endereço de mídia não corresponde ao arquivo")
        caption = item.get("caption", "")
        if not isinstance(caption, str) or len(caption) > 2200:
            raise Blocked("Legenda inválida")
        if not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256", ""))):
            raise Blocked("Checksum ausente")
        file = ROOT / path
        if not file.is_file() or file.stat().st_size > MAX_IMAGE_BYTES:
            raise Blocked(f"Arquivo ausente ou grande demais: {path}")
        contents = file.read_bytes()
        if contents[:3] != b"\xff\xd8\xff" or hashlib.sha256(contents).hexdigest() != item["sha256"]:
            raise Blocked(f"Arquivo alterado/corrompido: {path}")
    return data


def read_ledger():
    if not LEDGER_PATH.is_file():
        raise Blocked("Histórico de publicação ausente")
    result = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise Blocked("Histórico de publicação inválido")
    return result


def next_item(items, ledger):
    for item in items:
        entry = ledger.get(item["id"])
        if entry is None:
            return item
        if entry.get("status") != "published":
            raise Blocked(f"Tentativa anterior pendente ({item['id']}): {entry.get('status')}. Revisão manual obrigatória")
    return None


def check_pacing(item, ledger, now):
    last = None
    for entry in ledger.values():
        if isinstance(entry, dict) and entry.get("status") == "published":
            try:
                dt = datetime.fromisoformat(entry["published_at"])
                if dt.tzinfo is None:
                    raise ValueError("Naive datetime")
                if last is None or dt > last[0]:
                    last = (dt, entry.get("channel"))
            except (KeyError, ValueError, TypeError):
                raise Blocked("Horário inválido no histórico")
    if last is None:
        return
    interval = STORY_GAP if item["channel"] == "story" else (
        FIRST_FEED_GAP if last[1] == "story" else FEED_GAP
    )
    if now < last[0] + interval:
        raise Blocked(f"Aguardando intervalo de segurança até {(last[0] + interval).isoformat()}")


def graph_request(token, method, path, fields):
    if not token:
        raise Blocked("Token Instagram não configurado")
    url = f"{API_BASE}/{path.lstrip('/')}"
    encoded = urllib.parse.urlencode(fields)
    payload = None if method == "GET" else encoded.encode("utf-8")
    if method == "GET":
        url += "?" + encoded
    request = urllib.request.Request(
        url, data=payload, method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Não imprimir JSON da Meta: pode conter dados privados.
        raise Blocked(f"Erro da API Instagram HTTP {exc.code} no endpoint {path.split('/')[-1]}") from None
    except (urllib.error.URLError, TimeoutError):
        raise Blocked("Falha de rede: não repetir publicação automaticamente") from None


def verify_account(token, item):
    info = graph_request(token, "GET", "me", {"fields": "id,username,account_type"})
    if not info.get("id") or str(info.get("username", "")).casefold() != ACCOUNT:
        raise Blocked("Token não corresponde ao @bestcreations011")
    # Em integrações com restrição a Business, não tentar Story em conta Creator.
    if item["channel"] == "story" and str(info.get("account_type", "")).upper() != "BUSINESS":
        raise Blocked("Publicação de Story requer conta empresarial Business validada")
    return str(info["id"])


def verify_public_image(item):
    """Confirma que a imagem enviada à Meta será a mesma que foi aprovada."""
    request = urllib.request.Request(
        item["image_url"],
        headers={"User-Agent": "BestCreationsLaunch/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            blob = response.read(MAX_IMAGE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, urllib.error.HTTPError):
        raise Blocked("JPEG ainda não está acessível publicamente no GitHub") from None
    if len(blob) > MAX_IMAGE_BYTES or hashlib.sha256(blob).hexdigest() != item["sha256"]:
        raise Blocked("O JPEG público não corresponde à mídia aprovada")


def commit_ledger(item_id, fields, label):
    ledger = read_ledger()
    entry = ledger.get(item_id, {})
    entry.update(fields)
    ledger[item_id] = entry
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def run(args):
        subprocess.run(args, check=True, cwd=ROOT, timeout=60, stdout=subprocess.DEVNULL)
    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    run(["git", "add", str(LEDGER_PATH.relative_to(ROOT))])
    run(["git", "commit", "-m", f"instagram-launch: {label} {item_id} [skip ci]"])
    run(["git", "push", "origin", "HEAD:main"])


def publish_item(token, item):
    account_id = verify_account(token, item)
    verify_public_image(item)
    # Reserva persistente ANTES de qualquer chamada de criação.
    commit_ledger(item["id"], {
        "status": "attempt_started", "started_at": utcnow().isoformat(),
        "channel": item["channel"], "container_id": None, "ig_media_id": None,
    }, "reserve")
    print(f"Tentativa registrada para {item['id']}. Bloqueio de duplicidade ativo.")
    try:
        fields = {"image_url": item["image_url"]}
        if item["media_type"] == "STORY":
            fields["media_type"] = "STORIES"
        else:
            fields["caption"] = item["caption"]
        media = graph_request(token, "POST", f"{account_id}/media", fields)
        container_id = str(media["id"])
        commit_ledger(item["id"], {
            "status": "container_created", "container_id": container_id,
        }, "container")
        for _ in range(12):
            state = graph_request(token, "GET", container_id, {"fields": "status_code"}).get("status_code")
            if state == "FINISHED":
                break
            if state in ("ERROR", "EXPIRED", "PUBLISHED"):
                raise Blocked(f"Contêiner em estado inesperado: {state}")
            time.sleep(5)
        else:
            raise Blocked("Contêiner não ficou pronto; revisão manual necessária")
        # A tentativa pode ter sido publicada mesmo se a rede cair: sem retry automático.
        commit_ledger(item["id"], {"status": "publish_requested"}, "publish-requested")
        result = graph_request(token, "POST", f"{account_id}/media_publish", {"creation_id": container_id})
        media_id = str(result["id"])
        commit_ledger(item["id"], {
            "status": "published", "published_at": utcnow().isoformat(),
            "ig_media_id": media_id,
        }, "published")
        print(f"PUBLICADO {item['id']} ({item['channel']}), Instagram media ID {media_id}")
    except Exception:
        print("PUBLICAÇÃO NÃO CONFIRMADA; consulte o perfil e o ledger ANTES de qualquer nova tentativa")
        raise


def execute(mode, confirm=""):
    if mode == "manual":
        if confirm != "PUBLICAR_PROXIMO" or os.environ.get("INSTAGRAM_LAUNCH_ENABLE_MANUAL") != "true":
            raise Blocked("Confirmação manual explícita obrigatória")
    elif mode == "auto":
        if os.environ.get("INSTAGRAM_LAUNCH_ENABLE_AUTO") != "true":
            raise Blocked("Automação desabilitada por padrão")
    elif mode != "dry-run":
        raise Blocked("Modo inválido")

    items = read_queue()
    ledger = read_ledger()
    pending = next_item(items, ledger)
    if pending is None:
        print("LANÇAMENTO CONCLUÍDO: todas as 27 mídias já estão registradas como publicadas")
        return
    print(f"PRÓXIMO: {pending['id']} [{pending['channel']}] {pending['title']}")
    try:
        check_pacing(pending, ledger, utcnow())
    except Blocked as exc:
        if str(exc).startswith("Aguardando intervalo de segurança") and mode in ("auto", "dry-run"):
            print(f"AGUARDANDO INTERVALO ({mode}): {exc}. Nenhum post enviado")
            return
        raise
    if mode == "dry-run":
        print("DRY RUN OK: fila completa, mídias locais válidas e ordem correta; nenhum post enviado")
        return
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not token:
        raise Blocked("INSTAGRAM_ACCESS_TOKEN não configurado nos Secrets")
    publish_item(token, pending)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "manual", "auto"), default="dry-run")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    try:
        execute(args.mode, args.confirm)
    except (Blocked, ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"LANÇAMENTO BLOQUEADO: {exc}", file=sys.stderr)
        sys.exit(1)
