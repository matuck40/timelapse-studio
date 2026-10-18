import cv2
import numpy as np
import pytest
from sinteticos import sequencia

from timelapse import cache
from timelapse import correcao as c

ALINHAR = [0.1, 0.1, 0.55, 0.55]


@pytest.fixture(autouse=True)
def cache_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAIZ_CACHE", tmp_path / "cache")


def test_analisar_trata_salto_mao_e_luz(tmp_path):
    fotos = sequencia(tmp_path)
    analise = c.analisar(
        fotos,
        "IMG_0000.png",
        regiao_cor=[0.74, 0.69, 0.2, 0.2],
        regiao_alinhamento=ALINHAR,
        lado=900,
    )
    q = analise["quadros"]
    assert q["IMG_0002.png"]["falhou_alinhamento"] is True
    assert q["IMG_0002.png"]["cor_substituida"] is True
    # a do meio herda o deslize interpolado entre (3,-2) e (40,25)
    assert q["IMG_0002.png"]["tx"] == pytest.approx(21.5, abs=1.0)
    assert q["IMG_0003.png"]["tx"] == pytest.approx(40, abs=0.5)
    assert q["IMG_0003.png"]["ty"] == pytest.approx(25, abs=0.5)
    assert analise["zoom_borda"] > 1.0
    # a 5a foto foi escurecida para 0.8: o ganho volta ~1.25 (suavizado com vizinhos)
    assert 1.1 < q["IMG_0004.png"]["ganho"][1] < 1.3


def test_aplicar_em_tamanho_reduzido(tmp_path):
    fotos = sequencia(tmp_path)
    analise = c.analisar(fotos, "IMG_0000.png", regiao_alinhamento=ALINHAR, lado=900)
    pequena = c.carregar(fotos[3], 450, 300)
    quadros = analise["quadros"]
    saida = c.aplicar(pequena, quadros["IMG_0003.png"], analise, cor=False, estabilizar=True)
    ref = c.carregar(fotos[0], 450, 300)
    saida_ref = c.aplicar(ref, quadros["IMG_0000.png"], analise, cor=False, estabilizar=True)
    miolo = (slice(80, 220), slice(80, 300))
    # a foto 3 tambem esta mais escura: compara o desenho, nao o brilho
    a, b = saida[miolo][..., 1].ravel(), saida_ref[miolo][..., 1].ravel()
    assert np.corrcoef(a, b)[0, 1] > 0.97
    # sem alinhar, o desenho nao bate
    crua = cv2.resize(pequena, (450, 300))[miolo][..., 1].ravel()
    assert np.corrcoef(crua, b)[0, 1] < 0.5


def test_referencia_fora_da_pasta_e_recusada(tmp_path):
    fotos = sequencia(tmp_path)
    with pytest.raises(ValueError, match="Referência"):
        c.analisar(fotos, "NAO_EXISTE.png", regiao_alinhamento=ALINHAR)


def test_cancelar_para_a_analise(tmp_path):
    fotos = sequencia(tmp_path)
    with pytest.raises(c.Cancelado):
        c.analisar(
            fotos, "IMG_0000.png", regiao_alinhamento=ALINHAR, progresso=lambda feitos, total: False
        )


def test_foto_nova_na_pasta_refaz_a_analise(tmp_path):
    fotos = sequencia(tmp_path)
    primeira = c.analise_da_pasta(tmp_path, "IMG_0000.png", regiao_alinhamento=ALINHAR)
    # a captura continua: chega uma foto depois da analise
    (tmp_path / "IMG_0005.png").write_bytes(fotos[4].read_bytes())
    segunda = c.analise_da_pasta(tmp_path, "IMG_0000.png", regiao_alinhamento=ALINHAR)
    assert "IMG_0005.png" not in primeira["quadros"]
    assert "IMG_0005.png" in segunda["quadros"]


def test_analise_salva_e_reaproveitada(tmp_path, monkeypatch):
    sequencia(tmp_path)
    c.analise_da_pasta(tmp_path, "IMG_0000.png", regiao_alinhamento=ALINHAR)
    monkeypatch.setattr(c, "analisar", lambda *a, **k: pytest.fail("recalculou"))
    c.analise_da_pasta(tmp_path, "IMG_0000.png", regiao_alinhamento=ALINHAR)


def test_em_ordem_preserva_a_ordem():
    assert list(c.em_ordem(lambda x: x * 2, range(30), adiante=3)) == [x * 2 for x in range(30)]
