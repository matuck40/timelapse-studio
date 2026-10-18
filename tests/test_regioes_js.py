"""web/regioes.js converte as regioes desenhadas no quadro girado para a foto crua.

O teste roda o proprio JS no Node, para nao manter uma copia da conta em Python.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REGIOES = Path(__file__).resolve().parent.parent / "web" / "regioes.js"


def rodar(expressao):
    node = shutil.which("node")
    if not node:
        pytest.skip("node indisponivel")
    codigo = (
        f"const r = require({json.dumps(str(REGIOES))}); console.log(JSON.stringify({expressao}));"
    )
    saida = subprocess.run([node, "-e", codigo], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


def test_270_canto_superior_esquerdo_da_tela_vem_da_direita_de_cima_da_foto():
    # 270 = anti-horario: o topo-esquerdo da tela e o topo-DIREITO da foto crua
    x, y, w, h = rodar("r.paraCru('270', [0, 0, 0.25, 0.5])")
    assert [round(v, 6) for v in (x, y, w, h)] == [0.5, 0, 0.5, 0.25]


def test_90_e_o_espelho_do_270():
    x, y, w, h = rodar("r.paraCru('90', [0, 0, 0.25, 0.5])")
    assert [round(v, 6) for v in (x, y, w, h)] == [0, 0.75, 0.5, 0.25]


@pytest.mark.parametrize("giro", ["nao", "90", "180", "270"])
def test_ida_e_volta_devolve_o_mesmo_retangulo(giro):
    volta = rodar(f"r.paraTela('{giro}', r.paraCru('{giro}', [0.1, 0.2, 0.3, 0.4]))")
    assert [round(v, 6) for v in volta] == [0.1, 0.2, 0.3, 0.4]


def test_regiao_desenhada_na_previa_ampliada_volta_ao_tamanho_real():
    # a previa estabilizada tem zoom de borda 1.25 em torno do centro
    real = rodar("r.semZoom([0.5, 0.5, 0.25, 0.25], 1.25)")
    assert [round(v, 6) for v in real] == [0.5, 0.5, 0.2, 0.2]


def test_zoom_ida_e_volta():
    volta = rodar("r.comZoom(r.semZoom([0.1, 0.2, 0.3, 0.4], 1.1), 1.1)")
    assert [round(v, 6) for v in volta] == [0.1, 0.2, 0.3, 0.4]
