import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import cv2
import numpy as np
import pytest

from timelapse import acervo, ambiente, cli, servidor

RAIZ = Path(__file__).resolve().parent.parent
DIA = datetime(2026, 10, 3, 14, 30)


def test_nome_com_dia(tmp_path):
    assert cli.nome_de_saida("timelapse_{dia}.mp4", DIA) == "timelapse_2026-10-03.mp4"
    assert cli.nome_de_saida("timelapse_{data}.mp4", DIA).startswith("timelapse_20261003_1430")


def test_segundo_render_do_dia_ganha_sufixo(tmp_path):
    (tmp_path / "timelapse_2026-10-03.mp4").write_bytes(b"x")
    (tmp_path / "timelapse_2026-10-03_2.fotos.csv").write_text("x")  # sobra de um render
    livre = cli.caminho_livre(tmp_path / "timelapse_2026-10-03.mp4")
    assert livre == tmp_path / "timelapse_2026-10-03_3.mp4"


def test_caminho_livre_nao_mexe_se_esta_livre(tmp_path):
    alvo = tmp_path / "timelapse_2026-10-03.mp4"
    assert cli.caminho_livre(alvo) == alvo


def test_sugestoes_seguem_symlink(tmp_path):
    real = tmp_path / "iCloud" / "_brutos"
    for nome in ("ovo", "caveira-branca", ".oculta", "_arquivo"):
        (real / nome).mkdir(parents=True)
    (real / "solto.mp4").write_bytes(b"x")
    link = tmp_path / "_brutos"
    link.symlink_to(real, target_is_directory=True)
    assert acervo.subpastas(link) == ["caveira-branca", "ovo"]


def test_sugestoes_de_pasta_que_nao_existe(tmp_path):
    assert acervo.subpastas(tmp_path / "nada") == []


@pytest.fixture
def painel(tmp_path, monkeypatch):
    # painel.json do teste fica na pasta temporaria, nunca no do projeto
    monkeypatch.setattr(ambiente, "RAIZ", tmp_path)
    http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Painel)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{http.server_address[1]}"
    http.shutdown()


def chamar(url, corpo=None):
    dados = None if corpo is None else json.dumps(corpo).encode()
    pedido = Request(url, data=dados, headers={"Content-Type": "application/json"})
    with urlopen(pedido) as resposta:
        return json.loads(resposta.read())


def test_trocar_brutos_aceita_symlink_e_grava_painel_json(painel, tmp_path):
    real = tmp_path / "iCloud" / "_brutos"
    (real / "ovo").mkdir(parents=True)
    link = tmp_path / "_brutos"
    link.symlink_to(real, target_is_directory=True)
    resposta = chamar(painel + "/api/brutos/raiz", {"caminho": str(link)})
    assert resposta == {"pasta": str(link), "sugestoes": ["ovo"]}
    # guarda o link, nao o destino: se o iCloud mudar de lugar, o link continua valendo
    assert json.loads((tmp_path / "painel.json").read_text())["pasta_brutos"] == str(link)
    assert chamar(painel + "/api/brutos") == {"pasta": str(link), "sugestoes": ["ovo"]}
    assert chamar(painel + "/api/config")["pasta_brutos"] == str(link)


def test_trocar_brutos_recusa_link_quebrado(painel, tmp_path):
    link = tmp_path / "_brutos"
    link.symlink_to(tmp_path / "sumiu", target_is_directory=True)
    with pytest.raises(HTTPError) as erro:
        chamar(painel + "/api/brutos/raiz", {"caminho": str(link)})
    assert erro.value.code == 400


def test_peca_e_salva_no_enquadramento(painel, tmp_path):
    (tmp_path / "enquadramento.json").write_text(json.dumps({"zoom": 1.2}))
    chamar(
        painel + "/api/enquadramento/correcao",
        {"pasta": str(tmp_path), "correcao": {"peca": "ovo-de-pascoa"}},
    )
    salvo = json.loads((tmp_path / "enquadramento.json").read_text())
    assert salvo == {"zoom": 1.2, "peca": "ovo-de-pascoa"}


def test_render_vai_para_brutos_da_peca(tmp_path):
    try:
        cli.find_ffmpeg()
    except ValueError:
        pytest.skip("ffmpeg indisponivel")
    fotos = tmp_path / "fotos"
    fotos.mkdir()
    for i in range(3):
        cv2.imwrite(str(fotos / f"IMG_{i}.jpg"), np.full((40, 60, 3), i * 60, np.uint8))
    real = tmp_path / "iCloud" / "_brutos"
    real.mkdir(parents=True)
    link = tmp_path / "_brutos"
    link.symlink_to(real, target_is_directory=True)

    def render():
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "timelapse.cli",
                str(fotos),
                "--sem-config",
                "--pasta-saida",
                str(link / "ovo" / "timelapse"),
                "--nome-saida",
                "timelapse_{dia}.mp4",
            ],
            capture_output=True,
            text=True,
            cwd=RAIZ,
            env=os.environ,
        )

    hoje = datetime.now().strftime("%Y-%m-%d")
    primeiro, segundo = render(), render()
    assert primeiro.returncode == 0, primeiro.stderr
    assert segundo.returncode == 0, segundo.stderr
    # <peca>/ e timelapse/ foram criadas dentro do destino real do link
    assert (real / "ovo" / "timelapse" / f"timelapse_{hoje}.mp4").is_file()
    assert (real / "ovo" / "timelapse" / f"timelapse_{hoje}_2.mp4").is_file()
