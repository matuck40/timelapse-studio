"""A conta do recorte no navegador precisa bater com a do ffmpeg.

Estes testes fixam o comportamento da CLI que o painel replica em JS:
se `video_filter` mudar, o app.js precisa mudar junto.
"""
from types import SimpleNamespace

import pytest

from timelapse.cli import EXIF_TO_GIRO, ROTATIONS, video_filter


def args(**extra):
    base = dict(zoom=1.0, pos_x=0.0, pos_y=0.0, resolucao="1080x1920",
                enquadramento="preencher", girar="nao")
    base.update(extra)
    return SimpleNamespace(**base)


@pytest.fixture
def foto(tmp_path):
    """Um PNG minimo de 4000x6000: video_filter so le as dimensoes."""
    import struct
    import zlib

    largura, altura = 4000, 6000
    cabecalho = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)

    def bloco(tipo, dados):
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados)))

    caminho = tmp_path / "a.png"
    caminho.write_bytes(
        b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", cabecalho) + bloco(b"IEND", b"")
    )
    return caminho


def test_sem_zoom_preencher_corta_a_largura(foto):
    filtro = video_filter(args(), foto)
    assert "force_original_aspect_ratio=increase" in filtro
    assert "crop=1080:1920" in filtro


def test_ajustar_usa_barras(foto):
    filtro = video_filter(args(enquadramento="ajustar"), foto)
    assert "force_original_aspect_ratio=decrease" in filtro
    assert "pad=1080:1920" in filtro


def test_zoom_recorta_antes_de_escalar(foto):
    filtro = video_filter(args(zoom=2.0), foto)
    assert filtro.index("crop=w=") < filtro.index("scale=")


def test_giro_entra_primeiro_e_troca_as_dimensoes(foto):
    filtro = video_filter(args(girar="270", zoom=1.0, resolucao="original"), foto)
    assert filtro.startswith(ROTATIONS["270"])
    # depois do giro a fonte e 6000x4000, e o pad reflete isso
    assert "pad=6000:4000" in filtro


def test_mapa_exif_cobre_as_orientacoes_que_a_camera_usa():
    assert EXIF_TO_GIRO[8] == "270"
    assert EXIF_TO_GIRO[6] == "90"
