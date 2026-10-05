# Correção de cor e estabilização — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O Lucca escolhe um quadro de referência e duas áreas na prévia; o render iguala a cor e alinha cada foto a esse quadro, sem tocar nas fotos originais.

**Architecture:** Um módulo novo, `timelapse/correcao.py` (numpy + OpenCV + Pillow), analisa a sequência inteira **na foto crua, sem giro**: alinhamento euclidiano (ORB + ECC) primeiro, cor (ganho por canal em luz linear) depois. A análise fica num JSON de cache, compartilhado entre painel e render. No render, com alguma correção ligada, o Python decodifica cada foto já reduzida, aplica alinhamento + zoom de borda + ganho e manda os pixels ao ffmpeg por pipe (`rawvideo`). O `video_filter()` continua cuidando do giro, do zoom e do corte, sem mudança na conta, e por isso o espelho em JS e o `test_recorte.py` não mudam. Com as duas correções desligadas, o caminho antigo (symlink + image2) fica byte a byte igual.

**Tech Stack:** Python 3.12 numa `.venv` (numpy, Pillow, opencv-python), ffmpeg (`bin/ffmpeg`), http.server, JS vanilla, pytest, Node só para testar `web/regioes.js`.

**Spec:** `docs/correcao-estabilizacao.md` (decisões Q1–Q23, fechadas com o Lucca em 03/out/2026: não reabrir sem perguntar), incluindo o **Adendo: destino do render por peça** (Task 9).

## Global Constraints

- Dependências novas: só `numpy`, `Pillow`, `opencv-python`, declaradas em `pyproject.toml` (Q6/Q19). `pytest` e `ruff` como extras `dev`.
- Fotos originais intactas, nada gravado no HD além do `enquadramento.json` da sequência (Q4). Análise e prévia corrigida ficam em `.cache-previa/` no projeto.
- CLI: `corrigir_cor` e `estabilizar` **desligados por padrão**. Desligados, o comando ffmpeg é idêntico ao de hoje (Q12/Q20).
- Referência pelo **nome do arquivo**. Regiões `[x, y, w, h]` **normalizadas 0–1 na foto crua, antes do giro** (desenho da spec).
- Cor: ganho por canal R, G, B, global no frame (Q1); mede só na `regiao_cor` (Q2); uma referência (Q3); outlier usa vizinhos (Q7); média centrada de 5, fixa (Q8); brilho ≤ 2× com proporção entre canais preservada (Q9); sempre 100%, sem slider (Q10).
- Estabilização: euclidiana, escala = 1 (Q14); alinha à referência fixa, sem suavização (Q13/Q21); mede só na `regiao_alinhamento` (Q16); falha interpola os vizinhos e marca no slider (Q18); zoom automático mínimo para esconder a borda (Q17).
- Correção feita no tamanho que a saída precisa, nunca em 6000×4000 sem necessidade (Q11).
- Painel: as duas correções ligam sozinhas quando há referência + região, cada uma com botão de remover (Q12); um botão antes/depois (Q5/Q23).
- Adendos 1 e 2: campo **Peça** com a regra do atalho do iPhone (minúsculas, sem acento, espaços viram hífen), com sugestões das subpastas de `_brutos/` (sem as que começam com `_` ou `.`); `pasta_brutos` no `painel.json`, editável no painel, aceitando symlink (nada de `is_symlink`/`lstat` para recusar); com Peça, o render vai para `<pasta_brutos>/<peça>/timelapse/timelapse_<AAAA-MM-DD>.mp4`, criando `<peça>/` e `timelapse/`, com `_2`, `_3` se o nome existir; sem Peça, o destino atual; Peça salva no `enquadramento.json`; nada de caminho fixo no código.
- Mensagens para o Lucca em português com acento; comentários de código seguem o estilo do repo (português, sem acento).
- Arquivos novos passam em `ruff check`. Os 34 erros de ruff que já existem no repo **não** são corrigidos neste trabalho.

## Review Focus

1. **Região desenhada na prévia girada (EXIF 270, o caso real)** → precisa cair no mesmo lugar físico da foto crua; um erro aqui mede a cor na peça ou alinha pela mesa. Teste: `tests/test_regioes_js.py` (Task 8).
2. **Render com seleção parcial, ordem invertida, duração que repete fotos, `--previa`, e referência fora do trecho escolhido** → precisa renderizar, e cada quadro usa a correção da própria foto. Teste: `test_render_corrigido_respeita_selecao` (Task 6).
3. **Foto nova na pasta depois da análise (captura ainda rodando)** → a análise é refeita, sem `KeyError` no render. Teste: `test_foto_nova_na_pasta_refaz_a_analise` (Task 4).
4. **Cache da prévia remontado depois da correção** → a prévia corrigida antiga não pode aparecer em cima de quadros novos. Teste: `test_previa_corrigida_de_cache_antigo_e_ignorada` (Task 7).
5. **A luz muda junto com o esbarrão** → o alinhamento roda antes da cor e não pode depender do brilho. Teste: `test_alinhar_aguenta_mudanca_de_luz` (Task 3).

---

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `pyproject.toml` | dependências, build-system, extras dev |
| `Makefile` | `setup` cria `.venv`; alvos usam a venv quando existe |
| `scripts/iniciar-painel.sh` | sobe o painel com `.venv/bin/python` se existir |
| `timelapse/cache.py` | `TIMELAPSE_CACHE` (testes); `apagar()` com `rmtree` |
| `timelapse/correcao.py` | **novo**: cor, alinhamento, análise, prévia corrigida |
| `timelapse/cli.py` | novos parâmetros; `comando_ffmpeg()` extraído; render por pipe |
| `timelapse/fila.py` | `comando_cli()` extraído; regiões viram `x,y,w,h` |
| `timelapse/servidor.py` | `/api/fotos`, `/api/correcao`, `/api/enquadramento/correcao`, `/q/<id>/corrigido/` |
| `web/regioes.js` | **novo**: conversão de regiões tela girada ↔ foto crua |
| `web/index.html`, `web/app.js`, `web/estilo.css` | ferramentas de correção, antes/depois, marcas |
| `tests/sinteticos.py` | **novo**: imagens de teste geradas por código |
| `tests/test_correcao_cor.py`, `test_correcao_alinhamento.py`, `test_correcao_analise.py`, `test_cli_correcao.py`, `test_fila.py`, `test_servidor_correcao.py`, `test_regioes_js.py` | **novos** |
| `web/peca.js` | **novo**: normaliza o campo Peça para nome de pasta |
| `timelapse/acervo.py` | `subpastas()` para as sugestões de `_brutos/` |
| `tests/test_destino.py`, `tests/test_peca_js.py` | **novos** (Task 9) |
| `README.md`, `docs-cli.md` | instalação e uso |

**Como o código foi validado antes deste plano:** todo o Python e o JS abaixo rodaram num protótipo isolado (cópia do repo no scratchpad), com Python 3.12.12, numpy 2.5.3, OpenCV 5.0.0 e Pillow 12.3.0: 48 testes passando, ruff limpo nos arquivos novos, `node --check` ok. Com tudo desligado, o comando ffmpeg capturado do código atual e do novo é idêntico. Desempenho medido em JPG 6000×4000: análise ~0,09 s/foto (455 fotos ≈ 40 s, só na primeira vez), preparo do render ~0,024 s/foto.

---

### Task 1: Ambiente com numpy, Pillow e OpenCV

Hoje nenhum Python do Mac tem essas bibliotecas. O painel sobe com `/usr/local/bin/python3` (3.14, pelo PATH fixo do `scripts/iniciar-painel.sh`), e o `python3` do terminal é o pyenv 3.12.12. Nenhum dos dois tem numpy, e nem pytest. Uma `.venv` (já no `.gitignore`) isola tudo. A `fila.py` chama a CLI com `sys.executable`, então o render herda a venv do painel sem mudança.

**Files:**
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `scripts/iniciar-painel.sh:24-28`
- Modify: `timelapse/cache.py:7-23` e `:143-148`
- Modify: `README.md:4` e `:69`

**Interfaces:**
- Produces: `.venv/bin/python` com `numpy`, `cv2`, `PIL`, `pytest`, `ruff`; `cache.RAIZ_CACHE` respeita a variável de ambiente `TIMELAPSE_CACHE`; `cache.apagar()` apaga subpastas.

- [ ] **Step 1: Declarar as dependências em `pyproject.toml`**

