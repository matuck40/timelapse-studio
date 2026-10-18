# Correção de cor e estabilização por frame de referência

Especificação fechada com o Lucca em 03/out/2026. Todas as decisões abaixo já foram tomadas; não reabrir sem perguntar.

## Problema

1. **Luz:** a luz ambiente muda durante a impressão e trechos do timelapse ficam mais escuros ou azulados.
2. **Câmera:** a câmera às vezes leva um esbarrão (salto de posição, depois fica parada) ou treme continuamente (tripé/mesa vibrando). O enquadramento muda no meio do vídeo.

Solução: o Lucca navega pela prévia, escolhe **um frame de referência** e o app (a) corrige a cor e (b) alinha os demais frames para ficarem o mais parecidos possível com ele.

## Decisões

### Correção de cor
| # | Decisão |
|---|---|
| Q1 | Corrige **brilho e cor**: ganho independente por canal R, G, B (equivale a exposição + balanço de branco). Global no frame, sem correção por região. |
| Q2 | A medição é feita num **retângulo de área parada** desenhado pelo Lucca no painel (mesa, parede, lateral da impressora). Mede só ali e aplica a correção no frame inteiro. Motivo: a peça cresce e muda a cor média da cena. |
| Q3 | **Uma** referência para o vídeo todo. |
| Q7 | Frame com medição fora da curva (mão, bico ou sombra na região) usa a correção dos vizinhos. |
| Q8 | Suavização temporal leve e fixa (média centrada de ~5 frames), aplicada depois da rejeição de outliers. Sem controle no painel. |
| Q9 | Ganho limitado (máximo ~2× de brilho) para não estourar ruído. Frames muito escuros podem ficar um pouco mais escuros que a referência. |
| Q10 | Sempre 100%, sem slider de intensidade. |

### Estabilização
| # | Decisão |
|---|---|
| Q13 | Trata **salto** (esbarrão) **e tremor contínuo**. Os dois se resolvem alinhando cada frame à referência fixa, não ao frame anterior. |
| Q14 | Corrige **deslizamento + giro** (transformação euclidiana, escala fixa = 1). Sem zoom ou perspectiva. |
| Q15 | Usa o **mesmo frame de referência** da cor. |
| Q16 | Mede num **segundo retângulo**, separado do da cor, numa área parada e com textura. Bico, mesa (eixo Y na A1) e peça se movem e não servem de guia. |
| Q17 | Bordas: **zoom automático** só o suficiente para esconder a maior borda do vídeo, somado ao zoom e ao corte que o Lucca já define no painel. |
| Q18 | Frame que falha no alinhamento (escuro, mão na frente) usa o deslocamento interpolado dos vizinhos e fica **marcado no slider** do painel. |
| Q21 | Alinhamento **exato** frame a frame, sem suavização. Suavizar deixaria passar parte do tremor. Só os frames que falham usam os vizinhos. |
| Q22 | Borrão de movimento dentro da foto não é recuperável. Fora de escopo. |

### Geral
| # | Decisão |
|---|---|
| Q4 | Aplicado **no render**. As fotos originais ficam intactas, nada é duplicado no HD. As escolhas ficam salvas no `enquadramento.json` da sequência. |
| Q5/Q23 | Painel com um único botão **antes/depois**, navegando pelo slider com a prévia já corrigida (cor + estabilização). |
| Q6/Q19 | Novas dependências aceitas: **numpy, Pillow, opencv-python** (declarar em `pyproject.toml`, hoje `dependencies = []`). |
| Q11 | Aplicar a correção já no **tamanho necessário para o vídeo final**, não em 6000×4000. |
| Q12/Q20 | Dois liga/desliga **independentes**: `corrigir_cor` e `estabilizar`. No painel, ficam ligados automaticamente quando a sequência tem referência e região salvas, com botão para remover. Na CLI, os dois vêm **desligados por padrão**, para não mudar renders antigos. |

## Estado atual do código (levantado em 03/out/2026)

