# timelapse-studio

Painel local para montar timelapses de impressão 3D a partir de sequências de fotos
da câmera. Roda na própria máquina, sem serviço externo e sem dependência de `pip`.

O problema que ele resolve: decidir o enquadramento **antes** de gastar um render.
Uma peça fora do centro da mesa é decepada por um corte vertical centrado, e isso só
aparece no fim da impressão, quando a peça está no tamanho máximo. O painel mostra
qualquer quadro da sequência com o recorte aplicado, na hora.

## Como usar

Dois cliques em **`Abrir painel.command`**. O servidor sobe e o navegador abre em
`http://localhost:8765`.

Pelo terminal, o equivalente:

```bash
make painel
```

O fluxo na tela:

1. Escolha uma sequência na coluna da esquerda.
2. Na primeira vez ele monta um cache de prévia — algumas dezenas de segundos, uma vez
   só por sequência.
3. Ajuste zoom, pos-x e pos-y. A prévia reage na hora.
4. Arraste o **quadro** para percorrer a sequência e conferir se o enquadramento aguenta
   a peça crescendo. Ele abre no último quadro de propósito.
5. **Gerar timelapse** joga na fila e devolve a tela. Dá para ajustar a próxima enquanto
   a primeira renderiza.

**Salvar enquadramento** grava um `enquadramento.json` na pasta da peça, e ele é
recarregado da próxima vez.

A fila roda enquanto a janela do Terminal estiver aberta. Fechou, parou.

## Por que a prévia é instantânea

O cache guarda o **quadro inteiro já girado**, reduzido, mais um manifesto com as
dimensões da fonte. O recorte acontece no navegador, por CSS — não há ida e volta ao
servidor a cada ajuste de slider.

A conta do recorte em `web/app.js` espelha a de `video_filter` em `timelapse/cli.py`.
Se uma mudar, a outra precisa mudar junto; os testes em `tests/test_recorte.py` fixam
o comportamento da CLI justamente para essa mudança não passar batida.

## A linha de comando

O `timelapse/cli.py` funciona sozinho, sem o painel:

```bash
python3 -m timelapse.cli "/caminho/das/fotos" --resolucao 1080x1920 --zoom 1.3 --pos-x -25
```

`--previa` gera só um PNG do quadro escolhido; `--conferir` lista a sequência sem
renderizar nada. `docs-cli.md` tem a referência completa dos parâmetros.

Uma coisa que ela faz e vale saber: **`--girar auto` respeita a etiqueta EXIF**. Fotos
tiradas com a câmera montada em retrato entram em pé, e o zoom e a posição passam a
valer sobre o quadro já girado.

## Instalação

Precisa de Python 3.11+ e FFmpeg. Nenhum pacote de `pip`.

```bash
make setup    # diz onde achou o FFmpeg, ou o que fazer se não achou
```

O FFmpeg é procurado em `bin/ffmpeg`, no Homebrew e no `PATH`, nessa ordem. O binário
local não vai para o repositório — são 49 MB. Em outra máquina:

```bash
brew install ffmpeg
```

Chamadas com `-fps_mode` só existem no FFmpeg 5+; em versões anteriores o projeto usa
`-vsync` automaticamente.

## Configuração

`painel.json` na raiz:

| Campo | O que é |
|---|---|
| `acervo` | pasta raiz onde estão os projetos, um por peça |
| `porta` | porta do servidor local |
| `limite_cache` | quantos quadros o cache guarda por sequência |
| `largura_cache` | largura, em pixels, de cada quadro do cache |

`TIMELAPSE_ACERVO` e `TIMELAPSE_PORTA` sobrescrevem sem editar o arquivo.

O acervo é lido esperando uma pasta por projeto, com as fotos em `fotos/` ou
`fotos-<variante>/` e os vídeos em `render/`:

```
00_Em_Camadas/
├── 18_caveiras/
│   ├── fotos-branca/
│   ├── fotos-vermelha/
│   └── render/
└── 20_ovo/
    ├── fotos/
    └── render/
```

Fotos soltas na raiz do projeto também são reconhecidas.

## Desenvolvimento

```bash
make test     # pytest
make lint     # ruff
make clean    # apaga o cache de prévia
```

## Licença

MIT.