Substitua o arquivo inteiro por:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "timelapse-studio"
version = "0.1.0"
description = "Painel local para montar timelapses de impressao 3D a partir de sequencias de fotos"
requires-python = ">=3.11"
dependencies = [
    "numpy>=2.0",
    "Pillow>=10.0",
    "opencv-python>=4.9",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff"]

[project.scripts]
timelapse = "timelapse.cli:cli"

[tool.setuptools]
packages = ["timelapse"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`[tool.setuptools] packages` é obrigatório: sem ele, o `pip install -e .` tenta adivinhar os pacotes, encontra `web/`, `tests/`, `bin/` e `scripts/` na raiz e falha.

- [ ] **Step 2: `Makefile` usa a venv**

Substitua o arquivo inteiro por (as linhas de comando começam com **TAB**):

```make
.PHONY: painel iniciar parar setup test lint clean

# A .venv tem numpy, Pillow e OpenCV, usados pela correcao de cor e estabilizacao.
# Sem ela o painel e a CLI ainda rodam, so que sem a correcao.
PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

painel:  ## Sobe o painel em primeiro plano (Ctrl+C para parar)
	$(PY) -m timelapse.servidor

iniciar:  ## Sobe o painel em segundo plano e abre o navegador
	./scripts/iniciar-painel.sh && open http://localhost:8765

parar:  ## Para o painel e a fila
	./scripts/parar-painel.sh

setup:  ## Cria a .venv com as dependencias e localiza o ffmpeg
	test -x .venv/bin/python || python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
	.venv/bin/python -m timelapse.ambiente

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check . && $(PY) -m ruff format --check .

clean:  ## Apaga o cache de previa
	rm -rf .cache-previa
```

- [ ] **Step 3: O painel sobe com a venv**

Em `scripts/iniciar-painel.sh`, troque:

```zsh
PYTHON="$(command -v python3)"
if [[ -z "$PYTHON" ]]; then
  print -u2 -r -- "Python 3 não encontrado neste Mac."
  exit 1
fi
```

por:

```zsh
# A .venv (make setup) tem numpy, Pillow e OpenCV, que a correcao usa.
PYTHON="$PROJECT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi
if [[ -z "$PYTHON" ]]; then
  print -u2 -r -- "Python 3 não encontrado neste Mac."
  exit 1
fi
```

`parar-painel.sh` confere `*timelapse.servidor*` na linha de comando do processo, o que continua valendo.

- [ ] **Step 4: Cache configurável nos testes e `apagar()` com subpastas**

Em `timelapse/cache.py`, nos imports, troque `import os\nimport subprocess` por:

```python
import os
import shutil
import subprocess
```

Troque `RAIZ_CACHE = ambiente.RAIZ / ".cache-previa"` por:

```python
# TIMELAPSE_CACHE deixa os testes usarem uma pasta temporaria.
RAIZ_CACHE = Path(os.environ.get("TIMELAPSE_CACHE") or ambiente.RAIZ / ".cache-previa")
```

Troque a função `apagar` inteira por:

```python
def apagar(pasta: Path) -> None:
    # rmtree: a pasta pode ter a subpasta corrigido/ da previa corrigida
    destino = pasta_cache(pasta)
    if destino.is_dir():
        shutil.rmtree(destino)
```

(O `os` continua sendo usado por `os.environ`.)

- [ ] **Step 5: README de instalação**

Em `README.md`, linha 4, troque `da câmera. Roda na própria máquina, sem serviço externo e sem dependência de `pip`.` por `da câmera. Roda na própria máquina, sem serviço externo.`

Na seção `## Instalação`, troque:

````markdown
Precisa de Python 3.11+ e FFmpeg. Nenhum pacote de `pip`.

```bash
make setup    # diz onde achou o FFmpeg, ou o que fazer se não achou
```
````

por:

````markdown
Precisa de Python 3.11+ e FFmpeg. A correção de cor e a estabilização usam numpy,
Pillow e OpenCV, instalados numa `.venv` dentro do projeto:

```bash
make setup    # cria a .venv, instala as dependências e diz onde achou o FFmpeg
```

O atalho Iniciar Painel e o `make` usam a `.venv` quando ela existe. Sem ela, tudo
funciona menos a correção.
````

- [ ] **Step 6: Criar a venv e rodar os testes existentes**

Run: `make setup && make test`
Expected: o pip instala numpy, opencv-python, Pillow, pytest, ruff; `timelapse.ambiente` mostra o ffmpeg; `5 passed` (os testes de `tests/test_recorte.py`).

Run: `.venv/bin/python -c "import numpy, cv2, PIL; print(numpy.__version__, cv2.__version__, PIL.__version__)"`
Expected: três versões impressas, sem erro.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml Makefile scripts/iniciar-painel.sh timelapse/cache.py README.md
git commit -m "Install numpy, Pillow and OpenCV in a project venv"
```

---

### Task 2: Correção de cor (matemática pura)

**Files:**
- Create: `timelapse/correcao.py`
- Test: `tests/test_correcao_cor.py`

**Interfaces:**
- Produces:
  - `srgb_para_linear(valores) -> np.ndarray` e `linear_para_srgb(valores) -> np.ndarray` (0–255 ↔ 0–1, float64)
  - `recorte(regiao, largura, altura) -> (x0, y0, x1, y1)` em pixels
  - `medir_cor(rgb: uint8 HxWx3, regiao) -> np.ndarray (3,)` média linear
  - `interpolar(valores (N,k), validos bool(N)) -> (N,k)`
  - `fora_da_curva(valores (N,k), validos) -> bool(N)`
  - `suavizar(valores (N,k), janela=5) -> (N,k)`
  - `limitar_ganho(ganhos (N,3), maximo=2.0) -> (N,3)`
  - `ganhos_de_cor(referencia (3,), medidas (N,3)) -> (ganhos (N,3), substituidos bool(N))`
  - `tabela_de_ganho(ganho (3,)) -> uint8 (256,1,3)` LUT para `cv2.LUT`

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/test_correcao_cor.py`:

```python
import cv2
import numpy as np
import pytest

from timelapse import correcao as c


def test_ganho_recupera_balanco_conhecido():
    ref = np.full((3,), 0.4)
    ganho = np.array([0.5, 0.6, 0.8])
    medidas = np.tile(ref * ganho, (9, 1))
    ganhos, _ = c.ganhos_de_cor(ref, medidas)
    assert ganhos[4] == pytest.approx(1 / ganho, rel=1e-6)


def test_ganho_acima_do_teto_fica_em_2x():
    ref = np.full((3,), 0.4)
    medidas = np.tile(ref * 0.3, (9, 1))
    ganhos, _ = c.ganhos_de_cor(ref, medidas)
    assert ganhos[4] == pytest.approx([2.0, 2.0, 2.0])


def test_teto_preserva_a_proporcao_entre_canais():
    travado = c.limitar_ganho(np.array([[4.0, 2.0, 1.0]]))[0]
    assert travado @ c.LUMA == pytest.approx(2.0)
    assert travado[0] / travado[1] == pytest.approx(2.0)


def test_quadro_fora_da_curva_usa_vizinhos():
    ref = np.full((3,), 0.4)
    medidas = np.tile(ref, (9, 1))
    medidas[4] = [0.05, 0.05, 0.05]  # mao na frente
    ganhos, substituidos = c.ganhos_de_cor(ref, medidas)
    assert substituidos.tolist() == [False] * 4 + [True] + [False] * 4
    assert ganhos[4] == pytest.approx([1.0, 1.0, 1.0])


def test_medicao_zerada_conta_como_invalida():
    ref = np.full((3,), 0.4)
    medidas = np.tile(ref, (5, 1))
    medidas[0] = 0  # quadro que nao alinhou chega zerado
    ganhos, substituidos = c.ganhos_de_cor(ref, medidas)
    assert substituidos[0]
    assert ganhos[0] == pytest.approx([1.0, 1.0, 1.0])


def test_lut_aplica_ganho_em_luz_linear():
    rgb = np.full((2, 2, 3), 100, dtype=np.uint8)
    saida = cv2.LUT(rgb, c.tabela_de_ganho([2.0, 1.0, 0.5]))
    esperado = c.linear_para_srgb(c.srgb_para_linear(100) * np.array([2.0, 1.0, 0.5]))
    assert saida[0, 0].tolist() == np.round(esperado).astype(int).tolist()


def test_medir_cor_so_dentro_da_regiao():
    rgb = np.zeros((100, 100, 3), dtype=np.uint8)
    rgb[:50, :50] = 255
    assert c.medir_cor(rgb, [0, 0, 0.5, 0.5]) == pytest.approx([1.0, 1.0, 1.0])
    assert c.medir_cor(rgb, [0.5, 0.5, 0.5, 0.5]) == pytest.approx([0.0, 0.0, 0.0])
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_correcao_cor.py -q`
Expected: FAIL com `ImportError: cannot import name 'correcao' from 'timelapse'`

- [ ] **Step 3: Criar `timelapse/correcao.py` com a parte de cor**

```python
"""Correcao de cor e estabilizacao contra UM quadro de referencia.

Tudo aqui trabalha na foto CRUA, sem giro: e assim que o cache e o ffmpeg
(-noautorotate) enxergam a foto. Regioes chegam normalizadas (0-1) nesse
mesmo sistema. O giro EXIF continua sendo aplicado depois, pelo video_filter.

Convencao do alinhamento: a matriz A (2x3) de um quadro leva um ponto da
REFERENCIA ao ponto correspondente NESTE quadro. Para alinhar, cada pixel u
da saida busca o quadro em A(u): warpAffine com WARP_INVERSE_MAP.
"""
import numpy as np

GANHO_MAXIMO = 2.0  # Q9: teto do ganho de brilho
JANELA_SUAVIZAR = 5  # Q8: media centrada
JANELA_MEDIANA = 7
DESVIO_OUTLIER = 0.12  # em log natural: ~13% fora da mediana dos vizinhos
LUMA = np.array([0.2126, 0.7152, 0.0722])


# ---------- cor ----------

def srgb_para_linear(valores: np.ndarray) -> np.ndarray:
    v = np.asarray(valores, dtype=np.float64) / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def linear_para_srgb(valores: np.ndarray) -> np.ndarray:
    v = np.clip(np.asarray(valores, dtype=np.float64), 0.0, 1.0)
    s = np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)
    return s * 255.0


_LINEAR_DE_BYTE = srgb_para_linear(np.arange(256))


def recorte(regiao, largura: int, altura: int) -> tuple[int, int, int, int]:
    """Regiao normalizada [x, y, w, h] -> fatia em pixels, com pelo menos 1 px."""
    x, y, w, h = regiao
    x0 = min(int(round(x * largura)), largura - 1)
    y0 = min(int(round(y * altura)), altura - 1)
    x1 = max(int(round((x + w) * largura)), x0 + 1)
    y1 = max(int(round((y + h) * altura)), y0 + 1)
    return x0, y0, min(x1, largura), min(y1, altura)


def medir_cor(rgb: np.ndarray, regiao) -> np.ndarray:
    """Media por canal, em luz linear, dentro da regiao."""
    x0, y0, x1, y1 = recorte(regiao, rgb.shape[1], rgb.shape[0])
    trecho = _LINEAR_DE_BYTE[rgb[y0:y1, x0:x1]]
    return trecho.reshape(-1, 3).mean(axis=0)


def interpolar(valores: np.ndarray, validos: np.ndarray) -> np.ndarray:
    """Troca as linhas invalidas pela reta entre os vizinhos validos (Q7, Q18).

    Nas pontas, repete o vizinho valido mais proximo.
    """
    valores = np.asarray(valores, dtype=np.float64)
    validos = np.asarray(validos, dtype=bool)
    if not validos.any():
        raise ValueError("Nenhum quadro válido para servir de vizinho.")
    indices = np.arange(len(valores))
    saida = valores.copy()
    for coluna in range(valores.shape[1]):
        saida[:, coluna] = np.interp(indices, indices[validos], valores[validos, coluna])
    return saida


def fora_da_curva(valores: np.ndarray, validos: np.ndarray,
                  janela: int = JANELA_MEDIANA, limite: float = DESVIO_OUTLIER) -> np.ndarray:
    """Marca linhas que fogem da mediana movel dos vizinhos validos."""
    metade = janela // 2
    fora = np.zeros(len(valores), dtype=bool)
    for i in range(len(valores)):
        if not validos[i]:
            continue
        vizinhos = [j for j in range(max(0, i - metade), min(len(valores), i + metade + 1))
                    if validos[j]]
        mediana = np.median(valores[vizinhos], axis=0)
        fora[i] = np.max(np.abs(valores[i] - mediana)) > limite
    return fora


def suavizar(valores: np.ndarray, janela: int = JANELA_SUAVIZAR) -> np.ndarray:
    """Media movel centrada; nas pontas a janela encolhe."""
    metade = janela // 2
    n = len(valores)
    return np.array([valores[max(0, i - metade):min(n, i + metade + 1)].mean(axis=0)
                     for i in range(n)])


def limitar_ganho(ganhos: np.ndarray, maximo: float = GANHO_MAXIMO) -> np.ndarray:
    """Trava o ganho de brilho em `maximo`, mantendo a proporcao entre canais."""
    ganhos = np.asarray(ganhos, dtype=np.float64)
    brilho = ganhos @ LUMA
    fator = np.where(brilho > maximo, maximo / brilho, 1.0)
    return ganhos * fator[:, None]


def ganhos_de_cor(referencia: np.ndarray, medidas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ganho por quadro e canal = referencia / quadro, ja limpo, suave e limitado.

    Devolve (ganhos N x 3, substituidos N) — substituidos marca os quadros cuja
    medicao foi trocada pela dos vizinhos.
    """
    medidas = np.asarray(medidas, dtype=np.float64)
    validos = np.all(medidas > 1e-4, axis=1)
    log_ganho = np.zeros_like(medidas)
    log_ganho[validos] = np.log(referencia) - np.log(medidas[validos])
    validos &= ~fora_da_curva(log_ganho, validos)
    log_ganho = interpolar(log_ganho, validos)
    ganhos = limitar_ganho(np.exp(suavizar(log_ganho)))
    return ganhos, ~validos


def tabela_de_ganho(ganho) -> np.ndarray:
    """LUT 256 x 1 x 3 (uint8) que aplica o ganho em luz linear, canal a canal."""
    canais = [linear_para_srgb(_LINEAR_DE_BYTE * g) for g in ganho]
    return np.round(np.stack(canais, axis=1)).astype(np.uint8).reshape(256, 1, 3)
```

Por que log: rejeitar outlier e suavizar em log trata "metade da luz" e "o dobro da luz" como desvios do mesmo tamanho. A ordem segue a spec: rejeição (Q7) → suavização (Q8) → teto (Q9).

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/bin/python -m pytest tests/test_correcao_cor.py -q`
Expected: `7 passed`

Run: `.venv/bin/ruff check timelapse/correcao.py tests/test_correcao_cor.py`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add timelapse/correcao.py tests/test_correcao_cor.py
git commit -m "Compute per-channel colour gains against a reference frame"
```

---

### Task 3: Alinhamento, zoom de borda e aplicação

**Files:**
- Modify: `timelapse/correcao.py`
- Create: `tests/sinteticos.py`
- Test: `tests/test_correcao_alinhamento.py`

**Interfaces:**
- Consumes: `recorte`, `tabela_de_ganho` (Task 2)
- Produces:
  - `mascara(regiao, largura, altura) -> uint8 (H,W)` 0/255
  - `euclidiana(theta, tx, ty) -> float64 (2,3)`
  - `alinhar(ref_cinza, quadro_cinza, masc) -> float64 (2,3) | None`: matriz A referência → quadro, nos pixels destas imagens
  - `zoom_borda(matrizes, largura, altura) -> float >= 1`
  - `matriz_de_saida(theta, tx, ty, zoom, largura, altura) -> (2,3)` para `warpAffine(..., WARP_INVERSE_MAP)`
  - `aplicar(rgb, quadro: dict, analise: dict, cor: bool, estabilizar: bool) -> uint8 RGB`, em que `quadro` tem `theta`, `tx`, `ty` (pixels da foto crua) e `ganho`, e `analise` tem `largura_bruta`, `zoom_borda`, `alinhamento`, `cor`
  - `carregar(caminho, largura, altura) -> uint8 RGB` (foto crua, sem giro EXIF, reduzida)
  - `tamanho_reduzido(largura, altura, lado) -> (int, int)`
  - `tests/sinteticos.py`: `textura(largura=600, altura=400, semente=1) -> uint8 (H,W)`

- [ ] **Step 1: Criar o gerador de imagens de teste**

Crie `tests/sinteticos.py`:

```python
"""Imagens de teste geradas por codigo: nada depende do HD Workflow."""
import cv2
import numpy as np


def textura(largura=600, altura=400, semente=1):
    """Ruido suavizado: textura rica, boa para o ORB e o ECC acharem pontos."""
    gerador = np.random.default_rng(semente)
    ruido = gerador.integers(0, 256, (altura // 8, largura // 8), dtype=np.uint8)
    return cv2.resize(ruido, (largura, altura), interpolation=cv2.INTER_CUBIC)
```

(Sem `__init__.py` em `tests/`, o pytest põe a pasta no `sys.path`, e `from sinteticos import textura` funciona.)

- [ ] **Step 2: Escrever os testes que falham**

Crie `tests/test_correcao_alinhamento.py`:

```python
import math

import cv2
import numpy as np
import pytest
from sinteticos import textura

from timelapse import correcao as c


def test_alinhar_recupera_deslize_e_giro():
    ref = textura()
    a = c.euclidiana(math.radians(1.5), 12.0, -7.0)
    quadro = cv2.warpAffine(ref, a, (600, 400))
    achada = c.alinhar(ref, quadro, c.mascara([0.2, 0.2, 0.6, 0.6], 600, 400))
    assert achada is not None
    assert math.degrees(math.atan2(achada[1, 0], achada[0, 0])) == pytest.approx(1.5, abs=0.05)
    assert achada[0, 2] == pytest.approx(12.0, abs=0.3)
    assert achada[1, 2] == pytest.approx(-7.0, abs=0.3)


def test_alinhar_aguenta_salto_grande():
    ref = textura()
    a = c.euclidiana(math.radians(-3), 60.0, 35.0)
    quadro = cv2.warpAffine(ref, a, (600, 400))
    achada = c.alinhar(ref, quadro, c.mascara([0.3, 0.3, 0.4, 0.4], 600, 400))
    assert achada is not None
    assert achada[0, 2] == pytest.approx(60.0, abs=0.5)
    assert achada[1, 2] == pytest.approx(35.0, abs=0.5)


def test_alinhar_falha_com_mao_na_frente():
    ref = textura()
    quadro = ref.copy()
    quadro[60:340, 90:510] = 10
    assert c.alinhar(ref, quadro, c.mascara([0.2, 0.2, 0.6, 0.6], 600, 400)) is None


def test_alinhar_aguenta_mudanca_de_luz():
    # a luz muda junto com o esbarrao: alinhamento vem antes da cor e nao pode depender dela
    ref = textura()
    a = c.euclidiana(math.radians(0.5), 6.0, 4.0)
    quadro = cv2.warpAffine(ref, a, (600, 400)).astype(np.float64) * 0.55 + 10
    ruido = np.random.default_rng(9).normal(0, 4, quadro.shape)
    quadro = np.clip(quadro + ruido, 0, 255).astype(np.uint8)
    achada = c.alinhar(ref, quadro, c.mascara([0.2, 0.2, 0.6, 0.6], 600, 400))
    assert achada is not None
    assert achada[0, 2] == pytest.approx(6.0, abs=0.5)


def test_zoom_borda_esconde_o_maior_deslize():
    a = c.euclidiana(0, 30.0, 0)  # 30 px para a direita num quadro de 600
    z = c.zoom_borda([c.euclidiana(0, 0, 0), a], 600, 400)
    # metade da largura visivel (300/z) + 30 precisa caber em 300
    assert z == pytest.approx(300 / 270, rel=1e-4)


def test_sem_movimento_nao_tem_zoom():
    assert c.zoom_borda([c.euclidiana(0, 0, 0)] * 3, 600, 400) == 1.0


def test_matriz_de_saida_desfaz_o_deslize():
    ref = textura()
    a = c.euclidiana(math.radians(1.0), 8.0, -5.0)
    quadro = cv2.warpAffine(ref, a, (600, 400))
    m = c.matriz_de_saida(math.radians(1.0), 8.0, -5.0, 1.0, 600, 400)
    alinhado = cv2.warpAffine(quadro, m, (600, 400), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    miolo = (slice(100, 300), slice(150, 450))
    assert np.abs(alinhado[miolo].astype(int) - ref[miolo].astype(int)).mean() < 3


def test_aplicar_desligado_devolve_a_mesma_imagem():
    rgb = cv2.cvtColor(textura(), cv2.COLOR_GRAY2RGB)
    quadro = {"theta": 0.1, "tx": 50.0, "ty": 0.0, "ganho": [2.0, 2.0, 2.0]}
    analise = {"largura_bruta": 600, "zoom_borda": 1.3, "alinhamento": True, "cor": True}
    assert c.aplicar(rgb, quadro, analise, cor=False, estabilizar=False) is rgb


def test_carregar_reduz_sem_girar(tmp_path):
    from PIL import Image
    caminho = tmp_path / "a.jpg"
    Image.fromarray(np.zeros((400, 600, 3), dtype=np.uint8)).save(caminho)
    assert c.carregar(caminho, 300, 200).shape == (200, 300, 3)
    assert c.tamanho_reduzido(6000, 4000, 1500) == (1500, 1000)
```

Atenção à convenção do teste: `cv2.warpAffine(ref, A, tamanho)` **sem** `WARP_INVERSE_MAP` produz um quadro em que `quadro(A·x) = ref(x)`. É exatamente o A que `alinhar` precisa devolver.

- [ ] **Step 3: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_correcao_alinhamento.py -q`
Expected: FAIL com `AttributeError: module 'timelapse.correcao' has no attribute 'euclidiana'`

- [ ] **Step 4: Implementar**

Em `timelapse/correcao.py`, troque o bloco de imports `import numpy as np` por:

```python
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
```

Logo abaixo de `LUMA = ...`, acrescente:

```python
MIN_INLIERS = 12
CORRELACAO_MINIMA = 0.85  # abaixo disto o ECC nao confia no alinhamento
```

No fim do arquivo, acrescente:

```python


# ---------- alinhamento ----------

def mascara(regiao, largura: int, altura: int) -> np.ndarray:
    x0, y0, x1, y1 = recorte(regiao, largura, altura)
    m = np.zeros((altura, largura), dtype=np.uint8)
    m[y0:y1, x0:x1] = 255
    return m


def euclidiana(theta: float, tx: float, ty: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s, tx], [s, c, ty]], dtype=np.float64)


def _chute_orb(ref: np.ndarray, quadro: np.ndarray, masc: np.ndarray) -> np.ndarray | None:
    """Chute inicial robusto a saltos grandes: ORB + RANSAC, escala forcada a 1."""
    orb = cv2.ORB_create(nfeatures=2000)
    kp_r, des_r = orb.detectAndCompute(ref, masc)
    kp_q, des_q = orb.detectAndCompute(quadro, None)
    if des_r is None or des_q is None:
        return None
    pares = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(des_r, des_q)
    if len(pares) < MIN_INLIERS:
        return None
    origem = np.float32([kp_r[p.queryIdx].pt for p in pares])
    destino = np.float32([kp_q[p.trainIdx].pt for p in pares])
    matriz, inliers = cv2.estimateAffinePartial2D(origem, destino, method=cv2.RANSAC,
                                                  ransacReprojThreshold=3.0)
    if matriz is None or int(inliers.sum()) < MIN_INLIERS:
        return None
    theta = math.atan2(matriz[1, 0], matriz[0, 0])
    return euclidiana(theta, matriz[0, 2], matriz[1, 2])


def alinhar(ref: np.ndarray, quadro: np.ndarray, masc: np.ndarray) -> np.ndarray | None:
    """Matriz A (referencia -> quadro) em pixels destas imagens, ou None se falhou.

    `ref` e `quadro` em escala de cinza, uint8, mesmo tamanho. `masc` marca a
    area parada e com textura na referencia (Q16).
    """
    chute = _chute_orb(ref, quadro, masc)
    inicial = (chute if chute is not None else euclidiana(0, 0, 0)).astype(np.float32)
    criterio = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-6)
    try:
        correlacao, matriz = cv2.findTransformECC(
            ref, quadro, inicial, cv2.MOTION_EUCLIDEAN, criterio, masc, 5)
    except cv2.error:
        return None
    if correlacao < CORRELACAO_MINIMA:
        return None
    return matriz.astype(np.float64)


def zoom_borda(matrizes, largura: float, altura: float) -> float:
    """Menor zoom, centrado, que esconde a borda de TODOS os quadros (Q17).

    Com zoom z a saida mostra, da referencia, o retangulo central reduzido por
    1/z. Cada canto dele, levado por A, precisa cair dentro do quadro.
    """
    centro = np.array([largura / 2, altura / 2])
    cantos = np.array([[0, 0], [largura, 0], [0, altura], [largura, altura]], dtype=np.float64)

    def cabe(z: float) -> bool:
        pontos = centro + (cantos - centro) / z
        for a in matrizes:
            levados = pontos @ np.asarray(a)[:, :2].T + np.asarray(a)[:, 2]
            if (levados < -1e-6).any() or (levados[:, 0] > largura + 1e-6).any() \
                    or (levados[:, 1] > altura + 1e-6).any():
                return False
        return True

    if cabe(1.0):
        return 1.0
    baixo, alto = 1.0, 2.0
    while not cabe(alto):
        alto *= 2
        if alto > 64:
            raise ValueError("A câmera andou demais: não há zoom que esconda a borda.")
    for _ in range(40):
        meio = (baixo + alto) / 2
        baixo, alto = (baixo, meio) if cabe(meio) else (meio, alto)
    return alto


