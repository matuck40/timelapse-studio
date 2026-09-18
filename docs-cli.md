# Fotos → timelapse

## No seu Mac

1. Mantenha esta pasta inteira junta (atalho, script e pasta `bin`).
2. Dê dois cliques em **Gerar timelapse.command** e escolha a pasta de UMA impressão.
3. Espere a mensagem **Pronto!**. O MP4 e um relatório da ordem das fotos ficam na pasta escolhida.
4. Importe o MP4 no CapCut para editar.

O atalho usa o Python 3 já disponível neste Mac. O FFmpeg incluído é para Mac com Apple Silicon. Em outro sistema, use Python 3 e uma versão do FFmpeg compatível disponível no PATH, removendo o binário local incompatível.

## O que é gerado com a configuração padrão

- MP4 H.264 de alta qualidade (CRF 16), sem áudio, a 30 quadros por segundo.
- Cada foto corresponde a um quadro: 900 fotos = 30 segundos; 1.800 = 60 segundos.
- Mantém a resolução e a proporção da sequência; se uma dimensão for ímpar, acrescenta um pixel de borda para compatibilidade. Não faz corte vertical nem amplia para 4K.
- Nenhuma foto original é alterada. Cada execução cria um nome novo.
- CSV acompanha o vídeo para consultar qual foto aparece em cada momento.

Use uma sequência de JPG/JPEG **ou** PNG, com a mesma resolução e orientação, diretamente na pasta selecionada. Arquivos ocultos e outros formatos são ignorados; subpastas não entram. Fotos RAW/HEIC precisam ser exportadas antes. JPG e PNG misturados são recusados. Não acrescente/remova fotos enquanto o vídeo é gerado.

A ordem padrão é o nome com números em ordem natural: foto2 vem antes de foto10. Isso funciona para nomes sequenciais da câmera; se a numeração reiniciou ou misturou sessões, organize os nomes antes. O programa mostra a primeira e última foto. O CSV permite conferir a sequência completa.

## Parâmetros salvos: config.json

Edite `config.json` e salve. Use **Ver prévia.command** para conferir o primeiro quadro como imagem, ou **Gerar timelapse.command** para gerar o vídeo. Ele carrega esse arquivo automaticamente. Não é necessário alterar o código. JSON usa ponto para decimais, `null` para vazio e `true`/`false` para sim/não.

| Parâmetro | Padrão | Significado |
|---|---|---|
| `resolucao` | `"original"` | Ou dimensões pares: `"1080x1920"` vertical, `"1920x1080"` horizontal, `"2160x3840"` vertical 4K. Ampliar não recupera detalhes. |
| `enquadramento` | `"ajustar"` | `ajustar` preserva a área selecionada com bordas pretas; `preencher` ocupa toda a saída, cortando o excedente. |
| `zoom` | `1.0` | De 1 a 20. 1.5 aproxima 50%; 2 usa metade da largura e altura da foto. |
| `pos_x` | `0.0` | -100 seleciona a esquerda; 0 o centro; 100 a direita da área disponível para corte. |
| `pos_y` | `0.0` | -100 seleciona o topo; 0 o centro; 100 a base da área disponível para corte. |
| `pasta_saida` | `null` | Salva junto das fotos. Ou use um caminho absoluto entre aspas. |
| `nome_saida` | `"timelapse_{data}.mp4"` | `{data}` vira data/hora única. Um nome fixo é permitido, mas nunca é sobrescrito. |
| `fps` | `30` | 24, 25, 30 ou 60 quadros por segundo. |
| `duracao` | `null` | Duração desejada em segundos, por exemplo 20. Arredondada ao quadro mais próximo. |
| `velocidade` | `1.0` | 2 = duas vezes mais rápido; 0.5 = metade da velocidade. Alternativa à duração. |
| `inicio` / `fim` | `1` / `null` | Primeira e última foto, inclusive, depois da ordenação; null usa até o final. |
| `passo` | `1` | 2 seleciona uma a cada duas fotos. |
| `inverter` | `false` | true reproduz a seleção de trás para frente. |
| `ordem` | `"nome"` | `nome` numérico ou `data` de modificação, não EXIF. |
| `girar` | `"auto"` | Giro aplicado antes de qualquer corte. `auto` lê a etiqueta EXIF de orientação; `nao` mantém os pixels como estão; `90`, `180`, `270` forçam o giro. |
| `qualidade` | `16` | CRF entre 0 e 51: menor significa mais qualidade e arquivo maior. |
| `preset` | `"medium"` | `fast` exporta mais rápido; `slow` tende a comprimir melhor. |

