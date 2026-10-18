import json
import shutil
from pathlib import Path

from timelapse import ambiente, cli, servidor

RAIZ_REAL = Path(__file__).resolve().parents[1]


def _isolar(monkeypatch, tmp_path):
    monkeypatch.setattr(ambiente, "RAIZ", tmp_path)
    monkeypatch.delenv("TIMELAPSE_ACERVO", raising=False)
    monkeypatch.delenv("TIMELAPSE_PORTA", raising=False)


def test_opcoes_sem_painel_json_usa_padroes(tmp_path, monkeypatch):
    _isolar(monkeypatch, tmp_path)
    assert servidor.opcoes() == {"acervo": "", "porta": 8765, "limite_cache": 300,
                                 "lado_cache": 1050, "pasta_brutos": ""}


def test_painel_example_carrega_e_nao_tem_caminho_pessoal(tmp_path, monkeypatch):
    _isolar(monkeypatch, tmp_path)
    shutil.copy(RAIZ_REAL / "painel.example.json", tmp_path / "painel.json")
    cfg = servidor.opcoes()
    assert cfg["porta"] == 8765
    texto = (RAIZ_REAL / "painel.example.json").read_text()
    for proibido in ("/Users/", "/Volumes/", "iCloud", "Em_Camadas", "Em camadas"):
        assert proibido not in texto


def test_config_example_so_tem_chaves_conhecidas():
    valores = json.loads((RAIZ_REAL / "config.example.json").read_text())
    assert set(valores) <= set(cli.DEFAULTS)


def test_servidor_escuta_so_em_loopback():
    assert '("127.0.0.1", cfg["porta"])' in Path(servidor.__file__).read_text()
