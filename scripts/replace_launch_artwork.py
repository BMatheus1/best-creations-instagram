"""Importa somente imagens de posts ainda não publicados de um ZIP de substituição.

Pacote: Best_Creations_Feed_07_Artes_Neutras.zip
Nunca usa a Meta, não publica e não altera a arte de posts já publicados.
Para publicações já realizadas, a troca deve ser feita no próprio Instagram,
excluindo o post antigo e criando outro (operação não realizada aqui).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "content" / "launch_queue.json"
LEDGER_PATH = ROOT / "state" / "launch_publications.json"
ACCOUNT = "bestcreations011"
EXPECTED_IDS = {
    "bc-launch-020", "bc-launch-022", "bc-launch-023", "bc-launch-024",
    "bc-launch-025", "bc-launch-026", "bc-launch-027",
}
MAX_ARCHIVE_BYTES = 45 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class ImportErrorSafe(RuntimeError):
    pass


def _verify_filename(filename: str) -> bool:
    parts = PurePosixPath(filename).parts
    return bool(filename) and not filename.startswith("/") and "\\" not in filename and ".." not in parts and len(parts) <= 3


def prepare(archive_path: Path, root: Path = ROOT):
    """Valida tudo antes de tocar em qualquer arquivo da fila."""
    if not archive_path.is_file():
        raise ImportErrorSafe("ZIP não encontrado")
    queue_path = root / "content" / "launch_queue.json"
    ledger_path = root / "state" / "launch_publications.json"
    if not queue_path.is_file() or not ledger_path.is_file():
        raise ImportErrorSafe("Fila ou histórico indisponível")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not isinstance(queue, list) or len(queue) != 27 or not isinstance(ledger, dict):
        raise ImportErrorSafe("Fila de 27 itens ou histórico inválido")
    lookup = {item["id"]: item for item in queue}
    if len(lookup) != 27:
        raise ImportErrorSafe("Identificadores duplicados na fila")

    pending_updates = []
    skipped = []

    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) > 40 or len(set(names)) != len(names) or any(not _verify_filename(n) for n in names):
            raise ImportErrorSafe("ZIP contém caminhos não autorizados ou duplicados")
        if sum(info.file_size for info in archive.infolist()) > MAX_ARCHIVE_BYTES:
            raise ImportErrorSafe("ZIP excede o limite descompactado")
        if "manifesto_substituicao.json" not in names:
            raise ImportErrorSafe("Manifesto de substituição ausente")
        manifest = json.loads(archive.read("manifesto_substituicao.json"))
        if manifest.get("account") != ACCOUNT or manifest.get("type") != "best_creations_feed_replacement":
            raise ImportErrorSafe("Pacote de outra conta ou tipo incorreto")
        items = manifest.get("items")
        if not isinstance(items, list) or len(items) != 7 or {i.get("id") for i in items} != EXPECTED_IDS:
            raise ImportErrorSafe("Pacote deve conter exatamente as sete artes previamente aprovadas")
        for item in items:
            identifier = item["id"]
            current = lookup.get(identifier)
            if not current or current.get("channel") != "feed":
                raise ImportErrorSafe("ID não corresponde a um post de feed esperado")
            if item.get("sequence") != current.get("sequence") or item.get("path") != current.get("image_path"):
                raise ImportErrorSafe("Sequência/caminho não corresponde à fila atual")
            path = item["path"]
            if not re.fullmatch(r"media/launch/(20|22|23|24|25|26|27)_feed\.jpg", path):
                raise ImportErrorSafe("Caminho de mídia não autorizado")
            if path not in names:
                raise ImportErrorSafe(f"Imagem ausente do ZIP: {path}")
            file_info = archive.getinfo(path)
            if not (0 < file_info.file_size <= MAX_IMAGE_BYTES):
                raise ImportErrorSafe("Imagem vazia ou maior que 8 MB")
            blob = archive.read(path)
            digest = hashlib.sha256(blob).hexdigest()
            if digest != item.get("sha256"):
                raise ImportErrorSafe(f"Checksum incorreto: {path}")
            try:
                with Image.open(io.BytesIO(blob)) as im:
                    im.verify()
                with Image.open(io.BytesIO(blob)) as im:
                    if im.format != "JPEG" or im.width < 320 or not (0.8 <= im.width / im.height <= 1.91):
                        raise ImportErrorSafe(f"Formato fora do padrão de feed: {path}")
                    size = (im.width, im.height)
            except (UnidentifiedImageError, OSError) as exc:
                raise ImportErrorSafe(f"JPEG corrompido: {path}") from exc

            entry = ledger.get(identifier)
            if entry is not None:
                if not isinstance(entry, dict) or entry.get("status") != "published":
                    raise ImportErrorSafe(f"Publicação {identifier} tem tentativa pendente: não substituir")
                skipped.append(identifier)
                continue

            if current.get("status") != "approved":
                raise ImportErrorSafe(f"Post {identifier} não está aprovado")
            if current.get("sha256") == digest:
                skipped.append(identifier)
                continue

            replacement = dict(current)
            replacement.update(sha256=digest, width=size[0], height=size[1])
            pending_updates.append((identifier, root / path, blob, replacement))

    return queue, pending_updates, skipped


def apply(archive_path: Path, *, dry_run: bool = True, root: Path = ROOT):
    queue, updates, skipped = prepare(archive_path, root=root)
    print("ALREADY PUBLISHED / NO CHANGES:", ", ".join(skipped) or "nenhum", flush=True)
    print("PENDING TO UPDATE:", ", ".join(i for i, *_ in updates) or "nenhum", flush=True)
    if dry_run:
        print("SIMULAÇÃO OK: sem alterações no GitHub e sem publicações no Instagram", flush=True)
        return len(updates)
    mapping = {identifier: replacement for identifier, _, _, replacement in updates}
    for _, path, image, _ in updates:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image)
    if updates:
        result = [mapping.get(x["id"], x) for x in queue]
        queue_path = root / "content" / "launch_queue.json"
        queue_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ARTES ATUALIZADAS LOCALMENTE:", len(updates), "— nenhuma publicada", flush=True)
    return len(updates)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    try:
        apply(arguments.archive, dry_run=not arguments.apply)
    except (ImportErrorSafe, ValueError, KeyError, OSError, zipfile.BadZipFile, TypeError) as exc:
        print(f"SUBSTITUIÇÃO BLOQUEADA: {exc}", file=sys.stderr)
        sys.exit(1)
