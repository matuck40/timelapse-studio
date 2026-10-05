import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from timelapse import cli

RAIZ = Path(__file__).resolve().parent.parent


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


def test_escala_para_reel_de_foto_6000x4000_girada():
    # girada fica 4000x6000; preencher 1080x1920 escala por max(1080/4000, 1920/6000) = 0.32
    assert cli.escala_necessaria(args(), 6000, 4000, '270') == pytest.approx(0.32)


def test_escala_considera_zoom_do_usuario_e_da_borda():
    assert cli.escala_necessaria(args(zoom=2.0), 6000, 4000, '270', 1.1) == pytest.approx(0.704)


def test_escala_nunca_passa_da_foto_original():
    assert cli.escala_necessaria(args(zoom=5.0), 6000, 4000, '270') == 1.0
    assert cli.escala_necessaria(args(resolucao='original'), 6000, 4000, '270') == 1.0


def _ffmpeg_ou_pula():
    try:
        return cli.find_ffmpeg()
    except ValueError:
        pytest.skip('ffmpeg indisponivel')


def _pasta_tremida(tmp_path):
    """Cinco JPGs pequenos com a camera tremendo para a direita."""
    pasta = tmp_path / 'fotos'
    pasta.mkdir()
    gerador = np.random.default_rng(3)
    base = cv2.resize(gerador.integers(0, 256, (40, 60, 3), dtype=np.uint8), (600, 400),
                      interpolation=cv2.INTER_CUBIC)
    for i, dx in enumerate([0, 4, 9, 9, 2]):
        quadro = cv2.warpAffine(base, np.float64([[1, 0, dx], [0, 1, 0]]), (600, 400),
                                borderMode=cv2.BORDER_REFLECT)
        cv2.imwrite(str(pasta / f'IMG_{i}.jpg'), quadro)
    return pasta


def rodar_cli(tmp_path, *argumentos):
    """Roda a CLI de verdade, com o cache numa pasta temporaria."""
    return subprocess.run(
        [sys.executable, '-m', 'timelapse.cli', *argumentos, '--sem-config'],
        capture_output=True, text=True, cwd=RAIZ,
        env={**os.environ, 'TIMELAPSE_CACHE': str(tmp_path / 'cache')})


def test_render_corrigido_de_ponta_a_ponta(tmp_path):
    _ffmpeg_ou_pula()
    pasta, saida = _pasta_tremida(tmp_path), tmp_path / 'saida.mp4'
    resultado = rodar_cli(
        tmp_path, str(pasta), '--resolucao', '200x300', '--estabilizar', '--corrigir-cor',
        '--referencia', 'IMG_0.jpg', '--regiao-cor', '0.1,0.1,0.3,0.3',
        '--regiao-alinhamento', '0.2,0.2,0.6,0.6', '--saida', str(saida))
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert saida.stat().st_size > 0
    assert 'Zoom extra' in resultado.stdout


@pytest.mark.parametrize('extra', [
    # referencia fora do trecho escolhido, ordem invertida e pulando fotos
    ['--inicio', '2', '--passo', '2', '--inverter'],
    # a duracao repete fotos: cada repeticao usa a correcao da sua foto
    ['--duracao', '1', '--fps', '24'],
    ['--previa'],
])
def test_render_corrigido_respeita_selecao(tmp_path, extra):
    _ffmpeg_ou_pula()
    pasta, saida = _pasta_tremida(tmp_path), tmp_path / 'saida.mp4'
    resultado = rodar_cli(
        tmp_path, str(pasta), '--resolucao', '200x300', '--estabilizar',
        '--referencia', 'IMG_0.jpg', '--regiao-alinhamento', '0.2,0.2,0.6,0.6',
        '--saida', str(saida), *extra)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert 'Zoom extra' in resultado.stdout  # a correcao rodou, nao so o render antigo
    gerado = saida.with_suffix('.previa.png') if '--previa' in extra else saida
    assert gerado.stat().st_size > 0


def test_referencia_que_nao_existe_e_recusada(tmp_path):
    pasta = _pasta_tremida(tmp_path)
    resultado = rodar_cli(
        tmp_path, str(pasta), '--estabilizar', '--referencia', 'NAO_EXISTE.jpg',
        '--regiao-alinhamento', '0.2,0.2,0.6,0.6', '--saida', str(tmp_path / 's.mp4'))
    assert resultado.returncode == 1
    assert 'referência não está na pasta' in resultado.stderr


def test_foto_que_falha_no_meio_do_render_nao_trava(tmp_path):
    # captura ainda gravando: a foto esta truncada quando o render chega nela
    _ffmpeg_ou_pula()
    pasta = _pasta_tremida(tmp_path)
    parametros = ('--resolucao', '200x300', '--estabilizar', '--referencia', 'IMG_0.jpg',
                  '--regiao-alinhamento', '0.2,0.2,0.6,0.6')
    primeiro = rodar_cli(tmp_path, str(pasta), *parametros, '--saida', str(tmp_path / 'a.mp4'))
    assert primeiro.returncode == 0, primeiro.stderr
    foto = pasta / 'IMG_3.jpg'
    foto.write_bytes(foto.read_bytes()[:600])  # a analise salva e reaproveitada
    try:
        segundo = subprocess.run(
            [sys.executable, '-m', 'timelapse.cli', str(pasta), *parametros, '--sem-config',
             '--saida', str(tmp_path / 'b.mp4')],
            capture_output=True, text=True, cwd=RAIZ, timeout=60,
            env={**os.environ, 'TIMELAPSE_CACHE': str(tmp_path / 'cache')})
    except subprocess.TimeoutExpired:
        pytest.fail('o render travou esperando o ffmpeg')
    assert segundo.returncode == 1
    assert 'Não foi possível concluir' in segundo.stderr