def matriz_de_saida(theta: float, tx: float, ty: float, zoom: float,
                    largura: int, altura: int) -> np.ndarray:
    """Matriz para warpAffine(..., WARP_INVERSE_MAP): pixel de saida -> pixel do quadro.

    Junta o zoom de borda (centrado) com o alinhamento. tx, ty ja na escala
    desta imagem.
    """
    a = euclidiana(theta, tx, ty)
    rotacao = a[:, :2]
    centro = np.array([largura / 2, altura / 2])
    m = np.empty((2, 3))
    m[:, :2] = rotacao / zoom
    m[:, 2] = rotacao @ (centro * (1 - 1 / zoom)) + a[:, 2]
    return m


def aplicar(rgb: np.ndarray, quadro: dict, analise: dict, cor: bool,
            estabilizar: bool) -> np.ndarray:
    """Corrige uma imagem RGB uint8 de qualquer tamanho proporcional a foto crua."""
    altura, largura = rgb.shape[:2]
    if estabilizar and analise.get("alinhamento"):
        k = largura / analise["largura_bruta"]
        m = matriz_de_saida(quadro["theta"], quadro["tx"] * k, quadro["ty"] * k,
                            analise["zoom_borda"], largura, altura)
        rgb = cv2.warpAffine(rgb, m, (largura, altura),
                             flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                             borderMode=cv2.BORDER_REPLICATE)
    if cor and analise.get("cor"):
        rgb = cv2.LUT(rgb, tabela_de_ganho(quadro["ganho"]))
    return rgb


# ---------- leitura ----------

def carregar(caminho: Path, largura: int, altura: int) -> np.ndarray:
    """Foto CRUA (sem giro EXIF) em RGB uint8, reduzida para largura x altura.

    O draft do JPEG decodifica ja reduzido (1/2, 1/4, 1/8), o que corta muito
    o tempo em fotos de 6000 x 4000.
    """
    with Image.open(caminho) as imagem:
        imagem.draft("RGB", (largura, altura))
        rgb = np.asarray(imagem.convert("RGB"))
    if rgb.shape[1] != largura or rgb.shape[0] != altura:
        rgb = cv2.resize(rgb, (largura, altura), interpolation=cv2.INTER_AREA)
    return rgb


def tamanho_reduzido(largura: int, altura: int, lado: int) -> tuple[int, int]:
    escala = min(1.0, lado / max(largura, altura))
    return max(1, round(largura * escala)), max(1, round(altura * escala))
```

Como funciona: o ORB dá um chute que aguenta saltos grandes (esbarrão), e o ECC refina até o subpixel e devolve a correlação, que serve para saber quando a foto falhou. O zoom de borda entra **dentro** do mesmo `warpAffine`, então a saída tem o tamanho da entrada e o `video_filter()` continua igual. O Pillow não aplica o giro EXIF sozinho, e é por isso que `carregar` devolve a foto crua.

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/bin/python -m pytest tests/test_correcao_alinhamento.py tests/test_correcao_cor.py -q`
Expected: `16 passed`

Run: `.venv/bin/ruff check timelapse/correcao.py tests/`
Expected: os erros antigos de `tests/test_recorte.py` podem aparecer; nenhum erro em `correcao.py`, `sinteticos.py` ou `test_correcao_*.py`. Para conferir só os arquivos novos: `.venv/bin/ruff check timelapse/correcao.py tests/sinteticos.py tests/test_correcao_*.py` → `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add timelapse/correcao.py tests/sinteticos.py tests/test_correcao_alinhamento.py
git commit -m "Align frames to the reference with ORB and ECC, and hide the border"
```

---

### Task 4: Análise da sequência e cache da análise

**Files:**
- Modify: `timelapse/correcao.py`
- Modify: `tests/sinteticos.py`
- Test: `tests/test_correcao_analise.py`

**Interfaces:**
- Consumes: tudo da Task 2 e 3; `cache.fotos_de(pasta) -> list[Path]` e `cache.pasta_cache(pasta) -> Path` (já existem)
- Produces:
  - `class Cancelado(Exception)`
  - `chave(fotos, referencia, regiao_cor, regiao_alinhamento) -> str`
  - `analisar(fotos, referencia, regiao_cor=None, regiao_alinhamento=None, largura_bruta=None, altura_bruta=None, lado=1500, progresso=None) -> dict`, onde `progresso(feitos, total)` devolve `False` para cancelar
  - Formato da análise: `{"formato": 1, "chave", "referencia", "largura_bruta", "altura_bruta", "alinhamento": bool, "cor": bool, "zoom_borda": float, "quadros": {nome: {"theta", "tx", "ty", "ganho": [r,g,b], "falhou_alinhamento": bool, "cor_substituida": bool}}}`
  - `em_ordem(funcao, itens, adiante=8, trabalhadores=4)`: gerador paralelo, na ordem, com memória limitada
  - `analise_da_pasta(pasta, referencia, regiao_cor=None, regiao_alinhamento=None, progresso=None) -> dict` (lê ou grava `.cache-previa/<id>/analise.json`)
  - `tests/sinteticos.py`: `sequencia(pasta) -> list[Path]`

- [ ] **Step 1: Sequência sintética**

Acrescente ao fim de `tests/sinteticos.py`:

```python


def sequencia(pasta):
    """Cinco PNGs: tremor, um salto, luz caindo, e a do meio com uma mao na frente."""
    from PIL import Image

    from timelapse import correcao as c

    base = cv2.cvtColor(textura(900, 600), cv2.COLOR_GRAY2RGB)
    base[400:560, 650:850] = (140, 140, 140)  # area lisa para medir a cor
    deslizes = [(0, 0), (3, -2), (0, 0), (40, 25), (41, 24)]
    luzes = [1.0, 0.9, 1.0, 0.8, 0.8]
    fotos = []
    for i, ((dx, dy), luz) in enumerate(zip(deslizes, luzes, strict=True)):
        quadro = cv2.warpAffine(base, c.euclidiana(0, dx, dy), (900, 600),
                                borderMode=cv2.BORDER_REFLECT)
        linear = c.srgb_para_linear(quadro) * luz
        quadro = np.round(c.linear_para_srgb(linear)).astype(np.uint8)
        if i == 2:
            quadro[50:590, 100:880] = (20, 15, 10)
        caminho = pasta / f"IMG_{i:04d}.png"
        Image.fromarray(quadro).save(caminho)
        fotos.append(caminho)
    return fotos
```

- [ ] **Step 2: Escrever os testes que falham**

Crie `tests/test_correcao_analise.py`:

```python
import cv2
import numpy as np
import pytest
from sinteticos import sequencia

from timelapse import cache
from timelapse import correcao as c

ALINHAR = [0.1, 0.1, 0.55, 0.55]


@pytest.fixture(autouse=True)
def cache_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAIZ_CACHE", tmp_path / "cache")


def test_analisar_trata_salto_mao_e_luz(tmp_path):
    fotos = sequencia(tmp_path)
    analise = c.analisar(fotos, "IMG_0000.png", regiao_cor=[0.74, 0.69, 0.2, 0.2],
                         regiao_alinhamento=ALINHAR, lado=900)
    q = analise["quadros"]
    assert q["IMG_0002.png"]["falhou_alinhamento"] is True
    assert q["IMG_0002.png"]["cor_substituida"] is True
    # a do meio herda o deslize interpolado entre (3,-2) e (40,25)
    assert q["IMG_0002.png"]["tx"] == pytest.approx(21.5, abs=1.0)
    assert q["IMG_0003.png"]["tx"] == pytest.approx(40, abs=0.5)
    assert q["IMG_0003.png"]["ty"] == pytest.approx(25, abs=0.5)
    assert analise["zoom_borda"] > 1.0
    # a 5a foto foi escurecida para 0.8: o ganho volta ~1.25 (suavizado com vizinhos)
    assert 1.1 < q["IMG_0004.png"]["ganho"][1] < 1.3


def test_aplicar_em_tamanho_reduzido(tmp_path):
    fotos = sequencia(tmp_path)
    analise = c.analisar(fotos, "IMG_0000.png", regiao_alinhamento=ALINHAR, lado=900)
    pequena = c.carregar(fotos[3], 450, 300)
    quadros = analise["quadros"]
    saida = c.aplicar(pequena, quadros["IMG_0003.png"], analise, cor=False, estabilizar=True)
    ref = c.carregar(fotos[0], 450, 300)
    saida_ref = c.aplicar(ref, quadros["IMG_0000.png"], analise, cor=False, estabilizar=True)
    miolo = (slice(80, 220), slice(80, 300))
    # a foto 3 tambem esta mais escura: compara o desenho, nao o brilho
    a, b = saida[miolo][..., 1].ravel(), saida_ref[miolo][..., 1].ravel()
    assert np.corrcoef(a, b)[0, 1] > 0.97
    # sem alinhar, o desenho nao bate
    crua = cv2.resize(pequena, (450, 300))[miolo][..., 1].ravel()
    assert np.corrcoef(crua, b)[0, 1] < 0.5


def test_referencia_fora_da_pasta_e_recusada(tmp_path):
    fotos = sequencia(tmp_path)
    with pytest.raises(ValueError, match="Referência"):
        c.analisar(fotos, "NAO_EXISTE.png", regiao_alinhamento=ALINHAR)


def test_cancelar_para_a_analise(tmp_path):
    fotos = sequencia(tmp_path)
    with pytest.raises(c.Cancelado):
        c.analisar(fotos, "IMG_0000.png", regiao_alinhamento=ALINHAR,
                   progresso=lambda feitos, total: False)


def test_foto_nova_na_pasta_refaz_a_analise(tmp_path):
    fotos = sequencia(tmp_path)
    primeira = c.analise_da_pasta(tmp_path, "IMG_0000.png", regiao_alinhamento=ALINHAR)
    # a captura continua: chega uma foto depois da analise
    (tmp_path / "IMG_0005.png").write_bytes(fotos[4].read_bytes())
    segunda = c.analise_da_pasta(tmp_path, "IMG_0000.png", regiao_alinhamento=ALINHAR)
    assert "IMG_0005.png" not in primeira["quadros"]
    assert "IMG_0005.png" in segunda["quadros"]


def test_analise_salva_e_reaproveitada(tmp_path, monkeypatch):
    sequencia(tmp_path)
    c.analise_da_pasta(tmp_path, "IMG_0000.png", regiao_alinhamento=ALINHAR)
    monkeypatch.setattr(c, "analisar", lambda *a, **k: pytest.fail("recalculou"))
    c.analise_da_pasta(tmp_path, "IMG_0000.png", regiao_alinhamento=ALINHAR)


def test_em_ordem_preserva_a_ordem():
    assert list(c.em_ordem(lambda x: x * 2, range(30), adiante=3)) == [x * 2 for x in range(30)]
```

- [ ] **Step 3: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_correcao_analise.py -q`
Expected: FAIL com `AttributeError: module 'timelapse.correcao' has no attribute 'analisar'`

- [ ] **Step 4: Implementar**

Em `timelapse/correcao.py`, troque o bloco de imports por:

```python
import hashlib
import json
import math
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
```

Acima de `GANHO_MAXIMO`, acrescente:

```python
FORMATO = 1
LADO_ANALISE = 1500
```

Logo depois de `CORRELACAO_MINIMA = ...`, acrescente:

```python


class Cancelado(Exception):
    """O painel pediu outra correcao antes desta terminar."""
```

No fim do arquivo, acrescente:

```python


# ---------- analise da sequencia ----------

def chave(fotos: list[Path], referencia: str, regiao_cor, regiao_alinhamento) -> str:
    dados = json.dumps([FORMATO, referencia, regiao_cor, regiao_alinhamento,
                        [p.name for p in fotos]])
    return hashlib.sha1(dados.encode()).hexdigest()[:16]


def analisar(fotos: list[Path], referencia: str, regiao_cor=None, regiao_alinhamento=None,
             largura_bruta: int | None = None, altura_bruta: int | None = None,
             lado: int = LADO_ANALISE, progresso=None) -> dict:
    """Mede cada foto contra a referencia. Alinhamento primeiro, cor depois.

    `progresso(feitos, total)` e chamado a cada foto; se devolver False, a
    analise para com Cancelado.
    """
    nomes = [p.name for p in fotos]
    if referencia not in nomes:
        raise ValueError(f"Referência não está na pasta: {referencia}")
    if regiao_cor is None and regiao_alinhamento is None:
        raise ValueError("Marque ao menos uma região (cor ou alinhamento).")
    if largura_bruta is None:
        with Image.open(fotos[0]) as imagem:
            largura_bruta, altura_bruta = imagem.size
    largura, altura = tamanho_reduzido(largura_bruta, altura_bruta, lado)
    k = largura_bruta / largura  # pixels da analise -> pixels da foto crua

    ref_rgb = carregar(fotos[nomes.index(referencia)], largura, altura)
    ref_cinza = cv2.cvtColor(ref_rgb, cv2.COLOR_RGB2GRAY)
    masc = mascara(regiao_alinhamento, largura, altura) if regiao_alinhamento else None
    ref_cor = medir_cor(ref_rgb, regiao_cor) if regiao_cor else None

    n = len(fotos)
    parametros = np.zeros((n, 3))  # theta, tx, ty em pixels da foto crua
    alinhou = np.ones(n, dtype=bool)
    medidas = np.zeros((n, 3))

    def medir(i: int):
        rgb = ref_rgb if nomes[i] == referencia else carregar(fotos[i], largura, altura)
        matriz = euclidiana(0, 0, 0)
        ok = True
        if masc is not None and nomes[i] != referencia:
            achada = alinhar(ref_cinza, cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), masc)
            ok = achada is not None
            if ok:
                matriz = achada
        if ref_cor is not None:
            alinhada = rgb if not ok else cv2.warpAffine(
                rgb, matriz, (largura, altura),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
            cor = medir_cor(alinhada, regiao_cor)
        else:
            cor = np.ones(3)
        theta = math.atan2(matriz[1, 0], matriz[0, 0])
        return ok, (theta, matriz[0, 2] * k, matriz[1, 2] * k), cor

    with ThreadPoolExecutor(max_workers=4) as grupo:
        for i, (ok, params, cor) in enumerate(grupo.map(medir, range(n))):
            alinhou[i] = ok
            parametros[i] = params
            medidas[i] = cor
            if progresso and progresso(i + 1, n) is False:
                grupo.shutdown(cancel_futures=True)
                raise Cancelado()

    if masc is not None:
        if not alinhou.any():
            raise ValueError("O alinhamento falhou em todas as fotos. Escolha outra área.")
        parametros = interpolar(parametros, alinhou)
    zoom = zoom_borda([euclidiana(*p) for p in parametros], largura_bruta, altura_bruta) \
        if masc is not None else 1.0

    if ref_cor is not None:
        # quadro que nao alinhou mediu a cor no lugar errado: conta como invalido
        medidas[~alinhou] = 0
        ganhos, substituidos = ganhos_de_cor(ref_cor, medidas)
    else:
        ganhos, substituidos = np.ones((n, 3)), np.zeros(n, dtype=bool)

    return {
        "formato": FORMATO,
        "chave": chave(fotos, referencia, regiao_cor, regiao_alinhamento),
        "referencia": referencia,
        "largura_bruta": largura_bruta,
        "altura_bruta": altura_bruta,
        "alinhamento": masc is not None,
        "cor": ref_cor is not None,
        "zoom_borda": zoom,
        "quadros": {
            nome: {
                "theta": float(parametros[i, 0]),
                "tx": float(parametros[i, 1]),
                "ty": float(parametros[i, 2]),
                "ganho": [float(g) for g in ganhos[i]],
                "falhou_alinhamento": bool(not alinhou[i]),
                "cor_substituida": bool(substituidos[i]),
            }
            for i, nome in enumerate(nomes)
        },
    }


def em_ordem(funcao, itens, adiante: int = 8, trabalhadores: int = 4):
    """Como map(), em paralelo, mas com no maximo `adiante` resultados na memoria.

    Cada quadro reduzido tem varios MB; um map() comum enfileiraria todos.
    """
    with ThreadPoolExecutor(max_workers=trabalhadores) as grupo:
        pendentes = deque()
        for item in itens:
            pendentes.append(grupo.submit(funcao, item))
            if len(pendentes) >= adiante:
                yield pendentes.popleft().result()
        while pendentes:
            yield pendentes.popleft().result()


def arquivo_analise(pasta: Path) -> Path:
    from . import cache
    return cache.pasta_cache(pasta) / "analise.json"


def analise_da_pasta(pasta: Path, referencia: str, regiao_cor=None, regiao_alinhamento=None,
                     progresso=None) -> dict:
    """A analise salva no cache, ou uma nova. Painel e render dividem o mesmo arquivo."""
    from . import cache
    fotos = cache.fotos_de(pasta)
    esperada = chave(fotos, referencia, regiao_cor, regiao_alinhamento)
    arquivo = arquivo_analise(pasta)
    if arquivo.is_file():
        try:
            salva = json.loads(arquivo.read_text(encoding="utf-8"))
            if salva.get("chave") == esperada:
                return salva
        except (OSError, ValueError):
            pass
    analise = analisar(fotos, referencia, regiao_cor, regiao_alinhamento, progresso=progresso)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text(json.dumps(analise), encoding="utf-8")
    temporario.replace(arquivo)
    return analise
```

Por que `from . import cache` dentro da função: `cache.py` importa `cli.py`, e `cli.py` importa `correcao` (Task 6). O import tardio evita o ciclo. A análise cobre **todas** as fotos da pasta, na ordem por nome, e por isso a chave não depende de início, fim, passo ou ordem do render. Cada foto é procurada pelo nome.

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/bin/python -m pytest tests/test_correcao_analise.py tests/test_correcao_alinhamento.py tests/test_correcao_cor.py -q`
Expected: `23 passed`

Run: `.venv/bin/ruff check timelapse/correcao.py tests/sinteticos.py tests/test_correcao_*.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add timelapse/correcao.py tests/sinteticos.py tests/test_correcao_analise.py
git commit -m "Analyse a whole sequence against the reference and cache the result"
```

---

### Task 5: Parâmetros novos da CLI, comando extraído e fila

Esta task não muda nenhum comportamento: extrai o comando do ffmpeg para uma função e prova, com teste, que com as correções desligadas ele sai idêntico.

**Files:**
- Modify: `timelapse/cli.py` (DEFAULTS `:67-75`, argparse `:118-119`, validação `:166-170`, `video_filter` `:253-254`, `main` `:340-357`)
- Modify: `timelapse/fila.py:98-106`
- Test: `tests/test_cli_correcao.py`, `tests/test_fila.py`

**Interfaces:**
- Produces:
  - `cli.ler_regiao(valor, nome) -> list[float] | None` (aceita `"x,y,w,h"` ou lista)
  - `args.corrigir_cor: bool`, `args.estabilizar: bool`, `args.referencia: str | None`, `args.regiao_cor`, `args.regiao_alinhamento: list[float] | None`
  - `cli.video_filter(args, first_photo, tamanho=None)`
  - `cli.entrada_imagens(args, work, extension) -> list[str]`
  - `cli.comando_ffmpeg(ffmpeg, args, entrada, filtro, video) -> list[str]`
  - `fila.comando_cli(pasta: str, parametros: dict) -> list[str]` (lista vira `"a,b,c,d"`)

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/test_cli_correcao.py`:

```python
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
```

Crie `tests/test_fila.py`:

```python
import sys

from timelapse.fila import comando_cli


def test_regiao_vira_texto_x_y_w_h():
    comando = comando_cli("/fotos", {"regiao_cor": [0.1, 0.2, 0.3, 0.4], "estabilizar": True,
                                     "corrigir_cor": False, "referencia": "IMG_1.JPG"})
    assert comando == [sys.executable, "-m", "timelapse.cli", "/fotos",
                       "--regiao-cor", "0.1,0.2,0.3,0.4", "--estabilizar",
                       "--referencia", "IMG_1.JPG"]


def test_parametros_antigos_continuam_iguais():
    comando = comando_cli("/fotos", {"zoom": 1.5, "pos_x": -20, "fim": None, "inverter": False})
    assert comando[4:] == ["--zoom", "1.5", "--pos-x", "-20"]
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_cli_correcao.py tests/test_fila.py -q`
Expected: FAIL: `AttributeError: module 'timelapse.cli' has no attribute 'comando_ffmpeg'` e `ImportError: cannot import name 'comando_cli'`

- [ ] **Step 3: DEFAULTS e `ler_regiao` em `cli.py`**

Troque:

```python
    'girar': 'auto',
}
```

por:

```python
    'girar': 'auto',
    'corrigir_cor': False, 'estabilizar': False, 'referencia': None,
    'regiao_cor': None, 'regiao_alinhamento': None,
}


