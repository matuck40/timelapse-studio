# Publicar o repositório: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `matuck40/timelapse-studio` público, com CI verde (ruff, pytest em 3.11/3.12/3.13, gitleaks), sem configuração pessoal no versionamento e com README em inglês que só afirma o que o código faz.

**Architecture:** Nenhuma mudança de comportamento do produto. Mudanças em volta do código: `.gitignore`, arquivos `*.example.json`, formatação ruff, dependências fixadas num arquivo de restrições, um workflow do GitHub Actions e o README. Tudo numa branch nova, `publicar-repositorio`, com PR para a `main`.

**Tech Stack:** Python 3.11+, pytest, ruff 0.16.10, FFmpeg, Node (dois testes JS, pulados sem ele), GitHub Actions, gitleaks, `gh`.

**Spec:** `docs/BRIEFING-publico.md` (local, fora do git) e o pedido do Lucca de 17/10/2026, reproduzido nas tarefas abaixo.

## Global Constraints

- Não apagar arquivos, sem force push, sem `reset --hard`, sem reescrever histórico.
- Todo `git push` pede ok explícito do Lucca. `gh repo edit --visibility public` só com ok explícito, como última tarefa.
- Se a varredura do histórico (Task 4) achar qualquer coisa: PARAR e mostrar ao Lucca. Nada de `filter-repo`, `rebase` ou `amend` em commit já existente.
- Commits pequenos, mensagem em inglês, terminando com as linhas de atribuição da sessão.
- README, código novo e commits em inglês. Conversa com o Lucca em português, curta, sem travessão.
- README: nenhuma frase sem conferência no código; nenhum número que não foi contado (ex.: contagem de testes vem da saída do pytest).
- Actions fixadas por SHA de commit, com a tag em comentário.
- Dependências com versão exata (arquivo de restrições).

## Review Focus

1. **Clone limpo sem `painel.json`/`config.json`:** painel e CLI sobem com os padrões. Test: `test_opcoes_sem_painel_json_usa_padroes` (Task 3).
2. **Exemplo copiado vira configuração válida:** `cp config.example.json config.json` não faz a CLI recusar chave desconhecida. Test: `test_config_example_so_tem_chaves_conhecidas` (Task 3).
3. **Restrições não instalam em 3.11:** numpy 2.5.x pode exigir Python mais novo. Verificação com `pip download --python-version` (Task 5) antes de abrir o PR.
4. **Runner Linux sem FFmpeg ou sem Node:** testes de FFmpeg quebram, os de JS pulam calados. CI instala os dois e o passo de testes confere que nada foi pulado (Task 6).
5. **Servidor exposto na rede:** o README promete 127.0.0.1. Test: `test_servidor_escuta_so_em_loopback` (Task 3).

---

### Task 1: Diagnóstico (só leitura)

**Files:** nenhum.

- [ ] **Step 1: Estado e grafo**

Run: `git status && git log --oneline --all --graph`
Esperado (medido em 17/10): branch `correcao-estabilizacao`, 14 commits à frente da `main` (`40dccdf`), nenhum atrás; branch nunca enviada ao remoto; `painel.json` modificado; `.claude/`, `CLAUDE.md`, `docs/BRIEFING-publico.md` não rastreados.

- [ ] **Step 2: O que a branch faz**

Run: `git log --oneline main..correcao-estabilizacao && git diff --stat main...correcao-estabilizacao | tail -1`
Esperado: 14 commits, 29 arquivos, cerca de +5569/−53. Conteúdo: correção de cor por referência em espaço linear, estabilização ORB + ECC, prévia corrigida no painel, render por pipe, destino por peça em `_brutos`.

- [ ] **Step 3: Testes e lint na branch**

Run: `.venv/bin/python -m pytest -q | tail -1; .venv/bin/python -m ruff check . --statistics; .venv/bin/python -m ruff format --check . | tail -1`
Esperado (medido): `81 passed`; ruff check com 42 erros (41 E501, 1 I001); 18 arquivos a reformatar (inclui blocos Python dentro de `docs/**/*.md`).

