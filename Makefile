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
	.venv/bin/pip install -c requirements-dev.txt -e '.[dev]'
	.venv/bin/python -m timelapse.ambiente

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check . && $(PY) -m ruff format --check .

clean:  ## Apaga o cache de previa
	rm -rf .cache-previa