def ler_regiao(valor, nome):
    """Regiao normalizada [x, y, w, h], vinda do JSON (lista) ou da linha de comando (texto)."""
    if valor is None:
        return None
    if isinstance(valor, str):
        try:
            valor = [float(parte) for parte in valor.split(',')]
        except ValueError:
            raise ValueError(f'{nome} deve ser x,y,w,h com números entre 0 e 1.') from None
    if (not isinstance(valor, (list, tuple)) or len(valor) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in valor)):
        raise ValueError(f'{nome} deve ter quatro números: x,y,w,h.')
    x, y, w, h = (float(v) for v in valor)
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1 + 1e-9 or y + h > 1 + 1e-9:
        raise ValueError(f'{nome} precisa caber na foto: 0 <= x, y e x+w, y+h <= 1.')
    return [x, y, w, h]
```

- [ ] **Step 4: Bandeiras e validação**

Depois do `parser.add_argument('--girar', ...)` (as duas linhas que terminam em `help='Giro aplicado antes de tudo. ...')`), acrescente:

```python
    parser.add_argument('--corrigir-cor', action=argparse.BooleanOptionalAction,
                        help='Iguala brilho e cor ao quadro de referência, medindo em --regiao-cor.')
    parser.add_argument('--estabilizar', action=argparse.BooleanOptionalAction,
                        help='Alinha cada foto ao quadro de referência, medindo em --regiao-alinhamento.')
    parser.add_argument('--referencia', help='Nome do arquivo da foto de referência, como IMG_1234.JPG.')
    parser.add_argument('--regiao-cor', help='Área parada para medir a cor: x,y,w,h de 0 a 1, na foto sem giro.')
    parser.add_argument('--regiao-alinhamento', help='Área parada e com textura para alinhar: x,y,w,h de 0 a 1, na foto sem giro.')
```

No fim de `parse_args()`, troque:

```python
        raise ValueError('nome_saida deve ser apenas um nome terminado em .mp4, sem pastas.')
    return args
```

por:

```python
        raise ValueError('nome_saida deve ser apenas um nome terminado em .mp4, sem pastas.')
    for key in ('corrigir_cor', 'estabilizar'):
        if type(getattr(args, key)) is not bool:
            raise ValueError(f'{key} precisa ser true ou false.')
    args.regiao_cor = ler_regiao(args.regiao_cor, 'regiao_cor')
    args.regiao_alinhamento = ler_regiao(args.regiao_alinhamento, 'regiao_alinhamento')
    if (args.corrigir_cor or args.estabilizar) and not (isinstance(args.referencia, str) and args.referencia):
        raise ValueError('corrigir_cor e estabilizar precisam de referencia (nome da foto).')
    if args.corrigir_cor and args.regiao_cor is None:
        raise ValueError('corrigir_cor precisa de regiao_cor.')
    if args.estabilizar and args.regiao_alinhamento is None:
        raise ValueError('estabilizar precisa de regiao_alinhamento.')
    return args
```

- [ ] **Step 5: `video_filter` aceita tamanho e o comando vira função**

Troque:

```python
def video_filter(args, first_photo):
    source_w, source_h = image_size(first_photo)
```

por:

```python
def video_filter(args, first_photo, tamanho=None):
    """`tamanho` substitui as dimensões lidas da foto quando os quadros chegam já reduzidos."""
    source_w, source_h = tamanho or image_size(first_photo)
```

Logo antes de `def main():`, acrescente:

```python
def entrada_imagens(args, work, extension):
    return ['-f', 'image2', '-framerate', str(args.fps), '-start_number', '0',
            '-i', str(work / f'%08d.{extension}')]


def comando_ffmpeg(ffmpeg, args, entrada, filtro, video):
    command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-stats', '-nostdin',
               '-xerror', '-noautorotate', *entrada,
               '-vf', filtro,
               '-c:v', 'libx264', '-preset', args.preset, '-crf', str(args.qualidade),
               '-pix_fmt', 'yuv420p', *bandeira_de_quadros(ffmpeg),
               '-an', '-movflags', '+faststart', str(video)]
    if args.previa:
        command = command[:command.index('-c:v')] + ['-frames:v', '1', '-c:v', 'png', '-update', '1', str(video)]
    return command
```

Em `main()`, troque:

```python
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
```

por:

```python
        command = comando_ffmpeg(ffmpeg, args, entrada_imagens(args, work, extension),
                                 video_filter(args, photos[0]), video)
        subprocess.run(command, check=True)
```

- [ ] **Step 6: `fila.py` extrai `comando_cli`**

Logo antes de `@dataclass\nclass Trabalho:`, acrescente:

```python
def comando_cli(pasta: str, parametros: dict) -> list[str]:
    """Cada parametro do painel vira uma --bandeira da CLI."""
    comando = [sys.executable, "-m", "timelapse.cli", pasta]
    for chave, valor in parametros.items():
        bandeira = "--" + chave.replace("_", "-")
        if isinstance(valor, bool):
            if valor:
                comando.append(bandeira)
        elif isinstance(valor, (list, tuple)):
            comando += [bandeira, ",".join(str(v) for v in valor)]  # regioes x,y,w,h
        elif valor is not None and valor != "":
            comando += [bandeira, str(valor)]
    return comando


