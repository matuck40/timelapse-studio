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
    codigo = (f"const p = require({json.dumps(str(PECA))});"
              f" console.log(JSON.stringify(p.normalizarPeca({json.dumps(texto)})));")
    saida = subprocess.run([node, "-e", codigo], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


@pytest.mark.parametrize("texto, pasta", [
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
])
def test_normaliza_para_nome_de_pasta(texto, pasta):
    assert normalizar(texto) == pasta
