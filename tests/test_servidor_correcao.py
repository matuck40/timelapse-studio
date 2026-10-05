import json
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import Request, urlopen

import cv2
import numpy as np
import pytest

from timelapse import cache, cli, correcao, servidor


@pytest.fixture
def painel(tmp_path, monkeypatch):
    try:
        cli.find_ffmpeg()
    except ValueError:
        pytest.skip("ffmpeg indisponivel")
    monkeypatch.setattr(cache, "RAIZ_CACHE", tmp_path / "cache")
    pasta = tmp_path / "fotos"
    pasta.mkdir()
    gerador = np.random.default_rng(5)
    base = cv2.resize(gerador.integers(0, 256, (40, 60, 3), dtype=np.uint8), (600, 400),
                      interpolation=cv2.INTER_CUBIC)
    for i, dx in enumerate([0, 3, 6, 6, 5]):
        quadro = cv2.warpAffine(base, np.float64([[1, 0, dx], [0, 1, 0]]), (600, 400),
                                borderMode=cv2.BORDER_REFLECT)
        if i == 2:
            quadro[:] = 5  # mao na frente: tudo escuro
        cv2.imwrite(str(pasta / f"IMG_{i}.jpg"), quadro)
    cache.construir(pasta, limite=300, lado=300)
    http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Painel)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{http.server_address[1]}", pasta
    http.shutdown()


def chamar(url, corpo=None):
    dados = None if corpo is None else json.dumps(corpo).encode()
    pedido = Request(url, data=dados, headers={"Content-Type": "application/json"})
    with urlopen(pedido) as resposta:
        return json.loads(resposta.read())


def test_correcao_gera_previa_e_marca_falhas(painel):
    base, pasta = painel
    chamar(base + "/api/correcao", {
        "pasta": str(pasta), "referencia": "IMG_0.jpg",
        "regiao_cor": [0.1, 0.1, 0.3, 0.3], "regiao_alinhamento": [0.2, 0.2, 0.6, 0.6]})
    for _ in range(100):
        resposta = chamar(base + f"/api/correcao?pasta={quote(str(pasta))}")
        if resposta["info"] or (resposta["estado"] or {}).get("fase") == "erro":
            break
        time.sleep(0.1)
    assert resposta["estado"] is None, resposta
    assert resposta["info"]["falhas"] == [2]
    corrigidos = sorted((cache.pasta_cache(pasta) / "corrigido").glob("q_*.jpg"))
    assert len(corrigidos) == 5
    with urlopen(base + f"/q/{cache.id_da_pasta(pasta)}/corrigido/q_000000.jpg") as quadro:
        assert quadro.headers["Content-Type"] == "image/jpeg"


def test_sem_regiao_apaga_a_previa_corrigida(painel):
    base, pasta = painel
    destino = cache.pasta_cache(pasta) / "corrigido"
    destino.mkdir()
    (destino / "q_000000.jpg").write_bytes(b"x")
    resposta = chamar(base + "/api/correcao", {"pasta": str(pasta), "referencia": "IMG_0.jpg"})
    assert resposta == {"estado": None}
    assert not destino.exists()


def test_salvar_correcao_preserva_o_enquadramento(painel):
    base, pasta = painel
    (pasta / "enquadramento.json").write_text(json.dumps({"zoom": 1.4}))
    chamar(base + "/api/enquadramento/correcao", {
        "pasta": str(pasta), "correcao": {"referencia": "IMG_0.jpg", "intrusa": 1}})
    salvo = json.loads((pasta / "enquadramento.json").read_text())
    assert salvo == {"zoom": 1.4, "referencia": "IMG_0.jpg"}


def test_lista_nomes_das_fotos(painel):
    base, pasta = painel
    nomes = chamar(base + f"/api/fotos?pasta={quote(str(pasta))}")["nomes"]
    assert nomes == [f"IMG_{i}.jpg" for i in range(5)]


def test_previa_corrigida_de_cache_antigo_e_ignorada(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAIZ_CACHE", tmp_path / "cache")
    destino = cache.pasta_cache(tmp_path)
    (destino / "corrigido").mkdir(parents=True)
    (destino / "manifesto.json").write_text(json.dumps({"formato": cache.FORMATO, "montado": 2}))
    (destino / "corrigido" / "info.json").write_text(json.dumps({"montado": 1}))
    assert correcao.info_previa(tmp_path) is None


def test_foto_nova_durante_a_analise_nao_quebra_a_previa(painel):
    _, pasta = painel
    analise = correcao.analise_da_pasta(pasta, "IMG_0.jpg",
                                        regiao_alinhamento=[0.2, 0.2, 0.6, 0.6])
    # a captura continua: chega uma foto entre a analise e a previa
    (pasta / "IMG_5.jpg").write_bytes((pasta / "IMG_4.jpg").read_bytes())
    info = correcao.gerar_previa(pasta, analise, cor=False, estabilizar=True)
    assert info["total_fotos"] == 5
    assert info["falhas"] == [2]