```

Em `_executar`, troque:

```python
        comando = [sys.executable, "-m", "timelapse.cli", trabalho.pasta]
        for chave, valor in trabalho.parametros.items():
            bandeira = "--" + chave.replace("_", "-")
            if isinstance(valor, bool):
                if valor:
                    comando.append(bandeira)
            elif valor is not None and valor != "":
                comando += [bandeira, str(valor)]

        processo = subprocess.Popen(
```

por:

```python
        comando = comando_cli(trabalho.pasta, trabalho.parametros)
        processo = subprocess.Popen(
```

- [ ] **Step 7: Rodar para ver passar**

Run: `.venv/bin/python -m pytest -q`
Expected: todos passam (`test_recorte.py` inclusive), entre eles os 8 de `test_cli_correcao.py` e os 2 de `test_fila.py`.

Run: `.venv/bin/ruff check tests/test_cli_correcao.py tests/test_fila.py`
Expected: `All checks passed!` (`cli.py` já tem linhas longas antigas; não mexer nelas.)

- [ ] **Step 8: Prova extra de que o render antigo não mudou**

Run: `.venv/bin/python -m timelapse.cli "<uma pasta com fotos>" --sem-config --resolucao 1080x1920 --conferir`
Expected: lista a sequência, sem erro de parâmetro.

- [ ] **Step 9: Commit**

```bash
git add timelapse/cli.py timelapse/fila.py tests/test_cli_correcao.py tests/test_fila.py
git commit -m "Accept correction parameters in the CLI without changing the render"
```

---

### Task 6: Render corrigido por pipe

**Files:**
- Modify: `timelapse/cli.py`
- Modify: `docs-cli.md`
- Test: `tests/test_cli_correcao.py`

**Interfaces:**
- Consumes: `correcao.analise_da_pasta`, `correcao.carregar`, `correcao.aplicar`, `correcao.em_ordem` (Task 4); `cli.comando_ffmpeg`, `cli.video_filter(..., tamanho)` (Task 5)
- Produces:
  - `cli.escala_necessaria(args, largura, altura, giro, zoom_borda=1.0) -> float` em (0, 1]
  - `cli.entrada_pipe(args, largura, altura) -> list[str]`
  - `cli.render_corrigido(ffmpeg, args, folder, photos, giro, video) -> None`
  - Saída da CLI: linhas `Analisando N/T` e `Zoom extra para esconder a borda: 1.050x`; o `frame=` do ffmpeg continua saindo (a `fila.py` lê isso).

- [ ] **Step 1: Escrever os testes que falham**

No topo de `tests/test_cli_correcao.py`, troque os imports por:

```python
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
```

Acrescente no fim do arquivo:

```python


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
    gerado = saida.with_suffix('.previa.png') if '--previa' in extra else saida
    assert gerado.stat().st_size > 0


def test_referencia_que_nao_existe_e_recusada(tmp_path):
    pasta = _pasta_tremida(tmp_path)
    resultado = rodar_cli(
        tmp_path, str(pasta), '--estabilizar', '--referencia', 'NAO_EXISTE.jpg',
        '--regiao-alinhamento', '0.2,0.2,0.6,0.6', '--saida', str(tmp_path / 's.mp4'))
    assert resultado.returncode == 1
    assert 'referência não está na pasta' in resultado.stderr
```

`TIMELAPSE_CACHE` (Task 1) impede que a análise dos testes caia no `.cache-previa` do projeto.

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_cli_correcao.py -q`
Expected: FAIL: `escala_necessaria` não existe; os de ponta a ponta saem com returncode 0 **sem** `Zoom extra` (a correção é ignorada) ou falham na referência inexistente.

- [ ] **Step 3: Implementar**

Em `cli.py`, logo antes de `def entrada_imagens(...)`, acrescente:

```python
def escala_necessaria(args, largura, altura, giro, zoom_borda=1.0):
    """Fração da foto crua que basta para a saída não perder nitidez (Q11).

    A conta segue video_filter: o zoom recorta, depois a escala ajusta ou
    preenche. O zoom de borda amplia de novo, então pede mais pixels.
    """
    if args.resolucao == 'original':
        return 1.0
    fonte_w, fonte_h = (altura, largura) if giro in ('90', '270') else (largura, altura)
    saida_w, saida_h = map(int, args.resolucao.split('x'))
    visivel_w, visivel_h = fonte_w / args.zoom, fonte_h / args.zoom
    escolha = min if args.enquadramento == 'ajustar' else max
    return min(1.0, escolha(saida_w / visivel_w, saida_h / visivel_h) * zoom_borda)


```

Logo depois de `def entrada_imagens(...)`, acrescente:

```python
def entrada_pipe(args, largura, altura):
    return ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{largura}x{altura}',
            '-framerate', str(args.fps), '-i', 'pipe:0']
```

Logo depois de `def comando_ffmpeg(...)`, acrescente:

```python
def render_corrigido(ffmpeg, args, folder, photos, giro, video):
    """Corrige cada foto em Python e entrega os pixels ao ffmpeg por pipe (Q4, Q11)."""
    from timelapse import correcao
    analise = correcao.analise_da_pasta(
        folder, args.referencia,
        args.regiao_cor if args.corrigir_cor else None,
        args.regiao_alinhamento if args.estabilizar else None,
        progresso=lambda feitos, total: print(f'Analisando {feitos}/{total}', flush=True))
    if args.estabilizar:
        print(f'Zoom extra para esconder a borda: {analise["zoom_borda"]:.3f}x', flush=True)
    largura_bruta, altura_bruta = image_size(photos[0])
    escala = escala_necessaria(args, largura_bruta, altura_bruta, giro,
                               analise['zoom_borda'] if args.estabilizar else 1.0)
    largura = max(2, round(largura_bruta * escala))
    altura = max(2, round(altura_bruta * escala))

    def preparar(photo):
        rgb = correcao.carregar(photo, largura, altura)
        return correcao.aplicar(rgb, analise['quadros'][photo.name], analise,
                                cor=args.corrigir_cor, estabilizar=args.estabilizar)

    filtro = video_filter(args, photos[0], tamanho=(largura, altura))
    command = comando_ffmpeg(ffmpeg, args, entrada_pipe(args, largura, altura), filtro, video)
    processo = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for rgb in correcao.em_ordem(preparar, photos[:1] if args.previa else photos):
            processo.stdin.write(rgb.tobytes())
        processo.stdin.close()
    except BrokenPipeError:
        pass  # o ffmpeg parou antes; o código de saída dele diz o motivo
    finally:
        if processo.wait():
            raise subprocess.CalledProcessError(processo.returncode, command)
```

Em `main()`, logo depois de `print(f'Primeira: {photos[0].name}\nÚltima:   {photos[-1].name}', flush=True)`, acrescente:

```python
    if (args.corrigir_cor or args.estabilizar) and not (folder / args.referencia).is_file():
        raise ValueError(f'A foto de referência não está na pasta: {args.referencia}')
```

Ainda em `main()`, troque:

```python
        for index, photo in enumerate(photos):
            (work / f'{index:08d}.{extension}').symlink_to(photo)
        video = work / ('previa.png' if args.previa else 'video.mp4')
        report = work / 'fotos.csv'
        command = comando_ffmpeg(ffmpeg, args, entrada_imagens(args, work, extension),
                                 video_filter(args, photos[0]), video)
        subprocess.run(command, check=True)
```

por:

```python
        video = work / ('previa.png' if args.previa else 'video.mp4')
        report = work / 'fotos.csv'
        if args.corrigir_cor or args.estabilizar:
            render_corrigido(ffmpeg, args, folder, photos, giro, video)
        else:
            for index, photo in enumerate(photos):
                (work / f'{index:08d}.{extension}').symlink_to(photo)
            command = comando_ffmpeg(ffmpeg, args, entrada_imagens(args, work, extension),
                                     video_filter(args, photos[0]), video)
            subprocess.run(command, check=True)
```

Detalhes que importam:
- Os quadros vão ao ffmpeg **sem giro e já reduzidos**. O `video_filter` recebe o tamanho reduzido e aplica giro, zoom e corte do Lucca como sempre. Como o zoom do `video_filter` é relativo (`iw/zoom`), a conta do painel continua valendo.
- `em_ordem` limita a memória a 8 quadros: sem isso, 455 quadros de ~7 MB ficariam todos na RAM se o Python fosse mais rápido que o x264.
- `-nostdin` e `-i pipe:0` convivem: `-nostdin` só desliga o teclado (o teste de ponta a ponta prova isso).
- O ffmpeg herda o stdout e o stderr da CLI, então o `frame=` que a `fila.py` lê continua chegando.

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/bin/python -m pytest -q`
Expected: todos passam; `test_cli_correcao.py` com 16 testes.

Run: `.venv/bin/ruff check tests/test_cli_correcao.py`
Expected: `All checks passed!`

- [ ] **Step 5: Documentar a CLI**

Em `docs-cli.md`, logo depois da linha `- `--girar auto|nao|90|180|270`: giro antes do corte. Padrão `auto`, pela etiqueta EXIF.`, acrescente:

```markdown
- `--corrigir-cor`: iguala brilho e cor de cada foto à de referência, medindo só em `--regiao-cor`. Desligado por padrão.
- `--estabilizar`: alinha cada foto à de referência (deslize e giro), medindo só em `--regiao-alinhamento`, e amplia o mínimo necessário para esconder a borda. Desligado por padrão.
- `--referencia IMG_1234.JPG`: a foto que as outras devem imitar. Obrigatória com qualquer uma das duas correções.
- `--regiao-cor x,y,w,h` e `--regiao-alinhamento x,y,w,h`: retângulos de 0 a 1 na foto **sem giro**. O painel desenha e grava esses valores no `enquadramento.json`; à mão, prefira o painel.

Com alguma correção ligada, a primeira vez analisa a pasta inteira (cerca de 0,1 s por foto de 6000×4000) e guarda o resultado em `.cache-previa/`. As fotos originais nunca são alteradas.
```

- [ ] **Step 6: Commit**

```bash
git add timelapse/cli.py tests/test_cli_correcao.py docs-cli.md
git commit -m "Render corrected frames through a pipe to FFmpeg"
```

---

### Task 7: Prévia corrigida e rotas do servidor

**Files:**
- Modify: `timelapse/correcao.py`
- Modify: `timelapse/servidor.py`
- Test: `tests/test_servidor_correcao.py`

**Interfaces:**
- Consumes: `correcao.analise_da_pasta`, `aplicar`, `em_ordem`, `Cancelado` (Task 4); `cache.manifesto`, `cache.caminho_quadro`, `cache.construir` (já existem)
- Produces:
  - `correcao.gerar_previa(pasta, analise, cor, estabilizar, progresso=None) -> dict` → grava `.cache-previa/<id>/corrigido/q_%06d.jpg` e `info.json`
  - `info.json`: `{"chave", "montado", "cor": bool, "estabilizar": bool, "zoom_borda": float, "total_fotos": int, "falhas": [índices na pasta, 0-based], "versao": int}`
  - `correcao.info_previa(pasta) -> dict | None` (None se o cache foi remontado depois)
  - `correcao.apagar_previa(pasta) -> None`
  - Rotas:
    - `GET /api/fotos?pasta=` → `{"nomes": [...]}`
    - `GET /api/correcao?pasta=` → `{"estado": null | {"fase": "na fila"|"analisando"|"aplicando", "feitos", "total"} | {"fase": "erro", "erro"}, "info": info.json | null}`
    - `POST /api/correcao` `{pasta, referencia, regiao_cor|null, regiao_alinhamento|null}` → `{"estado": ...}`; sem referência ou sem região, apaga a prévia corrigida e devolve `{"estado": null}`
    - `POST /api/enquadramento/correcao` `{pasta, correcao: {...}}` → mescla só `referencia`, `regiao_cor`, `regiao_alinhamento`, `corrigir_cor`, `estabilizar` no `enquadramento.json`
    - `GET /q/<id>/corrigido/q_XXXXXX.jpg`

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/test_servidor_correcao.py`:

```python
import json
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import Request, urlopen

import cv2
import numpy as np
import pytest

from timelapse import cache, cli, correcao, servidor


@pytest.fixture
def painel(tmp_path, monkeypatch):
    try:
        cli.find_ffmpeg()
    except ValueError:
        pytest.skip("ffmpeg indisponivel")
    monkeypatch.setattr(cache, "RAIZ_CACHE", tmp_path / "cache")
    pasta = tmp_path / "fotos"
    pasta.mkdir()
    gerador = np.random.default_rng(5)
    base = cv2.resize(gerador.integers(0, 256, (40, 60, 3), dtype=np.uint8), (600, 400),
                      interpolation=cv2.INTER_CUBIC)
    for i, dx in enumerate([0, 3, 6, 6, 5]):
        quadro = cv2.warpAffine(base, np.float64([[1, 0, dx], [0, 1, 0]]), (600, 400),
                                borderMode=cv2.BORDER_REFLECT)
        if i == 2:
            quadro[:] = 5  # mao na frente: tudo escuro
        cv2.imwrite(str(pasta / f"IMG_{i}.jpg"), quadro)
    cache.construir(pasta, limite=300, lado=300)
    http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Painel)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{http.server_address[1]}", pasta
    http.shutdown()


def chamar(url, corpo=None):
    dados = None if corpo is None else json.dumps(corpo).encode()
    pedido = Request(url, data=dados, headers={"Content-Type": "application/json"})
    with urlopen(pedido) as resposta:
        return json.loads(resposta.read())


def test_correcao_gera_previa_e_marca_falhas(painel):
    base, pasta = painel
    chamar(base + "/api/correcao", {
        "pasta": str(pasta), "referencia": "IMG_0.jpg",
        "regiao_cor": [0.1, 0.1, 0.3, 0.3], "regiao_alinhamento": [0.2, 0.2, 0.6, 0.6]})
    for _ in range(100):
        resposta = chamar(base + f"/api/correcao?pasta={quote(str(pasta))}")
        if resposta["info"] or (resposta["estado"] or {}).get("fase") == "erro":
            break
        time.sleep(0.1)
    assert resposta["estado"] is None, resposta
    assert resposta["info"]["falhas"] == [2]
    corrigidos = sorted((cache.pasta_cache(pasta) / "corrigido").glob("q_*.jpg"))
    assert len(corrigidos) == 5
    with urlopen(base + f"/q/{cache.id_da_pasta(pasta)}/corrigido/q_000000.jpg") as quadro:
        assert quadro.headers["Content-Type"] == "image/jpeg"


def test_sem_regiao_apaga_a_previa_corrigida(painel):
    base, pasta = painel
    destino = cache.pasta_cache(pasta) / "corrigido"
    destino.mkdir()
    (destino / "q_000000.jpg").write_bytes(b"x")
    resposta = chamar(base + "/api/correcao", {"pasta": str(pasta), "referencia": "IMG_0.jpg"})
    assert resposta == {"estado": None}
    assert not destino.exists()


def test_salvar_correcao_preserva_o_enquadramento(painel):
    base, pasta = painel
    (pasta / "enquadramento.json").write_text(json.dumps({"zoom": 1.4}))
    chamar(base + "/api/enquadramento/correcao", {
        "pasta": str(pasta), "correcao": {"referencia": "IMG_0.jpg", "intrusa": 1}})
    salvo = json.loads((pasta / "enquadramento.json").read_text())
    assert salvo == {"zoom": 1.4, "referencia": "IMG_0.jpg"}


def test_lista_nomes_das_fotos(painel):
    base, pasta = painel
    nomes = chamar(base + f"/api/fotos?pasta={quote(str(pasta))}")["nomes"]
    assert nomes == [f"IMG_{i}.jpg" for i in range(5)]


def test_previa_corrigida_de_cache_antigo_e_ignorada(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAIZ_CACHE", tmp_path / "cache")
    destino = cache.pasta_cache(tmp_path)
    (destino / "corrigido").mkdir(parents=True)
    (destino / "manifesto.json").write_text(json.dumps({"formato": cache.FORMATO, "montado": 2}))
    (destino / "corrigido" / "info.json").write_text(json.dumps({"montado": 1}))
    assert correcao.info_previa(tmp_path) is None
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_servidor_correcao.py -q`
Expected: FAIL: `info_previa` não existe; as rotas devolvem 404 (`HTTPError: HTTP Error 404`).

- [ ] **Step 3: Prévia corrigida em `correcao.py`**

Troque o bloco de imports por:

```python
import hashlib
import json
import math
import shutil
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
```

No fim do arquivo, acrescente:

```python


# ---------- previa corrigida do painel ----------

def gerar_previa(pasta: Path, analise: dict, cor: bool, estabilizar: bool, progresso=None) -> dict:
    """Aplica a correcao nos quadros do cache, em .cache-previa/<id>/corrigido/.

    Devolve o info.json gravado: o painel o usa para trocar antes/depois e
    para marcar no slider as fotos que nao alinharam (Q18).
    """
    from . import cache
    manifesto = cache.manifesto(pasta)
    if manifesto is None:
        raise ValueError("Monte a prévia antes de corrigir.")
    fotos = cache.fotos_de(pasta)
    destino = cache.pasta_cache(pasta) / "corrigido"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "info.json").unlink(missing_ok=True)
    for antigo in destino.glob("q_*.jpg"):
        antigo.unlink()

    def corrigir(posicao: int) -> None:
        nome = fotos[manifesto["indices"][posicao]].name
        with Image.open(cache.caminho_quadro(pasta, posicao)) as imagem:
            rgb = np.asarray(imagem.convert("RGB"))
        saida = aplicar(rgb, analise["quadros"][nome], analise, cor, estabilizar)
        Image.fromarray(saida).save(destino / f"q_{posicao:06d}.jpg", quality=90)

    total = manifesto["quadros"]
    for feitos, _ in enumerate(em_ordem(corrigir, range(total)), start=1):
        if progresso and progresso(feitos, total) is False:
            raise Cancelado()

    info = {
        "chave": analise["chave"],
        "montado": manifesto["montado"],
        "cor": cor,
        "estabilizar": estabilizar,
        "zoom_borda": analise["zoom_borda"] if estabilizar else 1.0,
        "total_fotos": len(fotos),
        "falhas": [i for i, foto in enumerate(fotos)
                   if analise["quadros"][foto.name]["falhou_alinhamento"]],
        # vai na URL do quadro, como o "montado" do cache
        "versao": int(time.time() * 1000),
    }
    (destino / "info.json").write_text(json.dumps(info), encoding="utf-8")
    return info


def info_previa(pasta: Path) -> dict | None:
    """O info.json da previa corrigida, se ela ainda corresponde ao cache atual."""
    from . import cache
    manifesto = cache.manifesto(pasta)
    arquivo = cache.pasta_cache(pasta) / "corrigido" / "info.json"
    if manifesto is None or not arquivo.is_file():
        return None
    try:
        info = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return info if info.get("montado") == manifesto["montado"] else None


def apagar_previa(pasta: Path) -> None:
    from . import cache
    destino = cache.pasta_cache(pasta) / "corrigido"
    if destino.is_dir():
        shutil.rmtree(destino)
```

Os quadros do cache estão sem giro, igual às fotos cruas, e por isso o mesmo `aplicar` serve aqui. O navegador gira os quadros corrigidos do mesmo jeito que já gira os normais.

- [ ] **Step 4: Rotas em `servidor.py`**

Troque:

```python
FILA = Fila()
CACHES_EM_CURSO: dict[str, str] = {}
```

por:

```python
FILA = Fila()
CACHES_EM_CURSO: dict[str, str] = {}
# Correcao: um calculo por vez. Um pedido novo para a mesma pasta faz o antigo
# desistir no proximo quadro, em vez de terminar algo que ja nao serve.
CORRECOES: dict[str, dict] = {}
PEDIDOS_CORRECAO: dict[str, int] = {}
TRAVA_CORRECAO = threading.Lock()
CHAVES_CORRECAO = ("referencia", "regiao_cor", "regiao_alinhamento", "corrigir_cor", "estabilizar")
```

Logo depois de `def arquivo_enquadramento(...)`, acrescente:

```python


def mesclar_enquadramento(pasta: Path, novos: dict) -> dict:
    """Grava so as chaves passadas, preservando o resto do enquadramento.json."""
    arquivo = arquivo_enquadramento(pasta)
    atuais = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}
    atuais.update(novos)
    arquivo.write_text(json.dumps(atuais, ensure_ascii=False, indent=1), encoding="utf-8")
    return atuais


def calcular_correcao(pasta: Path, pedido: dict, numero: int) -> None:
    """Roda em thread: analisa a sequencia e gera a previa corrigida."""
    from . import correcao

    chave = str(pasta)

    def progresso(fase):
        def marcar(feitos, total):
            if PEDIDOS_CORRECAO.get(chave) != numero:
                return False
            CORRECOES[chave] = {"fase": fase, "feitos": feitos, "total": total}
            return True
        return marcar

    with TRAVA_CORRECAO:
        if PEDIDOS_CORRECAO.get(chave) != numero:
            return
        try:
            analise = correcao.analise_da_pasta(
                pasta, pedido["referencia"], pedido.get("regiao_cor"),
                pedido.get("regiao_alinhamento"), progresso=progresso("analisando"))
            correcao.gerar_previa(pasta, analise, cor=bool(pedido.get("regiao_cor")),
                                  estabilizar=bool(pedido.get("regiao_alinhamento")),
                                  progresso=progresso("aplicando"))
            CORRECOES.pop(chave, None)
        except correcao.Cancelado:
            pass
        except Exception as erro:  # noqa: BLE001 - vira aviso no painel
            CORRECOES[chave] = {"fase": "erro", "erro": str(erro)}
```

Em `do_GET`, troque:

```python
        if rota == "/api/fila":
            return self._json(FILA.estado())

        if rota.startswith("/q/"):
            partes = rota[3:].split("/")
            if len(partes) == 2:
                alvo = cache.RAIZ_CACHE / partes[0] / partes[1]
                return self._arquivo(alvo, cacheavel=True)
```

por:

```python
        if rota == "/api/fila":
            return self._json(FILA.estado())

        if rota == "/api/fotos":
            pasta = Path(consulta.get("pasta", ""))
            return self._json({"nomes": [p.name for p in cache.fotos_de(pasta)]})

        if rota == "/api/correcao":
            pasta = Path(consulta.get("pasta", ""))
            try:
                from . import correcao
                info = correcao.info_previa(pasta)
            except ImportError:
                info = None
            return self._json({"estado": CORRECOES.get(str(pasta)), "info": info})

        if rota.startswith("/q/"):
            partes = rota[3:].split("/")
            if len(partes) == 2:
                alvo = cache.RAIZ_CACHE / partes[0] / partes[1]
                return self._arquivo(alvo, cacheavel=True)
            if len(partes) == 3 and partes[1] == "corrigido":
                alvo = cache.RAIZ_CACHE / partes[0] / "corrigido" / partes[2]
                return self._arquivo(alvo, cacheavel=True)
```

Em `do_POST`, troque:

```python
        if rota == "/api/fila":
            pasta = Path(dados["pasta"])
```

por:

```python
        if rota == "/api/enquadramento/correcao":
            pasta = Path(dados["pasta"])
            novos = {k: v for k, v in dados["correcao"].items() if k in CHAVES_CORRECAO}
            return self._json({"salvo": mesclar_enquadramento(pasta, novos)})

        if rota == "/api/correcao":
            pasta = Path(dados["pasta"])
            try:
                from . import correcao
            except ImportError:
                return self._json({"erro": "Faltam numpy, Pillow e opencv-python. Rode make setup."}, 500)
            numero = PEDIDOS_CORRECAO.get(str(pasta), 0) + 1
            PEDIDOS_CORRECAO[str(pasta)] = numero
            if not dados.get("referencia") or not (dados.get("regiao_cor") or dados.get("regiao_alinhamento")):
                CORRECOES.pop(str(pasta), None)
                correcao.apagar_previa(pasta)
                return self._json({"estado": None})
            CORRECOES[str(pasta)] = {"fase": "na fila", "feitos": 0, "total": 0}
            threading.Thread(target=calcular_correcao, args=(pasta, dados, numero), daemon=True).start()
            return self._json({"estado": CORRECOES[str(pasta)]})

        if rota == "/api/fila":
            pasta = Path(dados["pasta"])
```

Por que o `import correcao` fica dentro das rotas: assim o painel continua subindo sem a venv (o caminho antigo não precisa de numpy) e mostra um erro claro só quando alguém tenta corrigir.

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/bin/python -m pytest -q`
Expected: todos passam; `test_servidor_correcao.py` com 5.

Run: `.venv/bin/ruff check tests/test_servidor_correcao.py timelapse/correcao.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add timelapse/correcao.py timelapse/servidor.py tests/test_servidor_correcao.py
git commit -m "Build the corrected preview and serve it from the panel"
```

---

### Task 8: Painel — referência, áreas, antes/depois e marcas

**Files:**
- Create: `web/regioes.js`
- Modify: `web/index.html`, `web/app.js`, `web/estilo.css`
- Modify: `README.md`
- Test: `tests/test_regioes_js.py`

**Interfaces:**
- Consumes: as rotas da Task 7; `giroEfetivo(p)` e `desenhar()` (já existem em `app.js`)
- Produces: `regioes.paraCru(giro, [x,y,w,h])` e `regioes.paraTela(giro, [x,y,w,h])` (global no navegador; `module.exports` no Node). O `enquadramento.json` ganha `referencia`, `regiao_cor`, `regiao_alinhamento`, `corrigir_cor` e `estabilizar`, e a fila recebe as mesmas chaves.

- [ ] **Step 1: Escrever o teste que falha**

Crie `tests/test_regioes_js.py`:

```python
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
    codigo = (f"const r = require({json.dumps(str(REGIOES))});"
              f" console.log(JSON.stringify({expressao}));")
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
```

Run: `.venv/bin/python -m pytest tests/test_regioes_js.py -q`
Expected: FAIL: `Cannot find module '.../web/regioes.js'` (via `CalledProcessError`)

- [ ] **Step 2: Criar `web/regioes.js`**

```javascript
'use strict';

// Regioes da correcao: o painel desenha sobre o quadro GIRADO, mas o arquivo
// guarda tudo na foto CRUA (sem giro), que e como o cache e o ffmpeg a leem.
// Coordenadas normalizadas de 0 a 1. Giro como em --girar: '90' e horario.

function giradoParaCru(giro, x, y) {
  if (giro === '90') return [y, 1 - x];
  if (giro === '180') return [1 - x, 1 - y];
  if (giro === '270') return [1 - y, x];
  return [x, y];
}

function cruParaGirado(giro, x, y) {
  if (giro === '90') return [1 - y, x];
  if (giro === '180') return [1 - x, 1 - y];
  if (giro === '270') return [y, 1 - x];
  return [x, y];
}

// Retangulo [x, y, w, h] convertido pelos dois cantos opostos.
function converterRetangulo(conversao, giro, r) {
  const [ax, ay] = conversao(giro, r[0], r[1]);
  const [bx, by] = conversao(giro, r[0] + r[2], r[1] + r[3]);
  return [Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay)];
}

const regioes = {
  paraCru: (giro, r) => converterRetangulo(giradoParaCru, giro, r),
  paraTela: (giro, r) => converterRetangulo(cruParaGirado, giro, r),
};

if (typeof module !== 'undefined') module.exports = regioes;
```

A conta bate com as transformações CSS que o `desenhar()` já usa: `270` é `translate(0, lb) rotate(270deg)`, que leva o ponto cru `(x, y)` normalizado a `(y, 1 − x)` na tela.

Run: `.venv/bin/python -m pytest tests/test_regioes_js.py -q`
Expected: `6 passed`

- [ ] **Step 3: `index.html`**

Troque:

```html
      <div id="moldura" class="moldura"><div id="giro" class="giro"><img id="quadro" alt=""></div></div>
```

por:

```html
      <div id="moldura" class="moldura"><div id="giro" class="giro"><img id="quadro" alt="">
        <div id="ret-cor" class="retangulo ret-cor" hidden></div>
        <div id="ret-alinhamento" class="retangulo ret-alinhamento" hidden></div>
      </div></div>
```

Troque:

```html
      <input type="range" id="quadro-atual" min="0" max="0" value="0" disabled>
      <div class="tempo-pontas"><span>início</span><span id="rotulo-total"></span></div>
```

por:

```html
      <div class="trilho">
        <input type="range" id="quadro-atual" min="0" max="0" value="0" disabled>
        <div id="marcas" class="marcas" title="Fotos que não alinharam: usam o deslocamento dos vizinhos"></div>
      </div>
      <div class="tempo-pontas"><span>início</span><span id="rotulo-total"></span></div>
      <button id="btn-antes-depois" class="secundario antes-depois" type="button" hidden>Ver antes</button>
```

Troque `    <details id="avancado">` por:

```html
    <h2>Correção</h2>
    <div class="campo correcao">
      <button id="btn-referencia" class="secundario" type="button" disabled>Usar este quadro como referência</button>
      <p class="dica dica-fixa" id="dica-referencia">Sem referência: nada é corrigido.</p>
      <div class="ferramentas">
        <button id="btn-area-cor" class="secundario ferramenta-cor" type="button" disabled>Área para cor</button>
        <button id="btn-area-alinhamento" class="secundario ferramenta-alinhamento" type="button" disabled>Área para alinhar</button>
      </div>
      <p class="dica dica-fixa">Cor: área parada e lisa (mesa, parede). Alinhar: área parada e com textura, longe do bico, da mesa e da peça.</p>
      <p id="estado-correcao" class="dica"></p>
      <div class="ferramentas">
        <button id="btn-remover-cor" class="secundario" type="button" hidden>Remover correção de cor</button>
        <button id="btn-remover-alinhamento" class="secundario" type="button" hidden>Remover estabilização</button>
      </div>
    </div>

    <details id="avancado">
```

Troque `<script src="/web/app.js"></script>` por:

```html
<script src="/web/regioes.js"></script>
<script src="/web/app.js"></script>
```

- [ ] **Step 4: `estilo.css`**

Logo antes de `.tempo label { display:block;`, acrescente:

```css
/* correcao: retangulos sobre a previa e marcas no slider */
.retangulo { position:absolute; border:2px solid; pointer-events:none; }
.retangulo[hidden] { display:none; }
.ret-cor { border-color:#3FA7D6; background:rgba(63,167,214,.12); }
.ret-alinhamento { border-color:#E0B53B; background:rgba(224,181,59,.12); border-style:dashed; }
.moldura.desenhando { cursor:crosshair; touch-action:none; }
/* sem isto o navegador arrasta a foto em vez de desenhar o retangulo */
.moldura img { -webkit-user-drag:none; user-select:none; }
.trilho { position:relative; }
.marcas { position:absolute; left:8px; right:8px; bottom:-3px; height:4px; pointer-events:none; }
.marcas i { position:absolute; width:2px; height:4px; background:var(--accent); }
.antes-depois { margin-top:6px; padding:5px 10px; font-size:12px; }
.ferramentas { display:flex; gap:6px; margin-top:6px; }
.ferramentas button { flex:1; padding:6px 8px; font-size:12px; }
.ferramentas button[hidden] { display:none; }
.ferramenta-cor.ativa { border-color:#3FA7D6; color:#3FA7D6; }
.ferramenta-alinhamento.ativa { border-color:#E0B53B; color:#E0B53B; }
.correcao > button { width:100%; }
```

Cores diferentes e traço diferente (cheio para cor, tracejado para alinhar) deixam as duas áreas distintas mesmo para quem confunde cores.

- [ ] **Step 5: `app.js`, estado e parâmetros**

Troque:

```javascript
const estado = { acervo: [], sequencia: null, manifesto: null, padroes: {}, limiteCache: 300 };
```

por:

```javascript
const estado = { acervo: [], sequencia: null, manifesto: null, padroes: {}, limiteCache: 300,
  // correcao: referencia e regioes na foto CRUA; info vem do servidor quando a previa corrigida existe
  correcao: { referencia: null, regiao_cor: null, regiao_alinhamento: null },
  nomes: [], infoCorrecao: null, verCorrigido: true, ferramenta: null };
```

Em `desenhar()`, troque:

```javascript
  const g = giroEfetivo(p);
  $('dica-giro').textContent = p.girar === 'auto'
```

por:

```javascript
  const g = giroEfetivo(p);
  desenharRegioes(g);
  $('dica-giro').textContent = p.girar === 'auto'
```

Troque a função `lerParametros()` inteira por:

```javascript
function lerParametros() {
  const p = {};
  for (const id of CONTROLES) {
    const el = $(id);
    if (el.type === 'checkbox') p[id] = el.checked;
    else if (el.type === 'number' || el.type === 'range') p[id] = el.value === '' ? null : Number(el.value);
    else p[id] = el.value;
  }
  return { ...p, ...camposCorrecao() };
}

// Q12: cada correcao liga sozinha quando ha referencia e a regiao dela.
function camposCorrecao() {
  const c = estado.correcao;
  return {
    ...c,
    corrigir_cor: Boolean(c.referencia && c.regiao_cor),
    estabilizar: Boolean(c.referencia && c.regiao_alinhamento),
  };
}
```

Em `aplicarParametros(p)`, troque:

```javascript
  ['zoom', 'pos_x', 'pos_y'].forEach((id) => { $('v-' + id).textContent = $(id).value; });
  desenhar();
}
```

por:

```javascript
  ['zoom', 'pos_x', 'pos_y'].forEach((id) => { $('v-' + id).textContent = $(id).value; });
  // "Voltar aos padroes" nao traz estas chaves e, por isso, mantem a correcao
  if ('referencia' in p || 'regiao_cor' in p || 'regiao_alinhamento' in p) {
    estado.correcao = {
      referencia: p.referencia ?? null,
      regiao_cor: p.regiao_cor ?? null,
      regiao_alinhamento: p.regiao_alinhamento ?? null,
    };
  }
  desenhar();
}
```

- [ ] **Step 6: `app.js`, abrir a sequência**

Em `escolher(seq, projeto)`, troque:

```javascript
  estado.sequencia = { ...seq, projeto: projeto.nome, projetoCaminho: projeto.caminho };
  estado.manifesto = null;
```

por:

```javascript
  estado.sequencia = { ...seq, projeto: projeto.nome, projetoCaminho: projeto.caminho };
  estado.manifesto = null;
  estado.infoCorrecao = null;
  estado.correcao = { referencia: null, regiao_cor: null, regiao_alinhamento: null };
  escolherFerramenta(null);
```

Troque (ainda em `escolher`):

```javascript
  ['btn-gerar', 'btn-salvar', 'btn-padroes'].forEach((b) => { $(b).disabled = true; });
```

por:

```javascript
  ['btn-gerar', 'btn-salvar', 'btn-padroes', 'btn-referencia', 'btn-area-cor', 'btn-area-alinhamento']
    .forEach((b) => { $(b).disabled = true; });
```

Troque:

```javascript
  const salvo = await (await fetch('/api/enquadramento?pasta=' + encodeURIComponent(seq.caminho))).json();
  if (minhaVez !== selecaoAtual) return;
```

por:

```javascript
  const salvo = await (await fetch('/api/enquadramento?pasta=' + encodeURIComponent(seq.caminho))).json();
  estado.nomes = (await (await fetch('/api/fotos?pasta=' + encodeURIComponent(seq.caminho))).json()).nomes;
  if (minhaVez !== selecaoAtual) return;
```

No fim de `garantirCache`, troque:

```javascript
  ['btn-gerar', 'btn-salvar', 'btn-padroes'].forEach((b) => { $(b).disabled = false; });
  trocarQuadro();
}
```

por:

```javascript
  ['btn-gerar', 'btn-salvar', 'btn-padroes', 'btn-referencia', 'btn-area-cor', 'btn-area-alinhamento']
    .forEach((b) => { $(b).disabled = false; });
  trocarQuadro();
  await carregarCorrecao(minhaVez);
}
```

- [ ] **Step 7: `app.js`, trocar quadro e as funções de correção**

No fim de `trocarQuadro()`, troque:

```javascript
  $('rotulo-quadro').textContent = `${indice + 1} / ${estado.manifesto.total_fotos}`;
  // o manifesto traz o id do cache (sha1 do caminho), que e como o servidor o guarda
  $('quadro').src = `/q/${estado.manifesto.id}/q_${String(posicao).padStart(6, '0')}.jpg` + `?v=${estado.manifesto.montado || 0}`;
  desenhar();
}
```

por:

```javascript
  const ehReferencia = estado.nomes[indice] === estado.correcao.referencia;
  $('rotulo-quadro').textContent = `${indice + 1} / ${estado.manifesto.total_fotos}`
    + (ehReferencia ? ' · referência' : '');
  // o manifesto traz o id do cache (sha1 do caminho), que e como o servidor o guarda
  const arquivo = `q_${String(posicao).padStart(6, '0')}.jpg`;
  const info = estado.infoCorrecao;
  $('quadro').src = info && estado.verCorrigido
    ? `/q/${estado.manifesto.id}/corrigido/${arquivo}?v=${info.versao}`
    : `/q/${estado.manifesto.id}/${arquivo}?v=${estado.manifesto.montado || 0}`;
  desenhar();
}

