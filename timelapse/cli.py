#!/usr/bin/env python3
"""Gera um MP4 de uma sequência de fotos, sem alterar os originais."""
import argparse
import csv
import json
import math
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import struct
import sys
import tempfile

# A raiz do repositorio: e la que ficam bin/ffmpeg e config.json.
ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS = {'.jpg': 'jpg', '.jpeg': 'jpg', '.png': 'png'}


def natural_key(path):
    # IMG_2 antes de IMG_10; desempate determinístico para zeros à esquerda.
    return (tuple((1, int(s)) if s.isdigit() else (0, s.casefold())
                  for s in re.split(r'(\d+)', path.name)), path.name)


def find_ffmpeg():
    local = ROOT / 'bin' / 'ffmpeg'
    candidates = [str(local), shutil.which('ffmpeg'), '/opt/homebrew/bin/ffmpeg',
                  '/usr/local/bin/ffmpeg']
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise ValueError('FFmpeg não encontrado. Mantenha a pasta bin junto do script.')


def bandeira_de_quadros(ffmpeg):
    """-fps_mode e do FFmpeg 5 em diante; antes disso o equivalente e -vsync.

    Mantem o projeto rodando tanto no binario empacotado (novo) quanto num
    FFmpeg 4.x de distribuicao Linux.
    """
    try:
        versao = subprocess.run(
            [ffmpeg, '-version'], capture_output=True, text=True, timeout=10
        ).stdout
        achado = re.search(r'version\s+n?(\d+)', versao)
        if achado and int(achado.group(1)) >= 5:
            return ['-fps_mode', 'passthrough']
    except (OSError, subprocess.SubprocessError):
        pass
    return ['-vsync', 'passthrough']