- [ ] **Step 4: Está terminada?**

Run: `grep -c '\- \[ \]' docs/superpowers/plans/2026-10-03-correcao-estabilizacao.md; grep -n '^### Task' docs/superpowers/plans/2026-10-03-correcao-estabilizacao.md`
Esperado: Tasks 1 a 9 têm commit correspondente; a Task 10 (validação manual com fotos reais e revisão do branch inteiro) não tem marca. Os 4 últimos commits são correções de uso real.

- [ ] **Step 5: Relatar ao Lucca** o resultado e a decisão (a). Nada é escrito até a resposta.

### Task 2: Branch de trabalho

**Files:** nenhum de código.

Depende da decisão (a):
- **Opção A (recomendada), mesclar junto:** `git switch -c publicar-repositorio correcao-estabilizacao`. O PR da Task 9 leva os 14 commits da correção e os desta publicação.
- **Opção B, publicar só a main:** `git switch -c publicar-repositorio main`. O `painel.json` modificado precisa de `git stash` antes (pedir ok). O README da Task 7 então não descreve correção de cor nem estabilização, porque elas não existem na `main`.

- [ ] **Step 1: Criar a branch conforme a opção escolhida.** O `painel.json` modificado vai junto no working tree (opção A).

Run: `git branch --show-current`
Esperado: `publicar-repositorio`.

- [ ] **Step 2: Commitar este plano**

```bash
git add docs/superpowers/plans/2026-10-18-publicar-repositorio.md
git commit -m "Add the plan for publishing the repository"
```

### Task 3: Configuração local fora do versionamento

**Files:**
- Modify: `.gitignore`
- Create: `painel.example.json`, `config.example.json`
- Untrack (sem apagar do disco): `painel.json`, `config.json`
- Test: `tests/test_config_local.py`

**Interfaces:**
- Consumes: `timelapse.servidor.opcoes() -> dict`, `timelapse.servidor.padroes_cli() -> dict`, `timelapse.cli.DEFAULTS: dict`, `timelapse.ambiente.RAIZ: Path`.
- Produces: `painel.example.json` com as chaves `acervo`, `porta`, `limite_cache`, `lado_cache`, `pasta_brutos`, `recentes`; `config.example.json` igual ao `config.json` atual (já é genérico, conferido em 17/10).

Diagnóstico já medido: `painel.json` tem `/Volumes/WorkFlow/00_Em_Camadas` (commitado) e `pasta_brutos` com `/Users/luccamatuck/...` (só no working tree). `config.json` não tem caminho pessoal, mas sai do git do mesmo jeito, porque o painel grava nele e cada máquina tem o seu. `opcoes()` e a CLI já funcionam sem os arquivos (usam padrões).

- [ ] **Step 1: Escrever os testes**

`tests/test_config_local.py`, usando `monkeypatch.setattr(ambiente, "RAIZ", tmp_path)` e `monkeypatch.delenv` para `TIMELAPSE_ACERVO`/`TIMELAPSE_PORTA`:

```python
def test_opcoes_sem_painel_json_usa_padroes(...):
    assert servidor.opcoes() == {"acervo": "", "porta": 8765, "limite_cache": 300,
                                 "lado_cache": 1050, "pasta_brutos": ""}

def test_painel_example_carrega_e_nao_tem_caminho_pessoal(...):
    # copia painel.example.json da raiz real para tmp_path/painel.json
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
```

O último é um teste de texto de propósito: subir o servidor no teste exigiria porta livre e thread; o que se quer fixar é que ninguém troque o endereço sem o teste reclamar.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_config_local.py -v`
Esperado: os dois testes de exemplo falham com `FileNotFoundError`; os outros dois passam (fixam comportamento existente).

- [ ] **Step 3: Criar os exemplos.** `painel.example.json`: `acervo` `"/path/to/your/prints"`, `pasta_brutos` `""`, `recentes` `[]`, demais com os padrões de `opcoes()`. `config.example.json`: cópia do `config.json`.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_config_local.py -v`
Esperado: 4 passed.