/* ---------- correcao de cor e estabilizacao ---------- */

function desenharRegioes(giro) {
  for (const [id, chave] of [['ret-cor', 'regiao_cor'], ['ret-alinhamento', 'regiao_alinhamento']]) {
    const r = estado.correcao[chave];
    const el = $(id);
    el.hidden = !r;
    if (!r) continue;
    const [x, y, w, h] = regioes.paraTela(giro, r);
    Object.assign(el.style, { left: `${x * 100}%`, top: `${y * 100}%`,
      width: `${w * 100}%`, height: `${h * 100}%` });
  }
  const c = estado.correcao;
  $('dica-referencia').textContent = c.referencia
    ? `Referência: ${c.referencia}` : 'Sem referência: nada é corrigido.';
  $('btn-remover-cor').hidden = !c.regiao_cor;
  $('btn-remover-alinhamento').hidden = !c.regiao_alinhamento;
}

function pintarMarcas() {
  const info = estado.infoCorrecao;
  const alvo = $('marcas');
  alvo.innerHTML = '';
  if (!info || !info.estabilizar || info.total_fotos < 2) return;
  for (const indice of info.falhas) {
    const marca = document.createElement('i');
    marca.style.left = `${(indice / (info.total_fotos - 1)) * 100}%`;
    alvo.appendChild(marca);
  }
}

function mostrarInfoCorrecao(info) {
  estado.infoCorrecao = info;
  $('btn-antes-depois').hidden = !info;
  $('btn-antes-depois').textContent = estado.verCorrigido ? 'Ver antes' : 'Ver depois';
  if (info) {
    const partes = [];
    if (info.cor) partes.push('cor');
    if (info.estabilizar) partes.push(`estabilização (zoom extra ${info.zoom_borda.toFixed(2)}x)`);
    if (info.estabilizar && info.falhas.length) partes.push(`${info.falhas.length} fotos não alinharam`);
    $('estado-correcao').textContent = 'Corrigido: ' + partes.join(' · ');
  }
  pintarMarcas();
  trocarQuadro();
}

// Ao abrir a sequencia: usa a previa corrigida que ja existe, ou calcula.
async function carregarCorrecao(minhaVez) {
  const url = '/api/correcao?pasta=' + encodeURIComponent(estado.sequencia.caminho);
  const dados = await (await fetch(url)).json();
  if (minhaVez !== selecaoAtual) return;
  const c = camposCorrecao();
  if (dados.info) mostrarInfoCorrecao(dados.info);
  else if (dados.estado) await acompanharCorrecao(minhaVez);
  else if (c.corrigir_cor || c.estabilizar) await recalcularCorrecao();
}

async function salvarCorrecao() {
  await fetch('/api/enquadramento/correcao', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pasta: estado.sequencia.caminho, correcao: camposCorrecao() }),
  });
}

// Grava as escolhas (Q4) e pede ao servidor a previa corrigida nova.
async function recalcularCorrecao() {
  const minhaVez = selecaoAtual;
  await salvarCorrecao();
  const c = camposCorrecao();
  mostrarInfoCorrecao(null);
  $('estado-correcao').textContent = '';
  const resposta = await fetch('/api/correcao', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pasta: estado.sequencia.caminho, referencia: c.referencia,
      regiao_cor: c.corrigir_cor ? c.regiao_cor : null,
      regiao_alinhamento: c.estabilizar ? c.regiao_alinhamento : null,
    }),
  });
  const dados = await resposta.json();
  if (!resposta.ok) { $('estado-correcao').textContent = dados.erro; return; }
  if (dados.estado) await acompanharCorrecao(minhaVez);
}

async function acompanharCorrecao(minhaVez) {
  const url = '/api/correcao?pasta=' + encodeURIComponent(estado.sequencia.caminho);
  for (;;) {
    await new Promise((r) => setTimeout(r, 700));
    if (minhaVez !== selecaoAtual) return;
    const dados = await (await fetch(url)).json();
    const e = dados.estado;
    if (e && e.fase === 'erro') { $('estado-correcao').textContent = e.erro; return; }
    if (!e) { mostrarInfoCorrecao(dados.info); return; }
    const conta = e.total ? ` ${e.feitos}/${e.total}` : '';
    $('estado-correcao').textContent = `Correção: ${e.fase}${conta}`;
  }
}

function escolherFerramenta(qual) {
  estado.ferramenta = estado.ferramenta === qual ? null : qual;
  $('btn-area-cor').classList.toggle('ativa', estado.ferramenta === 'cor');
  $('btn-area-alinhamento').classList.toggle('ativa', estado.ferramenta === 'alinhamento');
  $('moldura').classList.toggle('desenhando', Boolean(estado.ferramenta));
}

// Ponto do mouse em coordenadas normalizadas do quadro GIRADO (a caixa #giro).
function pontoNoQuadro(evento) {
  const caixa = $('giro').getBoundingClientRect();
  const limitar = (v) => Math.min(1, Math.max(0, v));
  return [limitar((evento.clientX - caixa.left) / caixa.width),
    limitar((evento.clientY - caixa.top) / caixa.height)];
}

let arrasto = null;

function iniciarArrasto(evento) {
  if (!estado.ferramenta || !estado.manifesto) return;
  evento.preventDefault();
  $('moldura').setPointerCapture(evento.pointerId);
  arrasto = { inicio: pontoNoQuadro(evento), chave: `regiao_${estado.ferramenta}` };
}

function retanguloDoArrasto(evento) {
  const [ax, ay] = arrasto.inicio;
  const [bx, by] = pontoNoQuadro(evento);
  return [Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay)];
}

function moverArrasto(evento) {
  if (!arrasto) return;
  const giro = giroEfetivo(lerParametros());
  estado.correcao[arrasto.chave] = regioes.paraCru(giro, retanguloDoArrasto(evento));
  desenharRegioes(giro);
}

async function terminarArrasto(evento) {
  if (!arrasto) return;
  const [, , w, h] = retanguloDoArrasto(evento);
  const chave = arrasto.chave;
  arrasto = null;
  escolherFerramenta(null);
  if (w < 0.01 || h < 0.01) {  // clique sem arrastar nao vira regiao
    estado.correcao[chave] = null;
    desenhar();
    return;
  }
  if (!estado.correcao.referencia) usarQuadroComoReferencia(false);
  await recalcularCorrecao();
}