def choose_folder():
    if sys.platform != 'darwin':
        raise ValueError('Informe a pasta das fotos como argumento.')
    result = subprocess.run(['osascript', '-e',
        'POSIX path of (choose folder with prompt "Escolha a pasta com as fotos de UMA impressão")'],
        capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Seleção de pasta cancelada.')
    return Path(result.stdout.strip())


DEFAULTS = {
    'fps': 30, 'duracao': None, 'velocidade': 1.0,
    'resolucao': 'original', 'enquadramento': 'ajustar',
    'qualidade': 16, 'preset': 'medium', 'ordem': 'nome',
    'inicio': 1, 'fim': None, 'passo': 1, 'inverter': False,
    'zoom': 1.0, 'pos_x': 0.0, 'pos_y': 0.0,
    'pasta_saida': None, 'nome_saida': 'timelapse_{data}.mp4',
    'girar': 'auto',
}


def parse_args():
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument('--config', type=Path)
    bootstrap.add_argument('--sem-config', action='store_true')
    initial, _ = bootstrap.parse_known_args()
    if initial.config and initial.sem_config:
        bootstrap.error('Use --config ou --sem-config, não ambos.')
    defaults = DEFAULTS.copy()
    config = initial.config or ROOT / 'config.json'
    if not initial.sem_config and (initial.config or config.exists()):
        with config.expanduser().open(encoding='utf-8') as handle:
            values = json.load(handle)
        if not isinstance(values, dict):
            raise ValueError('A configuração precisa ser um objeto JSON.')
        unknown = set(values) - set(DEFAULTS)
        if unknown:
            raise ValueError(f'Parâmetros desconhecidos na configuração: {sorted(unknown)}')
        defaults.update(values)
    parser = argparse.ArgumentParser(description=__doc__, parents=[bootstrap])
    parser.add_argument('pasta', nargs='?', type=Path, help='Pasta de uma impressão; omitida, abre o seletor no Mac.')
    parser.add_argument('--fps', type=int, help='Quadros por segundo: 24, 25, 30 ou 60.')
    parser.add_argument('--duracao', type=float, help='Duração final em segundos. Repete ou descarta fotos para caber.')
    parser.add_argument('--velocidade', type=float, help='Multiplicador: 2 acelera 2x; 0.5 desacelera. Alternativa à duração.')
    parser.add_argument('--resolucao', help='original ou LARGURAxALTURA, como 1080x1920.')
    parser.add_argument('--enquadramento', choices=['ajustar', 'preencher'], help='Ajustar: bordas pretas. Preencher: corta conforme posição X/Y.')
    parser.add_argument('--qualidade', type=int, help='CRF 0 a 51: menor = maior qualidade e arquivo. Padrão 16.')
    parser.add_argument('--preset', choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'], help='Velocidade de compressão; fast demora menos, slow tende a comprimir melhor.')
    parser.add_argument('--ordem', choices=['nome', 'data'], help='Nome numérico ou data de modificação (não EXIF).')
    parser.add_argument('--inicio', type=int, help='Primeira foto, começando em 1, após ordenar.')
    parser.add_argument('--fim', type=int, help='Última foto, inclusive; omitido usa até o fim.')
    parser.add_argument('--passo', type=int, help='Usar uma a cada N fotos, a partir do início selecionado.')
    parser.add_argument('--inverter', action=argparse.BooleanOptionalAction, help='Reverter sequência; --no-inverter desativa.')
    parser.add_argument('--zoom', type=float, help='Ampliação: 1 = sem zoom; 1.5 = 150%%; até 20.')
    parser.add_argument('--pos-x', type=float, help='Enquadramento horizontal: -100 esquerda, 0 centro, 100 direita.')
    parser.add_argument('--pos-y', type=float, help='Enquadramento vertical: -100 topo, 0 centro, 100 base.')
    parser.add_argument('--pasta-saida', help='Pasta de destino. Padrão: pasta das fotos.')
    parser.add_argument('--nome-saida', help='Nome do MP4; {data} insere data/hora única.')
    parser.add_argument('--previa', action='store_true', help='Gera só um PNG do primeiro quadro selecionado, com os ajustes.')
    parser.add_argument('--saida', type=Path, help='Caminho do MP4 novo. Nunca sobrescreve arquivos.')
    parser.add_argument('--conferir', action='store_true', help='Mostra sequência final e duração sem gerar vídeo.')
    parser.add_argument('--girar', choices=['auto', 'nao', '90', '180', '270'],
                        help='Giro aplicado antes de tudo. auto lê a etiqueta EXIF; nao mantém os pixels como estão.')
    parser.set_defaults(**defaults)
    args = parser.parse_args()
    # Uma opção explícita de tempo substitui a alternativa salva no JSON.
    explicit = {token.split('=')[0] for token in sys.argv[1:] if token.startswith('--')}
    if '--duracao' in explicit and '--velocidade' in explicit:
        parser.error('Use --duracao ou --velocidade, não ambos.')
    if '--duracao' in explicit:
        args.velocidade = 1.0
    if '--velocidade' in explicit:
        args.duracao = None
    for key in ('fps', 'qualidade', 'inicio', 'passo'):
        if type(getattr(args, key)) is not int:
            raise ValueError(f'{key} precisa ser um número inteiro.')
    if args.fim is not None and type(args.fim) is not int:
        raise ValueError('fim precisa ser inteiro ou null.')
    for key in ('duracao', 'velocidade'):
        value = getattr(args, key)
        if key == 'duracao' and value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{key} precisa ser um número positivo e finito.')
    if type(args.inverter) is not bool:
        raise ValueError('inverter precisa ser true ou false.')
    if args.fps not in (24, 25, 30, 60) or not 0 <= args.qualidade <= 51:
        raise ValueError('fps deve ser 24, 25, 30 ou 60; qualidade deve estar entre 0 e 51.')
    if args.inicio < 1 or args.passo < 1 or (args.fim is not None and args.fim < args.inicio):
        raise ValueError('inicio e passo devem ser positivos; fim não pode ser menor que inicio.')
    for key, choices in [('ordem', ('nome', 'data')), ('enquadramento', ('ajustar', 'preencher')),
                         ('girar', ('auto', 'nao', '90', '180', '270')),
                         ('preset', ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'))]:
        if getattr(args, key) not in choices:
            raise ValueError(f'{key} deve ser uma destas opções: {choices}')
    if args.duracao is not None and args.velocidade != 1:
        raise ValueError('Na configuração, escolha duracao ou velocidade diferente de 1, não ambos.')
    if not isinstance(args.resolucao, str):
        raise ValueError('resolucao precisa ser original ou LARGURAxALTURA.')
    if args.resolucao != 'original':
        match = re.fullmatch(r'(\d+)x(\d+)', args.resolucao)
        if not match or any(int(v) < 2 or int(v) % 2 for v in match.groups()):
            raise ValueError('resolucao deve ser original ou dimensões pares, como 1080x1920.')
    for key, low, high in [('zoom', 1, 20), ('pos_x', -100, 100), ('pos_y', -100, 100)]:
        value = getattr(args, key)
        if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{key} deve ser um número entre {low} e {high}.')
    if args.pasta_saida is not None and (not isinstance(args.pasta_saida, str) or not args.pasta_saida.strip()):
        raise ValueError('pasta_saida deve ser um caminho ou null.')
    if (not isinstance(args.nome_saida, str) or not args.nome_saida
            or '/' in args.nome_saida or '\\' in args.nome_saida
            or not args.nome_saida.lower().endswith('.mp4')):
        raise ValueError('nome_saida deve ser apenas um nome terminado em .mp4, sem pastas.')
    return args


def image_size(path):
    """Lê dimensões JPG/PNG sem carregar os pixels nem depender de bibliotecas extras."""
    with path.open('rb') as handle:
        header = handle.read(24)
        if header[:8] == b'\x89PNG\r\n\x1a\n' and len(header) == 24:
            return struct.unpack('>II', header[16:24])
        handle.seek(0)
        if handle.read(2) == b'\xff\xd8':
            while True:
                byte = handle.read(1)
                if not byte:
                    break
                if byte != b'\xff':
                    continue
                marker = handle.read(1)
                while marker == b'\xff':
                    marker = handle.read(1)
                if not marker or marker in (b'\xda', b'\xd9'):
                    break
                if marker == b'\x00' or marker[0] in (0x01, *range(0xd0, 0xd9)):
                    continue
                length_bytes = handle.read(2)
                if len(length_bytes) != 2:
                    break
                length = int.from_bytes(length_bytes, 'big')
                if length < 2:
                    break
                if marker[0] in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
                    data = handle.read(5)
                    if len(data) == 5:
                        height, width = struct.unpack('>HH', data[1:])
                        return width, height
                    break
                handle.seek(length - 2, 1)
    raise ValueError(f'Não foi possível ler as dimensões: {path.name}')


ROTATIONS = {'90': 'transpose=1', '180': 'transpose=1,transpose=1', '270': 'transpose=2'}
EXIF_TO_GIRO = {1: 'nao', 3: '180', 6: '90', 8: '270'}


def exif_orientation(path):
    """Lê a etiqueta EXIF de orientação (0x0112). Devolve None quando não existe."""
    try:
        with path.open('rb') as handle:
            data = handle.read(262144)
    except OSError:
        return None
    marker = data.find(b'Exif\x00\x00')
    if marker < 0:
        return None
    tiff = data[marker + 6:]
    order = '>' if tiff[:2] == b'MM' else '<' if tiff[:2] == b'II' else None
    if order is None or len(tiff) < 8:
        return None
    try:
        offset = struct.unpack(order + 'I', tiff[4:8])[0]
        count = struct.unpack(order + 'H', tiff[offset:offset + 2])[0]
        for index in range(count):
            entry = offset + 2 + index * 12
            if struct.unpack(order + 'H', tiff[entry:entry + 2])[0] == 0x0112:
                return struct.unpack(order + 'H', tiff[entry + 8:entry + 10])[0]
    except (struct.error, IndexError):
        return None
    return None


def giro_de(args, photo):
    """Resolve o giro final: o valor fixo pedido, ou o que a etiqueta EXIF indica."""
    if args.girar != 'auto':
        return args.girar
    orientation = exif_orientation(photo)
    if orientation is None:
        return 'nao'
    if orientation not in EXIF_TO_GIRO:
        print(f'Aviso: orientação EXIF {orientation} é espelhada e não é tratada; nada será girado.', flush=True)
        return 'nao'
    return EXIF_TO_GIRO[orientation]


def video_filter(args, first_photo):
    source_w, source_h = image_size(first_photo)
    filters = []
    giro = giro_de(args, first_photo)
    if giro != 'nao':
        filters.append(ROTATIONS[giro])
        if giro in ('90', '270'):
            source_w, source_h = source_h, source_w
    if min(source_w, source_h) < 2 * args.zoom:
        raise ValueError('Zoom excessivo para as dimensões desta foto.')
    if args.resolucao == 'original':
        width, height = source_w + source_w % 2, source_h + source_h % 2
    else:
        width, height = map(int, args.resolucao.split('x'))
    px, py = (args.pos_x + 100) / 200, (args.pos_y + 100) / 200
    if args.zoom != 1:
        filters.append(f'crop=w=trunc(iw/{args.zoom}/2)*2:h=trunc(ih/{args.zoom}/2)*2:'
                       f'x=(iw-ow)*{px}:y=(ih-oh)*{py}')
    if args.resolucao == 'original' and args.zoom == 1:
        filters.append(f'pad={width}:{height}')
    elif args.enquadramento == 'ajustar':
        filters.append(f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2')
        filters.append(f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2')
    else:
        filters.append(f'scale={width}:{height}:force_original_aspect_ratio=increase:force_divisible_by=2')
        filters.append(f'crop={width}:{height}:(iw-ow)*{px}:(ih-oh)*{py}')
    return ','.join(filters + ['setsar=1'])


def main():
    args = parse_args()
    folder = (args.pasta or choose_folder()).expanduser().resolve()
    if not folder.is_dir():
        raise ValueError(f'Pasta não encontrada: {folder}')
    photos = [p for p in folder.iterdir() if p.is_file() and not p.name.startswith('.')
              and p.suffix.lower() in EXTENSIONS]
    photos.sort(key=natural_key if args.ordem == 'nome' else lambda p: (p.stat().st_mtime_ns, natural_key(p)))
    if len(photos) < 2:
        raise ValueError('A pasta precisa ter pelo menos duas fotos JPG/JPEG ou PNG. Subpastas não são incluídas.')
    total = len(photos)
    if args.inicio > total or (args.fim is not None and args.fim > total):
        raise ValueError(f'A seleção ultrapassa as {total} fotos da pasta.')
    photos = photos[args.inicio - 1:args.fim:args.passo]
    if args.inverter:
        photos.reverse()
    kinds = {EXTENSIONS[p.suffix.lower()] for p in photos}
    if len(kinds) != 1:
        raise ValueError('Há JPG e PNG misturados na seleção. Separe uma sequência de um único formato.')
    selected_count = len(photos)
    target = args.duracao * args.fps if args.duracao is not None else selected_count / args.velocidade
    if not math.isfinite(target) or target < 1:
        raise ValueError('A duração/velocidade solicitada resulta em menos de um quadro ou é excessiva.')
    count = int(math.floor(target + 0.5))
    if count != selected_count:
        # Amostragem uniforme incluindo as pontas (quando há ao menos dois quadros).
        photos = [photos[round(i * (selected_count - 1) / (count - 1)) if count > 1 else 0]
                  for i in range(count)]
    print(f'\n{selected_count}/{total} fotos selecionadas | {count} quadros | '
          f'{args.fps} quadros/s | {count/args.fps:.3f} segundos', flush=True)
    print(f'Resolução: {args.resolucao} | Enquadramento: {args.enquadramento} | CRF: {args.qualidade}', flush=True)
    if args.girar == 'auto':
        amostra = [photos[0], photos[len(photos) // 2], photos[-1]]
        giros = {giro_de(args, photo) for photo in amostra}
        if len(giros) > 1:
            raise ValueError('A seleção mistura fotos com orientações EXIF diferentes. '
                             'Separe as sequências ou informe --girar com um valor fixo.')
    giro = giro_de(args, photos[0])
    print(f'Giro: {giro}' + (' (etiqueta EXIF)' if args.girar == 'auto' and giro != 'nao' else ''), flush=True)
    if count != selected_count:
        print('Atenção: a duração/velocidade escolhida repete ou descarta fotos; não cria movimento intermediário.', flush=True)
    print(f'Primeira: {photos[0].name}\nÚltima:   {photos[-1].name}', flush=True)
    if args.conferir:
        for index, photo in enumerate(photos):
            print(f'{index+1:06d}  {index/args.fps:9.3f}s  {photo.name}')
        return
    ffmpeg = find_ffmpeg()
    destination = Path(args.pasta_saida).expanduser() if args.pasta_saida else folder
    name = args.nome_saida.replace('{data}', datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output = (args.saida or destination / name).expanduser().resolve()
    if output.suffix.lower() != '.mp4':
        raise ValueError('A saída precisa terminar em .mp4.')
    if args.previa:
        output = output.with_suffix('.previa.png')
    manifest = output.with_suffix('.fotos.csv')
    if output.exists() or manifest.exists():
        raise ValueError('O vídeo ou relatório já existe. Escolha outro nome de saída.')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Arquivos temporários no mesmo disco: publicação final sem sobrescrever.
    with tempfile.TemporaryDirectory(prefix='.timelapse-', dir=output.parent) as temp:
        work = Path(temp)
        extension = next(iter(kinds))
        for index, photo in enumerate(photos):
            (work / f'{index:08d}.{extension}').symlink_to(photo)
        video = work / ('previa.png' if args.previa else 'video.mp4')
        report = work / 'fotos.csv'
        command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-stats', '-nostdin',
                   '-xerror', '-noautorotate', '-f', 'image2', '-framerate', str(args.fps), '-start_number', '0',
                   '-i', str(work / f'%08d.{extension}'),
                   '-vf', video_filter(args, photos[0]),
                   '-c:v', 'libx264', '-preset', args.preset, '-crf', str(args.qualidade),
                   '-pix_fmt', 'yuv420p', *bandeira_de_quadros(ffmpeg),
                   '-an', '-movflags', '+faststart', str(video)]
        if args.previa:
            command = command[:command.index('-c:v')] + ['-frames:v', '1', '-c:v', 'png', '-update', '1', str(video)]
        subprocess.run(command, check=True)
        if not video.is_file() or video.stat().st_size == 0:
            raise ValueError('O conversor não produziu um vídeo válido.')
        if args.previa:
            os.link(video, output)
            print(f'\nPrévia pronta: {output}', flush=True)
            return
        with report.open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.writer(handle)
            writer.writerow(['quadro (começa em 1)', 'segundos', 'foto original'])
            for index, photo in enumerate(photos):
                writer.writerow([index + 1, f'{index/args.fps:.6f}', str(photo)])
        os.link(report, manifest)
        try:
            os.link(video, output)
        except BaseException:
            manifest.unlink()
            raise
    print(f'\nPronto!\nVídeo: {output}\nOrdem das fotos: {manifest}', flush=True)


def cli():
    """Ponto de entrada com tratamento de erro, usado pelo console script."""
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'\nNão foi possível concluir: {error}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nGeração cancelada. As fotos originais estão preservadas.', file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    cli()