- Python stdlib puro + JS vanilla. Não existe processamento de cor nem de estabilização.
- **CLI:** `timelapse/cli.py`
  - `DEFAULTS` na linha ~67. Chaves desconhecidas são rejeitadas nas linhas ~92-94, então os novos parâmetros têm que entrar ali.
  - `video_filter()` nas linhas ~253-279: transpose (rotação EXIF 270 nas fotos reais) → crop de zoom → scale+pad ou scale+crop → setsar.
  - Comando ffmpeg nas linhas ~348-354. As fotos entram por symlink num diretório temporário (`%08d.ext`, image2).
- **Prévia:** `timelapse/cache.py:construir()`. Até 300 frames amostrados, lado maior de 1050 px, gravados **sem rotação** em `.cache-previa/<sha1[:16]>/q_%06d.jpg`, com `manifesto.json`.
- **Painel:** `timelapse/servidor.py` (http.server, porta 8765). Endpoints `/api/enquadramento` (GET/POST) gravam o `enquadramento.json` na pasta das fotos (linhas ~47 e ~160).
  - `web/index.html:47` tem o slider `#quadro-atual`. `web/app.js:292` `trocarQuadro()` troca o frame.
  - `web/app.js` `desenhar()` (linhas ~55-105) faz rotação, zoom e corte em CSS, espelhando a conta do ffmpeg.
- **Fila:** `timelapse/fila.py:443` converte cada parâmetro em `--flag` da CLI.
- **Testes:** `tests/test_recorte.py` fixa `video_filter` para bater com o JS. Continua passando.
- **Dados reais:** JPG 6000×4000, EXIF rotação 270, sequências de ~290 a 455 fotos (gaveta-underdesk, ovo, caveiras), no HD externo "Workflow".
- O Mac usa o `python3` do sistema (3.14, segundo o pycache). Confirmar que `opencv-python` tem wheel para essa versão; se não tiver, criar uma venv com 3.12/3.13 e ajustar `scripts/iniciar-painel.sh` e os atalhos.

## Desenho sugerido (o implementador pode ajustar o *como*, não o *o quê*)

### Dados no `enquadramento.json`
```json
{
  "referencia": "IMG_1234.JPG",
  "regiao_cor": [x, y, w, h],
  "regiao_alinhamento": [x, y, w, h],
  "corrigir_cor": true,
  "estabilizar": true
}
```
- Referência pelo **nome do arquivo**, não pelo índice do cache, que muda se o cache for refeito.
- Regiões em coordenadas **normalizadas (0-1) da foto original, antes da rotação**, igual ao que o cache guarda. O painel converte do sistema rotacionado da tela.

### Pipeline (módulo novo, ex.: `timelapse/correcao.py`)
1. **Análise** em resolução reduzida, por exemplo lado maior de ~1500 px, com rotação EXIF aplicada de forma consistente:
   - **Alinhamento primeiro.** Em escala de cinza, dentro de `regiao_alinhamento`, estimar a transformação euclidiana do frame para a referência.
     - Chute inicial robusto a saltos grandes: ORB + `cv2.estimateAffinePartial2D` (RANSAC), forçando escala = 1.
     - Refinamento: `cv2.findTransformECC` com `MOTION_EUCLIDEAN` e máscara da região.
     - Falha quando há poucos inliers ou a correlação ECC fica abaixo de um limiar. Nesse caso, interpolar entre os vizinhos válidos e marcar o frame (Q18).
     - Sem suavização (Q21).
   - **Cor depois.** Com o frame já alinhado, medir a média por canal dentro de `regiao_cor`, em luz linear (sRGB → linear).
     - Ganho por canal = ref / frame.
     - Outliers: mediana móvel e rejeição de desvio grande, substituído pelos vizinhos (Q7).
     - Média móvel centrada de 5 (Q8).
     - Limitar o ganho de luminância a ≤ 2× (Q9), preservando a proporção entre canais.
   - Guardar os parâmetros por frame num JSON de cache (chave = referência + regiões + lista de fotos), para não recalcular entre prévia e render.
