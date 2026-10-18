"""O painel so atende o proprio navegador: Host, Origin e tipo do corpo conferidos."""

import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

from timelapse import ambiente, cache, servidor


@pytest.fixture
def painel(tmp_path, monkeypatch):
    # painel.json e cache do teste ficam na pasta temporaria, nunca nos do projeto
    monkeypatch.setattr(ambiente, "RAIZ", tmp_path)
    monkeypatch.setattr(cache, "RAIZ_CACHE", tmp_path / "cache")
    http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Painel)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield http.server_address[1]
    http.shutdown()


def pedir(porta, metodo, caminho, corpo=None, cabecalhos=None):
    """http.client manda os cabecalhos como estao, sem completar nada."""
    conexao = HTTPConnection("127.0.0.1", porta, timeout=5)
    try:
        conexao.request(metodo, caminho, body=corpo, headers=cabecalhos or {})
        resposta = conexao.getresponse()
        return resposta.status, resposta.read()
    finally:
        conexao.close()


def salvar_enquadramento(porta, pasta, cabecalhos):
    corpo = json.dumps({"pasta": str(pasta), "parametros": {"x": 1}}).encode()
    return pedir(porta, "POST", "/api/enquadramento", corpo, cabecalhos)


@pytest.fixture
def pasta(tmp_path):
    destino = tmp_path / "fotos"
    destino.mkdir()
    return destino


def test_post_de_outro_site_e_recusado(painel, pasta):
    status, _ = salvar_enquadramento(
        painel,
        pasta,
        {"Content-Type": "application/json", "Origin": "https://evil.example"},
    )
    assert status == 403
    assert not (pasta / "enquadramento.json").exists()


def test_post_sem_json_e_recusado(painel, pasta):
    # text/plain e o que um formulario de outro site consegue mandar sem preflight
    status, _ = salvar_enquadramento(painel, pasta, {"Content-Type": "text/plain"})
    assert status == 403
    assert not (pasta / "enquadramento.json").exists()


def test_host_estranho_e_recusado(painel):
    # DNS rebinding: o navegador manda o nome do site atacante no Host
    status, _ = pedir(painel, "GET", "/api/config", cabecalhos={"Host": f"evil.example:{painel}"})
    assert status == 403


def test_pedido_do_proprio_painel_passa(painel, pasta):
    status, _ = salvar_enquadramento(
        painel,
        pasta,
        {
            "Host": f"localhost:{painel}",
            "Origin": f"http://localhost:{painel}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    assert status == 200
    assert json.loads((pasta / "enquadramento.json").read_text(encoding="utf-8")) == {"x": 1}


def test_get_do_proprio_painel_passa(painel):
    status, corpo = pedir(painel, "GET", "/api/config")
    assert status == 200
    assert "acervo" in json.loads(corpo)


def test_json_quebrado_vira_400(painel):
    status, corpo = pedir(
        painel,
        "POST",
        "/api/enquadramento",
        b"{nao e json",
        {"Content-Type": "application/json"},
    )
    assert status == 400
    assert "erro" in json.loads(corpo)