function usarQuadroComoReferencia(recalcular = true) {
  const indice = estado.manifesto.indices[Number($('quadro-atual').value)];
  estado.correcao.referencia = estado.nomes[indice];
  trocarQuadro();
  if (recalcular) recalcularCorrecao();
}

function removerRegiao(chave) {
  estado.correcao[chave] = null;
  desenhar();
  recalcularCorrecao();
}
```

A caixa `#giro` já tem o tamanho do quadro **girado**, e só a `<img>` dentro dela é transformada. Por isso o mouse é medido contra `#giro`, e os retângulos são filhos dela, com posição em %: continuam no lugar com qualquer zoom ou tamanho de janela. A conversão para a foto crua acontece só na hora de guardar.

- [ ] **Step 8: `app.js`, fila e botões**

Em `parametrosParaCli(p)`, troque:

```javascript
  if (p.inverter) args.inverter = true;
  return args;
```

por:

```javascript
  if (p.inverter) args.inverter = true;
  if (p.corrigir_cor || p.estabilizar) {
    args.referencia = p.referencia;
    if (p.corrigir_cor) { args.corrigir_cor = true; args.regiao_cor = p.regiao_cor; }
    if (p.estabilizar) { args.estabilizar = true; args.regiao_alinhamento = p.regiao_alinhamento; }
  }
  return args;
```

Troque `$('quadro-atual').addEventListener('input', trocarQuadro);` por:

```javascript
$('quadro-atual').addEventListener('input', trocarQuadro);
$('btn-referencia').onclick = () => usarQuadroComoReferencia();
$('btn-area-cor').onclick = () => escolherFerramenta('cor');
$('btn-area-alinhamento').onclick = () => escolherFerramenta('alinhamento');
$('btn-remover-cor').onclick = () => removerRegiao('regiao_cor');
$('btn-remover-alinhamento').onclick = () => removerRegiao('regiao_alinhamento');
$('btn-antes-depois').onclick = () => {
  estado.verCorrigido = !estado.verCorrigido;
  $('btn-antes-depois').textContent = estado.verCorrigido ? 'Ver antes' : 'Ver depois';
  trocarQuadro();
};
$('moldura').addEventListener('pointerdown', iniciarArrasto);
$('moldura').addEventListener('pointermove', moverArrasto);
$('moldura').addEventListener('pointerup', terminarArrasto);
```

- [ ] **Step 9: Checagens automáticas**

Run: `node --check web/app.js && node --check web/regioes.js && echo ok`
Expected: `ok`

Run: `.venv/bin/python -m pytest -q`
Expected: todos passam.

- [ ] **Step 10: Conferência no navegador (com o painel de verdade)**

Run: `make parar; make iniciar` (agora o painel sobe com a `.venv`).

No navegador, numa sequência real do HD Workflow (por exemplo `ovo`):
1. Arraste o slider até um quadro bom → **Usar este quadro como referência**. O rótulo do quadro mostra `· referência`.
2. **Área para cor** → arraste um retângulo sobre a mesa ou a parede. Aparece em azul, e o texto "Correção: analisando N/T" e depois "aplicando" corre.
3. **Área para alinhar** → arraste sobre uma área parada com textura (lateral da impressora). Aparece tracejado em amarelo.
4. Ao terminar: "Corrigido: cor · estabilização (zoom extra 1.0Xx)". **Ver antes / Ver depois** troca as imagens.
5. Troque **girar** para "não girar": os dois retângulos precisam continuar sobre **os mesmos objetos** (essa é a prova da conversão para a foto crua). Volte para "automático".
6. Recarregue a página e abra a sequência de novo: retângulos e prévia corrigida voltam sem recalcular.
7. **Remover estabilização** → recalcula só a cor; o retângulo amarelo some.
8. **Gerar timelapse** → na fila, o render conclui; abra o MP4.

Confira também que `enquadramento.json` na pasta das fotos tem `referencia`, `regiao_cor` e `regiao_alinhamento`.

- [ ] **Step 11: README de uso**

Em `README.md`, logo antes de `## Instalação`, acrescente:

```markdown
## Correção de cor e estabilização

Quando a luz muda no meio da impressão, ou a câmera leva um esbarrão ou treme, o painel
iguala tudo a **um quadro de referência**:

1. Navegue pelo slider até um quadro bom e clique **Usar este quadro como referência**.
2. **Área para cor**: arraste um retângulo numa área parada e lisa (mesa, parede). A cor é
   medida só ali e corrigida no quadro inteiro.
3. **Área para alinhar**: arraste numa área parada e com textura. O bico, a mesa (que anda
   no eixo Y da A1) e a peça se movem e não servem.
4. Espere a análise (cerca de 40 s para 450 fotos, só na primeira vez) e use **Ver antes /
   Ver depois** para comparar. Marcas vermelhas no slider indicam fotos que não alinharam
   (mão na frente, escuro); elas usam o deslocamento das vizinhas.

A estabilização amplia o mínimo necessário para esconder a borda, além do zoom que você já
escolheu. As fotos originais não mudam; as escolhas ficam no `enquadramento.json` da
sequência.
```

- [ ] **Step 12: Commit**

```bash
git add web/regioes.js web/index.html web/app.js web/estilo.css tests/test_regioes_js.py README.md
git commit -m "Pick the reference and correction areas in the panel, with before/after"
```

---

### Task 9: Destino do render por peça (Adendos 1 e 2 da spec)

O Adendo 1 (03/out) criou o campo Peça e a `pasta_brutos`; o Adendo 2 (04/out) substitui o destino: cada peça tem subpastas por tipo (`roteiro.md`, `timelapse/`, `clipes/`, `fotos/`, `narracao/`), e o render vai para `<pasta_brutos>/<peça>/timelapse/timelapse_<AAAA-MM-DD>.mp4`, a pasta que a skill `montar-reel-em-camadas` lê. No Mac do Lucca, `_brutos` é um **symlink para o iCloud Drive**. `Path.is_dir()` e `mkdir` seguem o link, então nada aqui pode usar `is_symlink()` ou `lstat()` para recusar o caminho. O `painel.json` guarda o caminho **do link**, não o destino: se o iCloud mudar de lugar, basta refazer o link.

Decisões:
- **Mesmo dia, mesma peça (Adendo 2):** a CLI nunca sobrescreve; o segundo render vira `timelapse_<dia>_2.mp4`, `_3`…
- **Regra do nome (Adendo 2, "mesma regra do atalho do iPhone"):** minúsculas, sem acento, espaços (um ou vários) viram um hífen, pontas aparadas, e **o resto fica como está** (`_`, `!`, números), para o painel e o atalho gerarem o mesmo nome. Exceções de segurança: `/` e `:` somem, e pontos no começo também (`..` subiria uma pasta; `.x` ficaria oculta). O resultado exato do atalho para `Ovo de Páscoa_2!` é conferido com o Lucca na Task 10.
- **Quando normaliza:** quando o cursor sai do campo (evento `change`). A cada tecla, o espaço digitado viraria hífen antes da palavra seguinte. Enquanto se digita, a dica já mostra o nome final.
- **Relatório `.fotos.csv`:** sai ao lado do MP4, em `<peça>/timelapse/`, como em todo render; a pasta é só de timelapse, então ele não se mistura com clipes. Na Task 10, conferir que a skill do reel o ignora.

**Files:**
- Create: `web/peca.js`
- Modify: `timelapse/acervo.py` (nova `subpastas`, antes de `listar`)
- Modify: `timelapse/cli.py` (`--nome-saida` aceita `{dia}`; `nome_de_saida` e `caminho_livre` antes de `main`)
- Modify: `timelapse/servidor.py` (`opcoes()`, `/api/config`, `/api/brutos`, `/api/brutos/raiz`; `peca` entra nas chaves mescláveis)
- Modify: `web/index.html`, `web/app.js`, `web/estilo.css`
- Modify: `README.md`, `docs-cli.md`
- Test: `tests/test_destino.py`, `tests/test_peca_js.py`

**Interfaces:**
- Consumes: `POST /api/enquadramento/correcao` e `mesclar_enquadramento` (Task 7); `salvar_opcoes`/`opcoes` (já existem); `aplicarParametros`, `parametrosParaCli`, `enfileirar` (Task 8 e anteriores)
- Produces:
  - `acervo.subpastas(base: Path) -> list[str]`: subpastas ordenadas, sem as que começam com `_` ou `.`, `[]` se a pasta não existe
  - `cli.nome_de_saida(modelo: str, agora: datetime) -> str`: `{data}` → `AAAAMMDD_HHMMSS_ffffff`, `{dia}` → `AAAA-MM-DD`
  - `cli.caminho_livre(saida: Path) -> Path`: o primeiro de `saida`, `<stem>_2`, `<stem>_3`… sem MP4 nem `.fotos.csv`
  - `painel.json`: chave `pasta_brutos` (padrão `""`)
  - `GET /api/config` ganha `pasta_brutos`; `GET /api/brutos` → `{"pasta", "sugestoes": [...]}`; `POST /api/brutos/raiz {caminho}` → mesmo formato, ou 400 `{"erro"}`
  - `enquadramento.json` ganha `peca` (texto já normalizado)
  - `normalizarPeca(texto) -> string` (global no navegador; `module.exports` no Node)

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/test_peca_js.py`:

```python
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
```

Crie `tests/test_destino.py`:

```python
import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import cv2
import numpy as np
import pytest

from timelapse import acervo, ambiente, cli, servidor

RAIZ = Path(__file__).resolve().parent.parent
DIA = datetime(2026, 10, 3, 14, 30)


def test_nome_com_dia(tmp_path):
    assert cli.nome_de_saida('timelapse_{dia}.mp4', DIA) == 'timelapse_2026-10-03.mp4'
    assert cli.nome_de_saida('timelapse_{data}.mp4', DIA).startswith('timelapse_20261003_1430')


def test_segundo_render_do_dia_ganha_sufixo(tmp_path):
    (tmp_path / 'timelapse_2026-10-03.mp4').write_bytes(b'x')
    (tmp_path / 'timelapse_2026-10-03_2.fotos.csv').write_text('x')  # sobra de um render
    livre = cli.caminho_livre(tmp_path / 'timelapse_2026-10-03.mp4')
    assert livre == tmp_path / 'timelapse_2026-10-03_3.mp4'


def test_caminho_livre_nao_mexe_se_esta_livre(tmp_path):
    alvo = tmp_path / 'timelapse_2026-10-03.mp4'
    assert cli.caminho_livre(alvo) == alvo


def test_sugestoes_seguem_symlink(tmp_path):
    real = tmp_path / 'iCloud' / '_brutos'
    for nome in ('ovo', 'caveira-branca', '.oculta', '_arquivo'):
        (real / nome).mkdir(parents=True)
    (real / 'solto.mp4').write_bytes(b'x')
    link = tmp_path / '_brutos'
    link.symlink_to(real, target_is_directory=True)
    assert acervo.subpastas(link) == ['caveira-branca', 'ovo']


def test_sugestoes_de_pasta_que_nao_existe(tmp_path):
    assert acervo.subpastas(tmp_path / 'nada') == []


@pytest.fixture
def painel(tmp_path, monkeypatch):
    # painel.json do teste fica na pasta temporaria, nunca no do projeto
    monkeypatch.setattr(ambiente, 'RAIZ', tmp_path)
    http = ThreadingHTTPServer(('127.0.0.1', 0), servidor.Painel)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{http.server_address[1]}'
    http.shutdown()


def chamar(url, corpo=None):
    dados = None if corpo is None else json.dumps(corpo).encode()
    pedido = Request(url, data=dados, headers={'Content-Type': 'application/json'})
    with urlopen(pedido) as resposta:
        return json.loads(resposta.read())


def test_trocar_brutos_aceita_symlink_e_grava_painel_json(painel, tmp_path):
    real = tmp_path / 'iCloud' / '_brutos'
    (real / 'ovo').mkdir(parents=True)
    link = tmp_path / '_brutos'
    link.symlink_to(real, target_is_directory=True)
    resposta = chamar(painel + '/api/brutos/raiz', {'caminho': str(link)})
    assert resposta == {'pasta': str(link), 'sugestoes': ['ovo']}
    # guarda o link, nao o destino: se o iCloud mudar de lugar, o link continua valendo
    assert json.loads((tmp_path / 'painel.json').read_text())['pasta_brutos'] == str(link)
    assert chamar(painel + '/api/brutos') == {'pasta': str(link), 'sugestoes': ['ovo']}
    assert chamar(painel + '/api/config')['pasta_brutos'] == str(link)


def test_trocar_brutos_recusa_link_quebrado(painel, tmp_path):
    link = tmp_path / '_brutos'
    link.symlink_to(tmp_path / 'sumiu', target_is_directory=True)
    with pytest.raises(HTTPError) as erro:
        chamar(painel + '/api/brutos/raiz', {'caminho': str(link)})
    assert erro.value.code == 400


def test_peca_e_salva_no_enquadramento(painel, tmp_path):
    (tmp_path / 'enquadramento.json').write_text(json.dumps({'zoom': 1.2}))
    chamar(painel + '/api/enquadramento/correcao',
           {'pasta': str(tmp_path), 'correcao': {'peca': 'ovo-de-pascoa'}})
    salvo = json.loads((tmp_path / 'enquadramento.json').read_text())
    assert salvo == {'zoom': 1.2, 'peca': 'ovo-de-pascoa'}


def test_render_vai_para_brutos_da_peca(tmp_path):
    try:
        cli.find_ffmpeg()
    except ValueError:
        pytest.skip('ffmpeg indisponivel')
    fotos = tmp_path / 'fotos'
    fotos.mkdir()
    for i in range(3):
        cv2.imwrite(str(fotos / f'IMG_{i}.jpg'), np.full((40, 60, 3), i * 60, np.uint8))
    real = tmp_path / 'iCloud' / '_brutos'
    real.mkdir(parents=True)
    link = tmp_path / '_brutos'
    link.symlink_to(real, target_is_directory=True)

    def render():
        return subprocess.run(
            [sys.executable, '-m', 'timelapse.cli', str(fotos), '--sem-config',
             '--pasta-saida', str(link / 'ovo' / 'timelapse'),
             '--nome-saida', 'timelapse_{dia}.mp4'],
            capture_output=True, text=True, cwd=RAIZ, env=os.environ)

    hoje = datetime.now().strftime('%Y-%m-%d')
    primeiro, segundo = render(), render()
    assert primeiro.returncode == 0, primeiro.stderr
    assert segundo.returncode == 0, segundo.stderr
    # <peca>/ e timelapse/ foram criadas dentro do destino real do link
    assert (real / 'ovo' / 'timelapse' / f'timelapse_{hoje}.mp4').is_file()
    assert (real / 'ovo' / 'timelapse' / f'timelapse_{hoje}_2.mp4').is_file()
```

Os testes do servidor trocam `ambiente.RAIZ` por uma pasta temporária, porque `salvar_opcoes` grava em `ambiente.RAIZ / "painel.json"`. Sem isso, o teste sobrescreveria o `painel.json` real do projeto.

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_destino.py tests/test_peca_js.py -q`
Expected: `17 failed`. Causas: `AttributeError` (`nome_de_saida`, `caminho_livre`, `subpastas`), rotas inexistentes (404 em vez de 400 ou 200), `peca` ignorada pelo merge e `Cannot find module .../web/peca.js`.

- [ ] **Step 3: `web/peca.js`**

```javascript
'use strict';

// O campo Peca vira o nome de uma subpasta de _brutos/: "Ovo de Páscoa" -> "ovo-de-pascoa".
// Mesma regra do atalho do iPhone: minusculas, sem acento, espacos viram hifen; o resto fica.
function normalizarPeca(texto) {
  return String(texto)
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[/:]/g, '')  // quebrariam o caminho
    .trim()
    .replace(/\s+/g, '-')
    .replace(/^\.+/, '');  // ".." subiria uma pasta; ".x" ficaria oculta
}

if (typeof module !== 'undefined') module.exports = { normalizarPeca };
```

O `normalize('NFD')` separa cada letra do acento (`ç` vira `c` + cedilha), e o `replace` seguinte apaga só os acentos.

- [ ] **Step 4: `acervo.subpastas`**

Em `timelapse/acervo.py`, logo antes de `def listar(base: Path) -> list[dict]:`, acrescente:

```python
def subpastas(base: Path) -> list[str]:
    """Nomes das subpastas de _brutos/, uma por peca. Pula as que comecam com _ ou .

    Segue symlink: no Mac, _brutos e um link para o iCloud Drive.
    """
    try:
        return sorted(p.name for p in base.iterdir()
                      if p.is_dir() and not p.name.startswith(("_", ".")))
    except OSError:
        return []


```

- [ ] **Step 5: `{dia}` e nome livre na CLI**

Em `timelapse/cli.py`, troque:

```python
    parser.add_argument('--nome-saida', help='Nome do MP4; {data} insere data/hora única.')
```

por:

```python
    parser.add_argument('--nome-saida',
                        help='Nome do MP4; {data} insere data/hora única; {dia} insere AAAA-MM-DD.')
```

Logo antes de `def main():`, acrescente:

