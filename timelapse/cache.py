"""Monta um cache reduzido da sequencia, SEM GIRO, para a previa ser instantanea.

A previa nao vai ao servidor a cada ajuste: o navegador recorta a imagem do cache
por CSS. Para isso o cache guarda o QUADRO INTEIRO, so que pequeno, e o manifesto
registra as dimensoes da fonte para a conta bater com a do ffmpeg no render final.
"""
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from . import ambiente
from .cli import EXIF_TO_GIRO, EXTENSIONS, exif_orientation, image_size, natural_key

LIMITE_PADRAO = 300
LADO_PADRAO = 1050  # maior lado do quadro guardado no cache
# Sobe quando o formato do cache muda. Manifesto com formato velho e ignorado,
# e o cache remonta sozinho, em vez de a previa mentir com quadros antigos.
FORMATO = 2
RAIZ_CACHE = ambiente.RAIZ / ".cache-previa"


def id_da_pasta(pasta: Path) -> str:
    return hashlib.sha1(str(pasta).encode()).hexdigest()[:16]


def pasta_cache(pasta: Path) -> Path:
    return RAIZ_CACHE / id_da_pasta(pasta)


def fotos_de(pasta: Path) -> list[Path]:
    arquivos = [
        p for p in pasta.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in EXTENSIONS
    ]
    return sorted(arquivos, key=natural_key)


def _amostra(total: int, limite: int) -> list[int]:
    """Indices distribuidos ao longo da sequencia, sempre incluindo as pontas."""
    if total <= limite:
        return list(range(total))
    return [round(i * (total - 1) / (limite - 1)) for i in range(limite)]


def manifesto(pasta: Path) -> dict | None:
    arquivo = pasta_cache(pasta) / "manifesto.json"
    if not arquivo.is_file():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if dados.get("formato") == FORMATO else None


def construir(pasta: Path, limite: int = LIMITE_PADRAO, lado: int = LADO_PADRAO) -> dict:
    """Gera o cache numa passada so do ffmpeg. Devolve o manifesto.

    O quadro e guardado SEM GIRO. A rotacao acontece no navegador, para que
    trocar --girar reflita na previa na hora, sem remontar o cache, e para que
    previa e render nunca divirjam.
    """
    fotos = fotos_de(pasta)
    if len(fotos) < 2:
        raise ValueError(f"A pasta precisa de pelo menos duas fotos: {pasta}")

    orientacao = exif_orientation(fotos[0])
    giro_exif = EXIF_TO_GIRO.get(orientacao, "nao") if orientacao else "nao"
    largura_bruta, altura_bruta = image_size(fotos[0])

    indices = _amostra(len(fotos), limite)
    destino = pasta_cache(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    for antigo in destino.glob("q_*.jpg"):
        antigo.unlink()

    # o maior lado vai para `lado`, seja a foto retrato ou paisagem
    filtros = [
        f"scale=w='if(gte(iw,ih),{lado},-2)':h='if(gte(iw,ih),-2,{lado})'"
    ]

    # O diretorio temporario fica fora da pasta de destino: em volume montado
    # a limpeza do tempfile falha.
    with tempfile.TemporaryDirectory(prefix="timelapse-cache-") as temporario:
        trabalho = Path(temporario)
        extensao = EXTENSIONS[fotos[0].suffix.lower()]
        for posicao, indice in enumerate(indices):
            (trabalho / f"{posicao:06d}.{extensao}").symlink_to(fotos[indice])

        subprocess.run(
            [
                str(ambiente.achar_ffmpeg()), "-hide_banner", "-loglevel", "error", "-nostdin",
                "-noautorotate", "-f", "image2", "-framerate", "1", "-start_number", "0",
                "-i", str(trabalho / f"%06d.{extensao}"),
                "-vf", ",".join(filtros), "-q:v", "5",
                # sem isto o ffmpeg numera a saida a partir de 1
                "-start_number", "0",
                str(destino / "q_%06d.jpg"),
            ],
            check=True, capture_output=True,
        )

    dados = {
        "id": id_da_pasta(pasta),
        "pasta": str(pasta),
        "total_fotos": len(fotos),
        "quadros": len(indices),
        "indices": indices,
        "largura_bruta": largura_bruta,
        "altura_bruta": altura_bruta,
        "giro_exif": giro_exif,
        "orientacao_exif": orientacao,
        "lado_cache": lado,
        "formato": FORMATO,
        # Muda a cada remontagem. Vai na URL do quadro para o navegador nao
        # servir bytes do cache antigo numa URL que nao mudou.
        "montado": int(time.time()),
        "primeira": fotos[0].name,
        "ultima": fotos[-1].name,
    }
    (destino / "manifesto.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return dados


def quadros_prontos(pasta: Path) -> int:
    """Quantos quadros ja foram escritos. Serve para mostrar progresso real."""
    destino = pasta_cache(pasta)
    if not destino.is_dir():
        return 0
    return sum(1 for _ in destino.glob("q_*.jpg"))


def caminho_quadro(pasta: Path, posicao: int) -> Path:
    return pasta_cache(pasta) / f"q_{posicao:06d}.jpg"


def apagar(pasta: Path) -> None:
    destino = pasta_cache(pasta)
    for arquivo in destino.glob("*"):
        arquivo.unlink()
    if destino.is_dir():
        os.rmdir(destino)
