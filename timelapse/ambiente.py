"""Localiza o ffmpeg e confere o ambiente. Usado pelo painel e pelo `make setup`."""
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

CANDIDATOS_FFMPEG = [
    RAIZ / "bin" / "ffmpeg",
    Path("/opt/homebrew/bin/ffmpeg"),
    Path("/usr/local/bin/ffmpeg"),
]


def achar_ffmpeg() -> Path:
    """Devolve o primeiro ffmpeg executavel. O binario local vem primeiro."""
    for caminho in CANDIDATOS_FFMPEG:
        if caminho.is_file() and _executavel(caminho):
            return caminho
    do_path = shutil.which("ffmpeg")
    if do_path and _executavel(Path(do_path)):
        return Path(do_path)
    raise RuntimeError(
        "FFmpeg nao encontrado. Rode `make setup` para ver as opcoes, "
        "ou coloque o binario em bin/ffmpeg."
    )


def _executavel(caminho: Path) -> bool:
    """Confere que o binario roda nesta arquitetura, nao so que existe."""
    try:
        subprocess.run(
            [str(caminho), "-version"], capture_output=True, timeout=10, check=True
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def diagnostico() -> int:
    print("timelapse-studio — ambiente\n")
    print(f"Python   {sys.version.split()[0]}")
    print(f"Raiz     {RAIZ}")

    achou = None
    for caminho in CANDIDATOS_FFMPEG:
        if not caminho.is_file():
            estado = "nao existe"
        elif _executavel(caminho):
            estado = "OK"
            achou = achou or caminho
        else:
            estado = "existe mas nao roda nesta arquitetura"
        print(f"  {estado:42} {caminho}")

    do_path = shutil.which("ffmpeg")
    if do_path:
        ok = _executavel(Path(do_path))
        print(f"  {'OK' if ok else 'nao roda':42} {do_path}  (PATH)")
        achou = achou or (Path(do_path) if ok else None)

    if achou:
        print(f"\nVai usar: {achou}")
        return 0
    print(
        "\nNenhum ffmpeg utilizavel.\n"
        "  brew install ffmpeg\n"
        "  ou copie um binario compativel para bin/ffmpeg"
    )
    return 1


if __name__ == "__main__":
    sys.exit(diagnostico())
