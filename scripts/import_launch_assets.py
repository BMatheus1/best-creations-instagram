"""Importa o pacote de lançamento aprovado (27 JPEGs) com verificações de integridade.

Uso: python scripts/import_launch_assets.py /caminho/zip
Não publica nada. A origem deve ser o ZIP criado para a Best Creations.
"""
from __future__ import annotations
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "content" / "launch_queue.json"
MEDIA = ROOT / "media" / "launch"
ACCOUNT = "bestcreations011"
REPO = "BMatheus1/best-creations-instagram"
ZIP_MANIFEST = "manifesto_publicacao.json"
TOTAL_STORIES = 7
TOTAL_FEED = 20
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 110 * 1024 * 1024


def _valid_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name) and not name.startswith("/")
        and "\\" not in name and ".." not in path.parts
        and len(path.parts) <= 3 and not name.endswith("/")
        and not re.search(r"[\x00-\x1f]", name)
    )


def _manifest_and_images(archive: zipfile.ZipFile):
    names = archive.namelist()
    if not names or len(names) > 70 or any(not _valid_name(n) for n in names):
        raise ValueError("ZIP contém caminhos inválidos ou arquivos inesperados")
    if len(set(names)) != len(names):
        raise ValueError("ZIP contém arquivos duplicados")
    if sum(info.file_size for info in archive.infolist()) > MAX_ARCHIVE_BYTES:
        raise ValueError("ZIP excede limite de tamanho descompactado")
    if ZIP_MANIFEST not in names:
        raise ValueError("Manifesto de lançamento ausente")
    manifest = json.loads(archive.read(ZIP_MANIFEST))
    if manifest.get("account") != ACCOUNT:
        raise ValueError("Pacote não corresponde ao @bestcreations011")
    items = manifest.get("items")
    if not isinstance(items, list) or len(items) != TOTAL_STORIES + TOTAL_FEED:
        raise ValueError("Pacote deve conter exatamente 7 Stories e 20 posts")
    return items


def assemble(archive_path: Path) -> list[tuple[dict, bytes]]:
    """Validação completa em memória; nenhum arquivo é escrito antes de concluir."""
    from PIL import Image, UnidentifiedImageError
    Image.MAX_IMAGE_PIXELS = 20_000_000
    output: list[tuple[dict, bytes]] = []
    with zipfile.ZipFile(archive_path) as archive:
        items = _manifest_and_images(archive)
        expected_files = {ZIP_MANIFEST}
        story_order = feed_order = 0
        for seq, item in enumerate(items, start=1):
            channel = item.get("channel")
            if channel == "story":
                story_order += 1
                if seq > TOTAL_STORIES or item.get("order") != story_order:
                    raise ValueError("A sequência de Stories está incorreta")
                media_type = "STORY"
                prefix = "01_STORIES_PUBLICAR_PRIMEIRO/"
            elif channel == "feed":
                feed_order += 1
                if seq <= TOTAL_STORIES or item.get("order") != feed_order:
                    raise ValueError("O feed deve começar após os sete Stories")
                media_type = "IMAGE"
                prefix = "02_FEED_PUBLICAR_DEPOIS/"
            else:
                raise ValueError("Canal desconhecido")
            name = item.get("file")
            if not isinstance(name, str) or not _valid_name(name) or not name.startswith(prefix) or not name.lower().endswith(".jpg"):
                raise ValueError("Caminho de mídia inválido")
            expected_files.add(name)
            file_info = archive.getinfo(name)
            if file_info.file_size > MAX_IMAGE_BYTES:
                raise ValueError(f"Imagem acima de 8 MB: {name}")
            source = archive.read(name)
            try:
                with Image.open(io.BytesIO(source)) as photo:
                    photo.verify()
                with Image.open(io.BytesIO(source)) as photo:
                    if photo.format != "JPEG":
                        raise ValueError(f"Imagem não é JPEG: {name}")
                    width, height = photo.size
            except (UnidentifiedImageError, OSError) as exc:
                raise ValueError(f"Imagem corrompida: {name}") from exc
            aspect = width / height
            if channel == "story" and not (0.55 <= aspect <= 0.58 and height >= 1000):
                raise ValueError(f"Story fora de 9:16: {name} ({width}x{height})")
            if channel == "feed" and not (0.8 <= aspect <= 1.91 and width >= 320):
                raise ValueError(f"Imagem de feed fora do formato suportado: {name}")
            caption = item.get("caption", "") if channel == "feed" else ""
            if not isinstance(caption, str) or len(caption) > 2200:
                raise ValueError("Legenda ausente ou longa demais")
            path = f"media/launch/{seq:02d}_{'story' if channel == 'story' else 'feed'}.jpg"
            prepared = {
                "id": f"bc-launch-{seq:03d}",
                "sequence": seq,
                "channel": channel,
                "media_type": media_type,
                "title": str(item.get("name", ""))[:100],
                "classification": str(item.get("kind", "institucional" if channel == "story" else "portfolio"))[:50],
                "image_path": path,
                "image_url": f"https://raw.githubusercontent.com/{REPO}/main/{path}",
                "sha256": hashlib.sha256(source).hexdigest(),
                "width": width,
                "height": height,
                "caption": caption,
                "status": "approved",
                "approved_by": "owner",
            }
            output.append((prepared, source))
        extra = set(archive.namelist()) - expected_files
        # ZIP pode incluir guias de texto e previews, mas nunca scripts executáveis.
        allowed_extra = {"sequencia_de_publicacao.md", "ordem_resumida.txt", "PREVIA_DO_PACOTE.jpg"}
        if extra - allowed_extra:
            raise ValueError(f"Arquivos inesperados no pacote: {sorted(extra - allowed_extra)}")
    return output


def install(archive_path: Path) -> int:
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    items = assemble(archive_path)
    if QUEUE.exists():
        previous = json.loads(QUEUE.read_text(encoding="utf-8"))
        if previous and previous != [row for row, _ in items]:
            raise RuntimeError("Fila existente difere do ZIP. Revisão manual necessária.")
    MEDIA.mkdir(parents=True, exist_ok=True)
    for item, source in items:
        path = ROOT / item["image_path"]
        if path.exists() and path.read_bytes() != source:
            raise RuntimeError(f"Imagem existente divergente: {path}")
    for item, source in items:
        path = ROOT / item["image_path"]
        path.write_bytes(source)
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text(json.dumps([row for row, _ in items], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"IMPORTAÇÃO PREPARADA: {TOTAL_STORIES} Stories e {TOTAL_FEED} fotos do feed; nenhuma publicação realizada")
    return len(items)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("Uso: python scripts/import_launch_assets.py <pacote.zip>")
        install(Path(sys.argv[1]))
    except (ValueError, RuntimeError, FileNotFoundError, zipfile.BadZipFile, KeyError) as exc:
        print(f"IMPORTAÇÃO BLOQUEADA: {exc}", file=sys.stderr)
        sys.exit(1)
