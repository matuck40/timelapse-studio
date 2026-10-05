import cv2
import numpy as np
import pytest

from timelapse import correcao as c


def test_ganho_recupera_balanco_conhecido():
    ref = np.full((3,), 0.4)
    ganho = np.array([0.5, 0.6, 0.8])
    medidas = np.tile(ref * ganho, (9, 1))
    ganhos, _ = c.ganhos_de_cor(ref, medidas)
    assert ganhos[4] == pytest.approx(1 / ganho, rel=1e-6)


def test_ganho_acima_do_teto_fica_em_2x():
    ref = np.full((3,), 0.4)
    medidas = np.tile(ref * 0.3, (9, 1))
    ganhos, _ = c.ganhos_de_cor(ref, medidas)
    assert ganhos[4] == pytest.approx([2.0, 2.0, 2.0])


def test_teto_preserva_a_proporcao_entre_canais():
    travado = c.limitar_ganho(np.array([[4.0, 2.0, 1.0]]))[0]
    assert travado @ c.LUMA == pytest.approx(2.0)
    assert travado[0] / travado[1] == pytest.approx(2.0)


def test_quadro_fora_da_curva_usa_vizinhos():
    ref = np.full((3,), 0.4)
    medidas = np.tile(ref, (9, 1))
    medidas[4] = [0.05, 0.05, 0.05]  # mao na frente
    ganhos, substituidos = c.ganhos_de_cor(ref, medidas)
    assert substituidos.tolist() == [False] * 4 + [True] + [False] * 4
    assert ganhos[4] == pytest.approx([1.0, 1.0, 1.0])


def test_medicao_zerada_conta_como_invalida():
    ref = np.full((3,), 0.4)
    medidas = np.tile(ref, (5, 1))
    medidas[0] = 0  # quadro que nao alinhou chega zerado
    ganhos, substituidos = c.ganhos_de_cor(ref, medidas)
    assert substituidos[0]
    assert ganhos[0] == pytest.approx([1.0, 1.0, 1.0])


def test_lut_aplica_ganho_em_luz_linear():
    rgb = np.full((2, 2, 3), 100, dtype=np.uint8)
    saida = cv2.LUT(rgb, c.tabela_de_ganho([2.0, 1.0, 0.5]))
    esperado = c.linear_para_srgb(c.srgb_para_linear(100) * np.array([2.0, 1.0, 0.5]))
    assert saida[0, 0].tolist() == np.round(esperado).astype(int).tolist()


def test_medir_cor_so_dentro_da_regiao():
    rgb = np.zeros((100, 100, 3), dtype=np.uint8)
    rgb[:50, :50] = 255
    assert c.medir_cor(rgb, [0, 0, 0.5, 0.5]) == pytest.approx([1.0, 1.0, 1.0])
    assert c.medir_cor(rgb, [0.5, 0.5, 0.5, 0.5]) == pytest.approx([0.0, 0.0, 0.0])
