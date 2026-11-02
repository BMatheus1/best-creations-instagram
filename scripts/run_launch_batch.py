"""Executa a fila de lançamento em uma única execução, com 5 min entre posts.

Apenas ações já aprovadas em content/launch_queue.json. Preserva os bloqueios de
duplicidade do publicador e para imediatamente em erro ou estado ambíguo.
Usado no workflow automático de lançamento para não depender de cada tick do cron.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from typing import Optional

import publish_launch as publication

MAX_ITEMS_PER_RUN = 27
MAX_WAIT_STEP_SECONDS = 30


def seconds_until_allowed(item: dict, ledger: dict, now: datetime) -> float:
    """Calcula a espera pelo mesmo intervalo aplicado por check_pacing."""
    latest: Optional[tuple[datetime, str]] = None
    for entry in ledger.values():
        if not isinstance(entry, dict) or entry.get("status") != "published":
            continue
        try:
            published = datetime.fromisoformat(entry["published_at"])
            if published.tzinfo is None:
                raise ValueError("naive")
        except (KeyError, ValueError, TypeError):
            raise publication.Blocked("Data inválida no histórico de publicações") from None
        if latest is None or published > latest[0]:
            latest = (published, entry.get("channel"))
    if latest is None:
        return 0.0
    duration = (
        publication.STORY_GAP if item["channel"] == "story"
        else publication.FIRST_FEED_GAP if latest[1] == "story"
        else publication.FEED_GAP
    )
    return max(0.0, (latest[0] + duration - now).total_seconds())


def execute():
    if os.environ.get("INSTAGRAM_LAUNCH_ENABLE_AUTO") != "true":
        raise publication.Blocked("Publicação automática não autorizada")
    if os.environ.get("INSTAGRAM_LAUNCH_VARIABLE_ENABLED") != "true":
        raise publication.Blocked("Variável de ativação do lançamento não habilitada")
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not token:
        raise publication.Blocked("Secret Instagram ausente")

    published_count = 0
    last_announced = None
    while published_count < MAX_ITEMS_PER_RUN:
        items = publication.read_queue()
        ledger = publication.read_ledger()
        pending = publication.next_item(items, ledger)
        if pending is None:
            print(f"LANÇAMENTO CONCLUÍDO: {len(items)} publicações registradas; {published_count} nesta execução")
            return
        remaining = seconds_until_allowed(pending, ledger, publication.utcnow())
        if remaining > 0:
            if pending["id"] != last_announced:
                print(
                    f"AGUARDANDO: próximo {pending['id']} [{pending['channel']}], "
                    f"intervalo mínimo de 5 minutos; {int(remaining + 0.999)}s restantes",
                    flush=True,
                )
                last_announced = pending["id"]
            time.sleep(min(remaining + 0.2, MAX_WAIT_STEP_SECONDS))
            continue
        publication.check_pacing(pending, ledger, publication.utcnow())
        print(f"PUBLICAÇÃO EM LOTE: {pending['id']} [{pending['channel']}] {pending['title']}", flush=True)
        publication.publish_item(token, pending)
        published_count += 1
        last_announced = None
    print("LIMITE DE ITENS DA EXECUÇÃO ALCANÇADO: nova execução necessária", flush=True)


if __name__ == "__main__":
    try:
        execute()
    except (publication.Blocked, ValueError, KeyError, OSError, RuntimeError) as exc:
        print(f"LOTE INTERROMPIDO COM SEGURANÇA: {exc}", file=sys.stderr)
        sys.exit(1)