- [ ] **Step 5: Tirar do git e ignorar.** Acrescentar ao `.gitignore`, numa seção `# configuracao local (copie de *.example.json)`: `painel.json`, `config.json`. Numa seção `# ferramentas locais`: `.claude/`, `CLAUDE.md`, `docs/BRIEFING-publico.md`, `.superpowers/`.

Run: `git rm --cached painel.json config.json && ls painel.json config.json && git status --short`
Esperado: os dois arquivos continuam no disco; status mostra `D` (staged) para eles, `A` para os exemplos e nada de `.claude/`, `CLAUDE.md` ou do briefing.

- [ ] **Step 6: Suíte inteira**

Run: `.venv/bin/python -m pytest -q | tail -1`
Esperado: `85 passed`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore painel.example.json config.example.json tests/test_config_local.py
git commit -m "Keep machine-specific settings out of git and ship example files"
```

### Task 4: Varredura de segurança do histórico inteiro (portão)

**Files:** nenhum. Saída em `$SCRATCH/varredura/` (scratchpad da sessão).

- [ ] **Step 1: gitleaks**

Run: `gitleaks detect --source . --log-opts="--all" --redact -v --report-path "$SCRATCH/varredura/gitleaks.json"`
Esperado para seguir: `no leaks found`, saída 0.

- [ ] **Step 2: Dados pessoais no histórico**

Run:
```bash
git log -p --all | grep -nIE '/Users/|/Volumes/|Mobile Documents|iCloud|luccamatuck|@[a-z0-9-]+\.(com|br)|\(?\+?55\)? ?[0-9]{2} ?9?[0-9]{4}-?[0-9]{4}' > "$SCRATCH/varredura/pessoal.txt"; wc -l "$SCRATCH/varredura/pessoal.txt"
git log --all --format='%an <%ae>' | sort -u
```
Mais uma busca por nomes de peça e de cliente: `git log -p --all | grep -niE 'em.camadas|cliente|pedido'`.

Já se sabe que vai aparecer: `/Volumes/WorkFlow/00_Em_Camadas` no `painel.json` commitado e no README, menções a iCloud em comentários e testes, e o e-mail de autor dos commits.

- [ ] **Step 3: Classificar os achados** com arquivo, commit e linha, em: segredo (gitleaks), token/senha, dado de cliente, caminho pessoal, e-mail/autor, nome de marca/peça. Decisão do Lucca (18/10): `/Volumes/WorkFlow/00_Em_Camadas`, outros caminhos pessoais desse tipo e o e-mail de autor são aceitáveis; ficam registrados na descrição do PR e a execução segue. **PARAR e mostrar ao Lucca só se aparecer segredo, token, senha ou dado de cliente.** Sem reescrever histórico em nenhum caso.

### Task 5: Lint verde e dependências fixadas

**Files:**
- Modify: `pyproject.toml` (`[tool.ruff] extend-exclude = ["docs"]`; `dev = ["pytest==9.1.1", "ruff==0.16.10"]`)
- Create: `requirements-dev.txt` (restrições com versão exata)
- Modify: os 17 arquivos `.py` que o `ruff format` mudar, e as linhas E501 que sobrarem
- Modify: `Makefile` (`setup` passa `-c requirements-dev.txt`)

`docs` sai do ruff porque são planos com trechos de código, não código do pacote. As 41 linhas longas: primeiro `ruff format`, depois quebrar à mão o que sobrar. Não aumentar `line-length`.

- [ ] **Step 1: Formatar** e commitar só formatação, para o diff do revisor ficar legível.

Run: `.venv/bin/python -m ruff format . && .venv/bin/python -m pytest -q | tail -1`
Esperado: `85 passed`.

```bash
git commit -am "Apply ruff format"
```

- [ ] **Step 2: Corrigir o resto**

Run: `.venv/bin/python -m ruff check --fix . && .venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .`
Esperado: `All checks passed!` e `files already formatted`. Testes de novo: `85 passed`.

- [ ] **Step 3: Restrições.** `requirements-dev.txt` = saída de `.venv/bin/pip freeze --exclude-editable` (numpy 2.5.3, opencv-python 5.0.0.93, pillow 12.3.0, pytest 9.1.1, ruff 0.16.10 e dependências).

- [ ] **Step 4: Conferir que instala nas três versões**

Run: `for v in 3.11 3.12 3.13; do pip download -q --only-binary=:all: --python-version $v --platform manylinux2014_x86_64 -r requirements-dev.txt -d "$SCRATCH/dl-$v" && echo "$v ok"; done`
Esperado: `3.11 ok`, `3.12 ok`, `3.13 ok`. Se 3.11 falhar (numpy recente pode exigir Python mais novo): parar e perguntar ao Lucca entre fixar a última numpy compatível com 3.11 ou subir `requires-python` para 3.12 e tirar 3.11 da matriz.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements-dev.txt Makefile timelapse tests
git commit -m "Make ruff pass and pin development dependencies"
```

