"""Agendador: publica no máximo uma foto aprovada por execução."""
import os
import sys
from datetime import datetime, timezone

from instagram_publish import publish_one, read_ledger
from social_manager import read_queue


def main():
    if os.environ.get("AUTO_PUBLISH_ENABLED") != "true":
        print("Agendamento pausado.")
        return
    now = datetime.now(timezone.utc)
    due = [
        item for item in read_queue()
        if item["status"] == "approved"
        and item["type"] == "IMAGE"
        and datetime.fromisoformat(item["scheduled_at"].replace("Z", "+00:00")) <= now
    ]
    if not due:
        print("Nenhuma foto aprovada vencida.")
        return
    ledger = read_ledger()
    due = [item for item in due if item["id"] not in ledger]
    if not due:
        print("Todos os conteúdos vencidos já possuem tentativas registradas.")
        return
    due.sort(key=lambda item: item["scheduled_at"])
    # Apenas 1 por execução; lock persistente previne duplicação.
    publish_one(due[0]["id"], os.environ["INSTAGRAM_ACCESS_TOKEN"], "schedule", "")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"Agendamento interrompido: {exc}", file=sys.stderr)
        sys.exit(1)