```python
def nome_de_saida(modelo, agora):
    """{data} vira data e hora únicas; {dia} vira AAAA-MM-DD, o nome que o _brutos usa."""
    return (modelo.replace('{data}', agora.strftime('%Y%m%d_%H%M%S_%f'))
            .replace('{dia}', agora.strftime('%Y-%m-%d')))


def caminho_livre(saida):
    """Segundo render no mesmo dia: timelapse_<dia>_2.mp4, _3... Nunca sobrescreve."""
    candidato, numero = saida, 2
    while candidato.exists() or candidato.with_suffix('.fotos.csv').exists():
        candidato = saida.with_name(f'{saida.stem}_{numero}{saida.suffix}')
        numero += 1
    return candidato


```

Em `main()`, troque:

```python
    name = args.nome_saida.replace('{data}', datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output = (args.saida or destination / name).expanduser().resolve()
```

por:

```python
    name = nome_de_saida(args.nome_saida, datetime.now())
    output = (args.saida or destination / name).expanduser().resolve()
    if not args.saida and '{dia}' in args.nome_saida:
        output = caminho_livre(output)
```

`<peça>/` e `timelapse/` já são criadas pelo `output.parent.mkdir(parents=True, exist_ok=True)` que existe em `main()`. O `.resolve()` segue o symlink, e o MP4 cai no iCloud de verdade. `--saida` explícito continua com a regra antiga: se o arquivo existe, dá erro.

- [ ] **Step 6: Servidor**

Em `timelapse/servidor.py`, em `opcoes()`, troque:

```python
    padrao = {"acervo": "", "porta": 8765, "limite_cache": 300, "lado_cache": 1050}
```

por:

```python
    padrao = {"acervo": "", "porta": 8765, "limite_cache": 300, "lado_cache": 1050,
              "pasta_brutos": ""}
```

Troque:

```python
CHAVES_CORRECAO = ("referencia", "regiao_cor", "regiao_alinhamento", "corrigir_cor", "estabilizar")
```

por:

```python
# Chaves que o painel grava sozinho no enquadramento.json, sem o botao Salvar.
CHAVES_MESCLAVEIS = ("referencia", "regiao_cor", "regiao_alinhamento", "corrigir_cor",
                     "estabilizar", "peca")
```

e, na rota `/api/enquadramento/correcao`, troque:

```python
            novos = {k: v for k, v in dados["correcao"].items() if k in CHAVES_CORRECAO}
```

por:

```python
            novos = {k: v for k, v in dados["correcao"].items() if k in CHAVES_MESCLAVEIS}
```

Em `/api/config`, troque:

```python
                               "limite_cache": cfg["limite_cache"],
```

por:

```python
                               "limite_cache": cfg["limite_cache"],
                               "pasta_brutos": cfg["pasta_brutos"],
```

Em `do_GET`, troque `        if rota == "/api/fotos":` por:

```python
        if rota == "/api/brutos":
            base = opcoes()["pasta_brutos"]
            return self._json({"pasta": base,
                               "sugestoes": acervo.subpastas(Path(base)) if base else []})

        if rota == "/api/fotos":
```

Em `do_POST`, troque `        if rota == "/api/enquadramento/correcao":` por:

```python
        if rota == "/api/brutos/raiz":
            caminho = Path(dados["caminho"]).expanduser()
            # is_dir segue o link: no Mac, _brutos e um symlink para o iCloud Drive.
            # Grava o caminho do link, que continua valendo se o iCloud mudar de lugar.
            if not caminho.is_dir():
                return self._json({"erro": f"Não é uma pasta: {caminho}"}, 400)
            salvar_opcoes({"pasta_brutos": str(caminho)})
            return self._json({"pasta": str(caminho), "sugestoes": acervo.subpastas(caminho)})

        if rota == "/api/enquadramento/correcao":
```

- [ ] **Step 7: Rodar os testes do backend**

Run: `.venv/bin/python -m pytest tests/test_destino.py tests/test_peca_js.py -q`
Expected: `17 passed`

- [ ] **Step 8: Painel, HTML e CSS**

Em `web/index.html`, troque `    <div class="acoes">` por:

```html
    <h2>Destino</h2>
    <div class="campo">
      <label for="peca">peça</label>
      <input type="text" id="peca" list="pecas" spellcheck="false" autocomplete="off" placeholder="ex.: ovo-de-pascoa">
      <datalist id="pecas"></datalist>
      <p class="dica dica-fixa" id="dica-destino">Sem peça: o vídeo vai para render/ do projeto.</p>
    </div>
    <div class="campo">
      <label for="pasta-brutos">pasta _brutos</label>
      <input type="text" id="pasta-brutos" spellcheck="false" placeholder="…/02_Marketing_Conteudo/_brutos">
      <div class="raiz-acoes"><button id="btn-trocar-brutos" class="secundario" type="button">Trocar pasta</button></div>
      <p id="aviso-brutos" class="dica"></p>
    </div>

    <div class="acoes">
```

Troque `<script src="/web/regioes.js"></script>` por:

```html
<script src="/web/regioes.js"></script>
<script src="/web/peca.js"></script>
```

O `<datalist>` é o jeito nativo do navegador de sugerir valores num campo de texto: mostra as subpastas existentes e ainda deixa digitar uma peça nova.

Em `web/estilo.css`, troque `/* raiz do acervo */` por:

```css
/* destino por peca: mesma cara do campo da raiz do acervo */
#pasta-brutos { font-family:var(--mono); font-size:11px; }

/* raiz do acervo */
```

- [ ] **Step 9: Painel, `app.js`**

Troque `  'nome_saida', 'inverter'];` por:

```javascript
  'nome_saida', 'inverter', 'peca'];
```

(Com `peca` em `CONTROLES`, o botão **Salvar enquadramento** grava a peça e `aplicarParametros` a carrega do `enquadramento.json`. Como `parametrosParaCli` monta os argumentos um a um, `--peca` nunca chega à CLI.)

Troque:

```javascript
  nomes: [], infoCorrecao: null, verCorrigido: true, ferramenta: null };
```

por:

```javascript
  nomes: [], infoCorrecao: null, verCorrigido: true, ferramenta: null, pastaBrutos: '' };
```

Em `carregarAcervo()`, troque:

```javascript
  desenharRecentes(cfg.recentes || []);
```

por:

```javascript
  desenharRecentes(cfg.recentes || []);
  estado.pastaBrutos = cfg.pasta_brutos || '';
  $('pasta-brutos').value = estado.pastaBrutos;
  carregarSugestoes();
```

Em `escolher()`, troque:

```javascript
  estado.correcao = { referencia: null, regiao_cor: null, regiao_alinhamento: null };
  escolherFerramenta(null);
```

por:

```javascript
  estado.correcao = { referencia: null, regiao_cor: null, regiao_alinhamento: null };
  escolherFerramenta(null);
  $('peca').value = '';  // a peca e da sequencia: nao herda a da anterior
```

e troque:

```javascript
  aplicarParametros({ ...padroesDaSequencia(), ...(salvo.salvo || {}) });
```

por:

```javascript
  aplicarParametros({ ...padroesDaSequencia(), ...(salvo.salvo || {}) });
  atualizarDestino();
```

Em `enfileirar()`, troque:

```javascript
  const args = parametrosParaCli(p);
  const base = seq.nome.replace(/^fotos-?/, '') || seq.projeto;
  args['pasta_saida'] = seq.projetoCaminho + '/render';
  args['nome_saida'] = p.nome_saida.replace('{peca}', base.replace(/[^\w-]/g, '_'));
```

por:

```javascript
  const args = parametrosParaCli(p);
  const peca = normalizarPeca(p.peca || '');
  if (peca) {
    if (!estado.pastaBrutos) { $('aviso').textContent = 'Escolha a pasta _brutos antes de usar a peça.'; return; }
    // _brutos/<peca>/timelapse/timelapse_<AAAA-MM-DD>.mp4; a CLI cria as pastas e poe _2 se o dia repetir
    args['pasta_saida'] = `${estado.pastaBrutos}/${peca}/timelapse`;
    args['nome_saida'] = 'timelapse_{dia}.mp4';
  } else {
    const base = seq.nome.replace(/^fotos-?/, '') || seq.projeto;
    args['pasta_saida'] = seq.projetoCaminho + '/render';
    args['nome_saida'] = p.nome_saida.replace('{peca}', base.replace(/[^\w-]/g, '_'));
  }
```

Troque `/* ---------- fila ---------- */` por:

```javascript
/* ---------- destino por peca ---------- */

async function carregarSugestoes() {
  const dados = await (await fetch('/api/brutos')).json();
  $('pecas').innerHTML = '';
  for (const nome of dados.sugestoes) {
    const opcao = document.createElement('option');
    opcao.value = nome;
    $('pecas').appendChild(opcao);
  }
}

async function trocarBrutos() {
  $('aviso-brutos').textContent = 'Lendo…';
  const resposta = await fetch('/api/brutos/raiz', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ caminho: $('pasta-brutos').value.trim() }),
  });
  const dados = await resposta.json();
  if (!resposta.ok) { $('aviso-brutos').textContent = dados.erro; return; }
  $('aviso-brutos').textContent = '';
  estado.pastaBrutos = dados.pasta;
  $('pasta-brutos').value = dados.pasta;
  await carregarSugestoes();
  atualizarDestino();
}

function atualizarDestino() {
  const peca = normalizarPeca($('peca').value);
  $('dica-destino').textContent = !peca
    ? 'Sem peça: o vídeo vai para render/ do projeto.'
    : `Vai para _brutos/${peca}/timelapse/timelapse_<data>.mp4`;
}

// Ao sair do campo: normaliza e grava no enquadramento.json da sequencia.
async function confirmarPeca() {
  $('peca').value = normalizarPeca($('peca').value);
  atualizarDestino();
  if (!estado.sequencia) return;
  await fetch('/api/enquadramento/correcao', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pasta: estado.sequencia.caminho, correcao: { peca: $('peca').value } }),
  });
}

/* ---------- fila ---------- */
```

Troque `$('btn-gerar').onclick = enfileirar;` por:

```javascript
$('btn-gerar').onclick = enfileirar;
$('peca').addEventListener('input', atualizarDestino);
$('peca').addEventListener('change', confirmarPeca);
$('btn-trocar-brutos').onclick = trocarBrutos;
$('pasta-brutos').addEventListener('keydown', (e) => { if (e.key === 'Enter') trocarBrutos(); });
```

- [ ] **Step 10: Checagens automáticas**

Run: `node --check web/app.js && node --check web/peca.js && echo ok`
Expected: `ok`

Run: `.venv/bin/python -m pytest -q`
Expected: todos passam (74 no total, contando os 5 de `test_recorte.py`).

Run: `.venv/bin/ruff check tests/test_destino.py tests/test_peca_js.py`
Expected: `All checks passed!` E nenhum erro de ruff **novo** em `acervo.py`, `cli.py` ou `servidor.py` (compare com `git stash` se tiver dúvida: a contagem antiga desses arquivos se mantém).

- [ ] **Step 11: Conferência no navegador**

`make parar; make iniciar`, e então:
1. Em **pasta _brutos**, cole o caminho do link (`…/Em camadas 3D/02_Marketing_Conteudo/_brutos`) → **Trocar pasta**. Não pode aparecer erro, mesmo sendo symlink. O `painel.json` ganha `pasta_brutos` com o caminho do link.
2. No campo **peça**, as subpastas existentes aparecem como sugestão, sem as que começam com `_`.
3. Digite `Ovo de Páscoa` e tecle Tab: o campo vira `ovo-de-pascoa`, e a dica mostra `Vai para _brutos/ovo-de-pascoa/timelapse/timelapse_<data>.mp4`.
4. Troque de sequência e volte: a peça reaparece, porque está no `enquadramento.json`. Uma sequência sem peça abre com o campo vazio.
5. **Gerar timelapse** duas vezes: aparecem `timelapse_<hoje>.mp4` e `timelapse_<hoje>_2.mp4` em `<peça>/timelapse/`, visíveis no Finder pelo iCloud.
6. Apague a peça e gere de novo: o vídeo volta para `render/` do projeto, com o nome de sempre.

- [ ] **Step 12: Documentação**

Em `README.md`, na tabela de `painel.json`, logo depois da linha `| `largura_cache` | largura, em pixels, de cada quadro do cache |`, acrescente:

```markdown
| `pasta_brutos` | pasta `_brutos/` do marketing; com o campo Peça preenchido, o render vai para `_brutos/<peça>/timelapse/timelapse_<AAAA-MM-DD>.mp4`. Pode ser um symlink (o do Mac aponta para o iCloud Drive) |
```

Em `docs-cli.md`, na tabela do `config.json`, troque a célula de significado de `nome_saida`, de `` `{data}` vira data/hora única. Um nome fixo é permitido, mas nunca é sobrescrito. `` para:

```markdown
`{data}` vira data/hora única; `{dia}` vira `AAAA-MM-DD` e, se o arquivo já existir, ganha `_2`, `_3`… Um nome fixo é permitido, mas nunca é sobrescrito.
```

- [ ] **Step 13: Commit**

```bash
git add web/peca.js web/index.html web/app.js web/estilo.css timelapse/acervo.py timelapse/cli.py timelapse/servidor.py tests/test_destino.py tests/test_peca_js.py README.md docs-cli.md
git commit -m "Send renders to the piece's folder in _brutos"
```

---

### Task 10: Validação com o Lucca e revisão final

Esta task não tem código: confere o resultado com fotos reais e passa o branch inteiro por um revisor.

- [ ] **Step 1: Sequência com mudança de luz.** No painel, escolha uma sequência do HD Workflow com trechos escuros ou azulados. Marque referência + área de cor, compare antes/depois em 5 pontos do slider e gere o MP4. Anote se algum trecho ficou estourado (o teto de 2× deveria impedir).
- [ ] **Step 2: Sequência com esbarrão.** Se nenhuma existir, simule: durante uma captura curta, desloque a câmera de leve no meio. Marque a área de alinhar, confira que o salto some no antes/depois e que as marcas vermelhas só aparecem onde há mão ou escuro de verdade.
- [ ] **Step 3: Calibrar se preciso.** Se fotos boas forem marcadas como falha, o primeiro ajuste é `CORRELACAO_MINIMA` em `timelapse/correcao.py` (0.85 → 0.75). Se a cor "pular" num quadro com mão na região, o ajuste é `DESVIO_OUTLIER` (0.12 → 0.08). Qualquer mudança vem acompanhada de um teste em `tests/test_correcao_*.py` com o caso real reproduzido sinteticamente.
- [ ] **Step 4: Destino por peça.** Com a peça preenchida numa sequência real, confira o MP4 em `_brutos/<peça>/timelapse/` pelo Finder e pelo iPhone (iCloud), que a skill `montar-reel-em-camadas` acha o arquivo e ignora o `.fotos.csv`, e que o atalho do iPhone gera o mesmo nome que o painel para `Ovo de Páscoa_2!` (se não gerar, ajustar `normalizarPeca` e o teste).
- [ ] **Step 5: Render antigo intacto.** Renderize uma sequência **sem** referência e compare com um MP4 antigo da mesma pasta e dos mesmos parâmetros: mesma duração, mesmo enquadramento.
- [ ] **Step 6: Revisão do branch inteiro por um subagente revisor** (regra do CLAUDE.md), contra a spec e este plano. Achados confirmados viram correção com teste antes do merge.

---

## Self-review

- **Cobertura da spec:** Q1/Q9/Q10 → Task 2; Q2 → `regiao_cor` em Tasks 4 e 8; Q3/Q15 → uma `referencia` compartilhada; Q4 → render por pipe (Task 6) e `enquadramento.json` (Tasks 7 e 8); Q5/Q23 → antes/depois (Task 8); Q6/Q19 → Task 1; Q7 → `fora_da_curva` + medição zerada (Tasks 2 e 4); Q8 → `suavizar` (Task 2); Q11 → `escala_necessaria` (Task 6); Q12/Q20 → `camposCorrecao` + DEFAULTS falsos (Tasks 5 e 8); Q13/Q14/Q21 → `alinhar` contra a referência fixa, euclidiana, sem suavização (Task 3); Q16 → `regiao_alinhamento` (Tasks 3, 4 e 8); Q17 → `zoom_borda` (Task 3) somado ao zoom do usuário via `video_filter` (Task 6); Q18 → `interpolar` + `falhas` + marcas no slider (Tasks 4, 7 e 8); Q22 → fora de escopo, nada a fazer. Adendos 1 e 2 → Task 9: Peça normalizada como no atalho (`normalizarPeca`), sugestões sem `_`/`.` (`acervo.subpastas`), `pasta_brutos` editável e aceitando symlink (`/api/brutos/raiz`), destino `<peça>/timelapse/timelapse_<dia>.mp4` com as pastas criadas e `_2`/`_3` (`{dia}` + `caminho_livre`), Peça no `enquadramento.json` (`CONTROLES` e `CHAVES_MESCLAVEIS`).
- **Desvio consciente do "desenho sugerido":** a spec admite que o zoom de borda passe pelo `video_filter()`. Aqui ele entra no `warpAffine` do Python, e por isso o `video_filter`, o espelho JS e o `test_recorte.py` ficam intocados. O *o quê* (Q17) não muda; muda só o *como*, que a spec deixa livre.
- **Tipos consistentes:** `analise["quadros"][nome]` tem `theta`/`tx`/`ty`/`ganho`/`falhou_alinhamento`/`cor_substituida` em todas as tasks; regiões são sempre `[x, y, w, h]` em listas de float; `info.falhas` são índices na pasta inteira (0-based), que o JS divide por `total_fotos - 1`.