### Task 6: CI

**Files:** Create: `.github/workflows/ci.yml`

Desenho:
- Gatilhos: `push` e `pull_request`. `permissions: contents: read`.
- Job `test`, `ubuntu-24.04`, matriz `python-version: ["3.11", "3.12", "3.13"]`: checkout, setup-python, `sudo apt-get update && sudo apt-get install -y ffmpeg`, setup-node (Node 22), `pip install -c requirements-dev.txt -e '.[dev]'`, `ruff check .`, `ruff format --check .`, `pytest -q -rs`, e um passo que falha se a saída do pytest tiver `skipped` (os testes JS pulam calados sem Node).
- Job `gitleaks`: checkout com `fetch-depth: 0`, `gitleaks/gitleaks-action` (conta pessoal, sem licença), `GITHUB_TOKEN` do próprio workflow.
- Actions fixadas por SHA. Para cada uma: `gh api repos/<dono>/<action>/commits/<tag> --jq .sha` (`actions/checkout` v4, `actions/setup-python` v5, `actions/setup-node` v4, `gitleaks/gitleaks-action` v2), SHA no `uses:` e `# vX.Y.Z` ao lado.

- [ ] **Step 1: Escrever o workflow.**

- [ ] **Step 2: Validar a sintaxe localmente**

Run: `ruby -ryaml -e 'YAML.load_file(".github/workflows/ci.yml"); puts "yaml ok"'` e `grep -E 'uses: .+@[0-9a-f]{40} # v' .github/workflows/ci.yml | wc -l`
Esperado: `yaml ok` e 4 linhas (todas as actions com SHA).

- [ ] **Step 3: Simular o que a CI roda**

