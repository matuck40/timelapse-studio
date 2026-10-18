"""web/peca.js transforma o texto do campo Peca num nome de subpasta de _brutos/."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PECA = Path(__file__).resolve().parent.parent / "web" / "peca.js"


def normalizar(texto):
    node = shutil.which("node")
    if not node:
        pytest.skip("node indisponivel")
    codigo = (
        f"const p = require({json.dumps(str(PECA))});"
        f" console.log(JSON.stringify(p.normalizarPeca({json.dumps(texto)})));"
    )
    saida = subprocess.run([node, "-e", codigo], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


@pytest.mark.parametrize(
    "texto, pasta",
    [
        ("Caveira Vermelha", "caveira-vermelha"),
        ("Ovo de Páscoa", "ovo-de-pascoa"),
        ("  Ação   2026 ", "acao-2026"),
        # como o atalho do iPhone: so espaco vira hifen, o resto fica
        ("ovo_v2", "ovo_v2"),
        ("Ovo de Páscoa_2!", "ovo-de-pascoa_2!"),
        # a peca vira parte de um caminho: nada de subir pasta nem de pasta oculta
        ("../../etc", "etc"),
        ("..", ""),
        ("", ""),
    ],
)
def test_normaliza_para_nome_de_pasta(texto, pasta):
    assert normalizar(texto) == pasta


def escolher(texto, existentes):
    node = shutil.which("node")
    if not node:
        pytest.skip("node indisponivel")
    codigo = (
        f"const p = require({json.dumps(str(PECA))});"
        f" console.log(JSON.stringify(p.escolherPeca({json.dumps(texto)},"
        f" {json.dumps(existentes)})));"
    )
    saida = subprocess.run([node, "-e", codigo], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


def test_pasta_existente_com_acento_e_usada_como_esta():
    # o atalho do iPhone criou a pasta com acento; escolher a sugestao nao pode duplicar
    assert escolher("ovo-de-páscoa_2!", ["caveira", "ovo-de-páscoa_2!"]) == "ovo-de-páscoa_2!"
    assert escolher("Ovo de Pascoa_2!", ["ovo-de-páscoa_2!"]) == "ovo-de-páscoa_2!"


def test_pasta_existente_em_nfd_do_mac_tambem_casa():
    nfd = "ovo-de-páscoa"  # o Mac pode guardar o acento separado da letra
    assert escolher("ovo-de-páscoa", [nfd]) == nfd


def test_peca_nova_e_normalizada():
    assert escolher("Gaveta Nova", ["ovo"]) == "gaveta-nova"