2. **Borda (Q17):** a partir de todos os deslocamentos e giros, calcular o menor zoom extra que esconde a borda em todos os frames. Combinar esse zoom com o zoom/corte do usuário. Se essa conta passar pelo `video_filter()`, atualizar o espelho JS e o `test_recorte.py`.
3. **Render:** quando `corrigir_cor` ou `estabilizar` estiver ligado, o Python decodifica cada foto, aplica a transformação e os ganhos na resolução necessária para a saída (Q11) e envia o resultado ao ffmpeg por pipe (`-f rawvideo`, stdin), sem gravar arquivos intermediários. Com os dois desligados, o caminho atual (symlink + image2) fica **intocado**.
   - "Resolução necessária" = tamanho de saída ÷ fração do corte. Considerar o zoom do usuário para não perder nitidez.
   - Manter o progresso que `fila.py` lê (`frame=`).

### Painel
- Botão "Usar este frame como referência" no frame atual do slider.
- Duas ferramentas de retângulo sobre a prévia: "Área para cor" (lisa, neutra) e "Área para alinhar" (com textura). Cores diferentes.
- Endpoint novo que gera a prévia corrigida a partir dos JPGs do cache (rápido, até 300 frames) em `.cache-previa/<id>/corrigido/`, com progresso, como o `/api/cache`.
- Botão antes/depois que troca entre `q_*.jpg` e `corrigido/q_*.jpg`.
- Marcas no slider nos frames em que o alinhamento falhou.
- Botões "remover correção de cor" e "remover estabilização".

### CLI
- `--corrigir-cor`, `--estabilizar` (default desligados), `--referencia <arquivo>`, `--regiao-cor x,y,w,h`, `--regiao-alinhamento x,y,w,h`. Registrar em `DEFAULTS`.
- `fila.py` passa esses parâmetros a partir do `enquadramento.json`.

### Testes (sintéticos, sem depender do HD)
- Imagem com textura deslocada e girada de valores conhecidos: o alinhamento recupera a transformação dentro de uma tolerância.
- Frame com ganho RGB conhecido: a correção recupera o ganho. Ganho acima do limite fica travado em 2×.
- Sequência com um frame "mão na frente": o outlier é substituído pelos vizinhos, tanto na cor quanto no alinhamento.
- Com os dois desligados, o comando ffmpeg gerado é idêntico ao atual.
- `tests/test_recorte.py` continua passando.

### Validação manual com o Lucca
Rodar numa sequência real do HD Workflow que tenha mudança de luz, e numa com esbarrão (se não houver, simular deslocando a câmera no meio de uma captura). Conferir o antes/depois no painel e o MP4 final.

## Adendo (03/out/2026): destino do render por peça

O reel passa a juntar o timelapse com clipes do iPhone, com **uma subpasta por peça** em `Em camadas 3D/02_Marketing_Conteudo/_brutos/<peça>/`. Consumidor: skill `montar-reel-em-camadas`.

- O painel ganha um campo **"Peça"**: texto curto, normalizado para nome de pasta (minúsculas, hífen, sem acento), com sugestões das subpastas que já existem em `_brutos/`.
- Com "Peça" preenchido, o render vai para `_brutos/<peça>/timelapse_<AAAA-MM-DD>.mp4` (cria a subpasta se faltar). Sem "Peça", mantém o destino atual.
- O caminho de `_brutos/` vai no `painel.json` (chave nova, ex.: `pasta_brutos`), editável no painel como a raiz do acervo. Nada de caminho fixo no código.
- O valor de "Peça" fica salvo no `enquadramento.json` da sequência.

## Adendo 2 (04/out/2026): subpastas por tipo dentro da peça

A pasta de cada peça agora tem subpastas por tipo: `roteiro.md`, `timelapse/`, `clipes/`, `fotos/`, `narracao/`. Substitui o destino do Adendo 1:

- Com "Peça" preenchido, o render vai para `<pasta_brutos>/<peça>/timelapse/timelapse_<AAAA-MM-DD>.mp4` (criar `<peça>/` e `timelapse/` se faltarem; se já existir arquivo com o mesmo nome, acrescentar `_2`, `_3`).
- As sugestões do campo "Peça" listam as subpastas de `<pasta_brutos>` (ignorar as que começam com `_` ou `.`).
- O nome da peça segue a mesma regra do atalho do iPhone: minúsculas, sem acento, espaços viram hífen.
