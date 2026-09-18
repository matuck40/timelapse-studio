"""Le a estrutura do acervo: uma pasta por projeto, com fotos-*/ e render/ dentro."""
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

FOTO = (".jpg", ".jpeg", ".png")
VIDEO = (".mp4", ".mov")
CLIPE_CAMERA = re.compile(r"^C\d{4}\.(MP4|MOV)$", re.I)


@dataclass
class Sequencia:
    """Uma pasta de fotos que vira um video."""

    id: str
    nome: str
    caminho: str
    fotos: int
    segundos: float
    primeira: str
    ultima: str
    buracos: int | None
    renders: list[str] = field(default_factory=list)


@dataclass
class Projeto:
    id: str
    nome: str
    caminho: str
    sequencias: list[Sequencia] = field(default_factory=list)


def _numero(nome: str) -> int | None:
    achados = re.findall(r"(\d+)", nome)
    return int(achados[-1]) if achados else None


def _analisar(pasta: Path, renders: list[str]) -> Sequencia | None:
    try:
        arquivos = sorted(
            f for f in os.listdir(pasta)
            if not f.startswith(".") and f.lower().endswith(FOTO)
        )
    except OSError:
        return None
    if len(arquivos) < 20:
        return None

    numeros = [_numero(f) for f in arquivos]
    buracos = None
    if all(n is not None for n in numeros):
        ordenados = sorted(numeros)
        if ordenados == numeros:
            buracos = (numeros[-1] - numeros[0] + 1) - len(numeros)

    return Sequencia(
        id=str(pasta),
        nome=pasta.name,
        caminho=str(pasta),
        fotos=len(arquivos),
        segundos=round(len(arquivos) / 30, 1),
        primeira=arquivos[0],
        ultima=arquivos[-1],
        buracos=buracos,
        renders=renders,
    )


def listar(base: Path) -> list[dict]:
    """Varre a base e devolve os projetos com suas sequencias de fotos."""
    projetos: list[Projeto] = []
    if not base.is_dir():
        return []

    for dir_projeto in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")):
        pasta_render = dir_projeto / "render"
        renders = []
        if pasta_render.is_dir():
            renders = sorted(
                f for f in os.listdir(pasta_render)
                if f.lower().endswith(VIDEO) and not CLIPE_CAMERA.match(f)
            )

        projeto = Projeto(id=dir_projeto.name, nome=dir_projeto.name, caminho=str(dir_projeto))

        # fotos/ e fotos-<variante>/ sao as sequencias; o resto (sony/, iphone/) nao e.
        for sub in sorted(dir_projeto.iterdir()):
            if not sub.is_dir() or not sub.name.startswith("fotos"):
                continue
            seq = _analisar(sub, renders)
            if seq:
                projeto.sequencias.append(seq)

        # Projeto com as fotos soltas na raiz, sem subpasta.
        if not projeto.sequencias:
            seq = _analisar(dir_projeto, renders)
            if seq:
                projeto.sequencias.append(seq)

        if projeto.sequencias:
            projetos.append(projeto)

    return [asdict(p) for p in projetos]
