import math

import cv2
import numpy as np
import pytest
from sinteticos import textura

from timelapse import correcao as c


def test_alinhar_recupera_deslize_e_giro():
    ref = textura()
    a = c.euclidiana(math.radians(1.5), 12.0, -7.0)
    quadro = cv2.warpAffine(ref, a, (600, 400))
    achada = c.alinhar(ref, quadro, c.mascara([0.2, 0.2, 0.6, 0.6], 600, 400))
    assert achada is not None
    assert math.degrees(math.atan2(achada[1, 0], achada[0, 0])) == pytest.approx(1.5, abs=0.05)
    assert achada[0, 2] == pytest.approx(12.0, abs=0.3)
    assert achada[1, 2] == pytest.approx(-7.0, abs=0.3)


def test_alinhar_aguenta_salto_grande():
    ref = textura()
    a = c.euclidiana(math.radians(-3), 60.0, 35.0)
    quadro = cv2.warpAffine(ref, a, (600, 400))
    achada = c.alinhar(ref, quadro, c.mascara([0.3, 0.3, 0.4, 0.4], 600, 400))
    assert achada is not None
    assert achada[0, 2] == pytest.approx(60.0, abs=0.5)
    assert achada[1, 2] == pytest.approx(35.0, abs=0.5)


def test_alinhar_falha_com_mao_na_frente():
    ref = textura()
    quadro = ref.copy()
    quadro[60:340, 90:510] = 10
    assert c.alinhar(ref, quadro, c.mascara([0.2, 0.2, 0.6, 0.6], 600, 400)) is None


def test_alinhar_aguenta_mudanca_de_luz():
    # a luz muda junto com o esbarrao: alinhamento vem antes da cor e nao pode depender dela
    ref = textura()
    a = c.euclidiana(math.radians(0.5), 6.0, 4.0)
    quadro = cv2.warpAffine(ref, a, (600, 400)).astype(np.float64) * 0.55 + 10
    ruido = np.random.default_rng(9).normal(0, 4, quadro.shape)
    quadro = np.clip(quadro + ruido, 0, 255).astype(np.uint8)
    achada = c.alinhar(ref, quadro, c.mascara([0.2, 0.2, 0.6, 0.6], 600, 400))
    assert achada is not None
    assert achada[0, 2] == pytest.approx(6.0, abs=0.5)


def test_zoom_borda_esconde_o_maior_deslize():
    a = c.euclidiana(0, 30.0, 0)  # 30 px para a direita num quadro de 600
    z = c.zoom_borda([c.euclidiana(0, 0, 0), a], 600, 400)
    # metade da largura visivel (300/z) + 30 precisa caber em 300
    assert z == pytest.approx(300 / 270, rel=1e-4)


def test_sem_movimento_nao_tem_zoom():
    assert c.zoom_borda([c.euclidiana(0, 0, 0)] * 3, 600, 400) == 1.0


def test_matriz_de_saida_desfaz_o_deslize():
    ref = textura()
    a = c.euclidiana(math.radians(1.0), 8.0, -5.0)
    quadro = cv2.warpAffine(ref, a, (600, 400))
    m = c.matriz_de_saida(math.radians(1.0), 8.0, -5.0, 1.0, 600, 400)
    alinhado = cv2.warpAffine(quadro, m, (600, 400), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    miolo = (slice(100, 300), slice(150, 450))
    assert np.abs(alinhado[miolo].astype(int) - ref[miolo].astype(int)).mean() < 3


def test_aplicar_desligado_devolve_a_mesma_imagem():
    rgb = cv2.cvtColor(textura(), cv2.COLOR_GRAY2RGB)
    quadro = {"theta": 0.1, "tx": 50.0, "ty": 0.0, "ganho": [2.0, 2.0, 2.0]}
    analise = {"largura_bruta": 600, "zoom_borda": 1.3, "alinhamento": True, "cor": True}
    assert c.aplicar(rgb, quadro, analise, cor=False, estabilizar=False) is rgb


def test_carregar_reduz_sem_girar(tmp_path):
    from PIL import Image
    caminho = tmp_path / "a.jpg"
    Image.fromarray(np.zeros((400, 600, 3), dtype=np.uint8)).save(caminho)
    assert c.carregar(caminho, 300, 200).shape == (200, 300, 3)
    assert c.tamanho_reduzido(6000, 4000, 1500) == (1500, 1000)
