from pathlib import Path
from types import SimpleNamespace

import pytest

from timelapse import cli


def args(**extra):
    base = dict(fps=30, preset='medium', qualidade=16, previa=False, zoom=1.0,
                resolucao='1080x1920', enquadramento='preencher')
    base.update(extra)
    return SimpleNamespace(**base)


def test_desligado_gera_o_mesmo_comando_de_antes(monkeypatch):
    monkeypatch.setattr(cli, 'bandeira_de_quadros', lambda ffmpeg: ['-fps_mode', 'passthrough'])
    work, video = Path('/tmp/w'), Path('/tmp/w/video.mp4')
    a = args()
    comando = cli.comando_ffmpeg('ff', a, cli.entrada_imagens(a, work, 'jpg'), 'FILTRO', video)
    # copia literal do comando de antes da correcao (cli.py, commit 40dccdf)
    assert comando == ['ff', '-hide_banner', '-loglevel', 'warning', '-stats', '-nostdin',
                       '-xerror', '-noautorotate', '-f', 'image2', '-framerate', '30',
                       '-start_number', '0', '-i', '/tmp/w/%08d.jpg', '-vf', 'FILTRO',
                       '-c:v', 'libx264', '-preset', 'medium', '-crf', '16',
                       '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough',
                       '-an', '-movflags', '+faststart', '/tmp/w/video.mp4']


def test_desligado_previa_gera_o_mesmo_comando_de_antes(monkeypatch):
    monkeypatch.setattr(cli, 'bandeira_de_quadros', lambda ffmpeg: ['-fps_mode', 'passthrough'])
    work, video = Path('/tmp/w'), Path('/tmp/w/previa.png')
    a = args(previa=True)
    comando = cli.comando_ffmpeg('ff', a, cli.entrada_imagens(a, work, 'jpg'), 'FILTRO', video)
    assert comando == ['ff', '-hide_banner', '-loglevel', 'warning', '-stats', '-nostdin',
                       '-xerror', '-noautorotate', '-f', 'image2', '-framerate', '30',
                       '-start_number', '0', '-i', '/tmp/w/%08d.jpg', '-vf', 'FILTRO',
                       '-frames:v', '1', '-c:v', 'png', '-update', '1', '/tmp/w/previa.png']


def test_regiao_aceita_texto_e_lista():
    assert cli.ler_regiao('0.1,0.2,0.3,0.4', 'r') == [0.1, 0.2, 0.3, 0.4]
    assert cli.ler_regiao([0, 0, 1, 1], 'r') == [0.0, 0.0, 1.0, 1.0]
    assert cli.ler_regiao(None, 'r') is None


@pytest.mark.parametrize('ruim', ['1,2,3', 'a,b,c,d', [0.5, 0.5, 0.6, 0.1], [0, 0, 0, 0.5]])
def test_regiao_invalida_e_recusada(ruim):
    with pytest.raises(ValueError):
        cli.ler_regiao(ruim, 'r')


def test_padroes_deixam_a_correcao_desligada():
    assert cli.DEFAULTS['corrigir_cor'] is False
    assert cli.DEFAULTS['estabilizar'] is False