Zoom e posição são fixos durante todo o vídeo. Não são animações ou keyframes. X/Y definem **qual região da foto fica visível**, não um deslocamento em pixels. Sem zoom nem corte, não há margem para deslocar. O zoom recorta primeiro; a resolução/enquadramento ajusta esse recorte ao tamanho final. As mesmas posições também controlam o corte adicional no modo preencher. Com `girar` em `auto`, a etiqueta EXIF de orientação é respeitada: fotos tiradas com a câmera em retrato entram em pé, e o zoom, a posição e a resolução passam a valer sobre o quadro já girado. Use `girar` igual a `nao` para o comportamento anterior, de usar os pixels como estão. Uma seleção que misture orientações diferentes é recusada; separe as sequências ou informe um giro fixo.

Com duração null, velocidade 1 e passo 1, todas as fotos selecionadas são preservadas, uma por quadro. Duração ou velocidade diferentes podem descartar ou repetir fotos; não há interpolação. Para trabalhar depois no CapCut com máxima liberdade, mantenha os padrões de tempo. Não use duração definida e velocidade diferente de 1 juntas no JSON.

## Pela linha de comando

No Terminal, digite `python3 `, arraste `timelapse.py`, digite um espaço e arraste a pasta das fotos. Acrescente as opções desejadas. Elas têm prioridade sobre o JSON:

```text
--resolucao 1080x1920 --enquadramento preencher --zoom 1.5 --pos-x 20 --pos-y -30
```

Para escolher o destino:

```text
--pasta-saida "/caminho/dos/videos" --nome-saida "impressao_{data}.mp4"
```

Ou `--saida "/caminho/dos/videos/peca.mp4"` para um caminho completo (prioridade sobre pasta/nome).

**Confira antes de renderizar:** acrescente `--previa` para gerar uma imagem PNG do primeiro quadro selecionado com zoom, posição e resolução aplicados. Usa o mesmo destino do MP4, trocando a extensão por `.previa.png`. Não gera vídeo nem CSV. Use `--inicio` para visualizar outro momento da sequência. Retire `--previa` para exportar o vídeo.

Outras opções:

- `--duracao 20` ou `--velocidade 2`: tempo final ou multiplicador. Uma opção explícita substitui a alternativa salva no JSON.
- `--inicio 100 --fim 900 --passo 2`: seleciona a faixa e usa uma a cada duas fotos.
- `--inverter` / `--no-inverter`: ativa/desativa sequência reversa.
- `--girar auto|nao|90|180|270`: giro antes do corte. Padrão `auto`, pela etiqueta EXIF.
- `--conferir`: apenas lista a sequência final e duração; não renderiza.
- `--config "/caminho/preset.json"`: usa outro arquivo JSON.
- `--sem-config`: ignora o JSON e parte dos padrões originais.
- `--help`: mostra todas as opções.

## Edição e começo do Reels

Guarde este MP4 como vídeo-base. No CapCut, as curvas de velocidade permitem acelerar partes repetitivas e dar mais tempo às transformações interessantes. Uma exportação com todas as fotos preserva suas opções. Desacelerar muito pode revelar saltos, pois não existem fotos dos momentos intermediários; interpolação pode criar deformações.

Sugestão criativa para testar, sem promessa de retenção:

- **0–1 segundo:** um movimento ou transformação visual forte do próprio timelapse.
- **1–3 segundos:** continue esse trecho até criar curiosidade; texto curto, se fizer sentido, como “Olha o que isso vai virar”.
- **Depois:** volte ao início da impressão, acelere etapas repetitivas e dê mais tempo aos detalhes que surgem.
- **Final:** mostre a peça concluída. Em uma edição futura, um take real do produto pode servir também de abertura.

A escolha do trecho inicial depende das imagens. Esta primeira versão gera a sequência cronológica completa; a seleção do gancho fica para a edição.

## Referências

- [Sequências de imagens no FFmpeg](https://ffmpeg.org/ffmpeg.html)
- [Curvas de velocidade no CapCut](https://www.capcut.com/resource/how-to-do-velocity-on-capcut)
- [Distribuição do FFmpeg via imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)

O executável FFmpeg é distribuído com os avisos e licenças do pacote em `bin/licencas`. O script e o atalho são independentes do CapCut e não precisam de assinatura ou serviço online para gerar o vídeo.