Run: `.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check . && .venv/bin/python -m pytest -q -rs | tail -3`
Esperado: lint limpo, `85 passed`, nenhum `SKIPPED`. A prova real é a CI verde na Task 9.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Add CI: ruff and pytest on Python 3.11 to 3.13, and gitleaks"
```

### Task 7: README em inglês

**Files:** Modify: `README.md`. Modify: `pyproject.toml` (`description` em inglês).

Seções, nesta ordem:
1. **What it is** e **The problem:** decidir o enquadramento 9:16 antes de renderizar, porque a peça cresce durante a impressão e um corte centrado decepa peça fora do centro, o que só se vê no fim.
2. Espaço para o GIF: `<!-- TODO: panel GIF (docs/painel.gif) -->` e nenhuma imagem quebrada.
3. **How it works:** prévia instantânea por CSS sobre cache de quadros inteiros já girados e reduzidos (`timelapse/cache.py`, `web/app.js`), a conta do recorte espelhada entre `web/app.js` e `video_filter` em `timelapse/cli.py`, fixada por `tests/test_recorte.py`; fila de render em segundo plano (`timelapse/fila.py`); correção de cor contra um quadro de referência em espaço linear, ganho por canal medido numa área escolhida (`timelapse/correcao.py`); estabilização euclidiana com ORB e refino ECC numa máscara de região estática, quadros que falham herdam o deslocamento das vizinhas, zoom mínimo para esconder a borda; render corrigido por pipe para o FFmpeg.
4. **Install:** Python 3.11+, FFmpeg, `make setup`, `cp painel.example.json painel.json`, `cp config.example.json config.json` (opcional).
5. **Usage:** painel (`make painel`, `make iniciar`/`make parar`, o fluxo na tela) e CLI (`python -m timelapse.cli`, `--previa`, `--conferir`, `--girar auto`). Atalhos `.app` só no macOS.
6. **Configuration:** tabela do `painel.json`, `TIMELAPSE_ACERVO`, `TIMELAPSE_PORTA`.
7. **Tests:** `make test`, `make lint`, contagem tirada da saída do pytest no momento.
8. **Security:** o servidor não tem autenticação e escuta só em `127.0.0.1` (`timelapse/servidor.py`); qualquer processo local pode usá-lo; não expor com proxy ou port-forward.
9. **Limits:** interface e identificadores em português; `docs-cli.md` e `docs/correcao-estabilizacao.md` em português; testado em macOS, CI em Linux; estabilização é euclidiana (sem perspectiva); áreas de alinhar precisam de textura parada.
10. **License:** MIT.

Números que o README pode citar: só os que a Task 7 medir na hora (contagem de testes). O "cerca de 40 s para 450 fotos" do README atual sai, a não ser que o Lucca confirme que mediu.

- [ ] **Step 1: Escrever o README.**

- [ ] **Step 2: Conferência frase a frase.** Um subagente que não escreveu o README recebe o arquivo e o código e devolve, para cada afirmação técnica, o `arquivo:linha` que a sustenta ou "sem suporte". Toda "sem suporte" é corrigida ou removida.

- [ ] **Step 3: Conferir os comandos do README**

Run: `make -n setup painel test lint && .venv/bin/python -m timelapse.cli --help | head -3 && grep -c '127.0.0.1' README.md`
Esperado: comandos existem, `--help` imprime o uso, ao menos 1 menção a `127.0.0.1`.

- [ ] **Step 4: Commit**

```bash
git add README.md pyproject.toml
git commit -m "Rewrite the README in English"
```

### Task 8: Revisão

- [ ] **Step 1:** `superpowers:requesting-code-review` com um subagente que não escreveu nada desta branch, sobre `git diff main...publicar-repositorio`, contra este plano. Achado confirmado vira correção com teste e commit próprio.
- [ ] **Step 2:** `/security-review`. Achados vão para o Lucca antes do push.
- [ ] **Step 3: Verificação final**

Run: `.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check . && .venv/bin/python -m pytest -q | tail -1 && gitleaks detect --source . --log-opts="--all" --redact`
Esperado: lint limpo, testes passando (colar a saída), `no leaks found`.

### Task 9: Push e PR

- [ ] **Step 1: Pedir ok do Lucca para o push.** Só depois: `git push -u origin publicar-repositorio`.
- [ ] **Step 2: PR**

```bash
gh pr create --base main --head publicar-repositorio --title "Prepare the repository for publication" --body "<resumo, como testar, saída dos testes>"
```

- [ ] **Step 3: CI verde**

Run: `gh pr checks --watch`
Esperado: `test (3.11)`, `test (3.12)`, `test (3.13)` e `gitleaks` com `pass`. Falha: `superpowers:systematic-debugging`, correção em commit novo, novo push com ok.

- [ ] **Step 4: Merge com ok do Lucca**: `gh pr merge --merge` (sem squash, preserva os commits pequenos). Depois `gh run list --branch main --limit 1` mostra a CI da `main` verde.

### Task 10: Tornar público (só com ok explícito)

- [ ] **Step 1:** `gitleaks detect --source . --log-opts="--all"` de novo sobre a `main` atualizada: `no leaks found`.
- [ ] **Step 2: Pedir o ok do Lucca**, lembrando que todo o histórico e todas as branches enviadas ficam visíveis.
- [ ] **Step 3:** `gh repo edit matuck40/timelapse-studio --visibility public --accept-visibility-change-consequences`
- [ ] **Step 4: Conferir**

Run: `gh repo view matuck40/timelapse-studio --json visibility --jq .visibility`
Esperado: `PUBLIC`.
