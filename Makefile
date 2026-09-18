.PHONY: painel iniciar parar setup test lint clean

painel:  ## Sobe o painel em primeiro plano (Ctrl+C para parar)
	python3 -m timelapse.servidor

iniciar:  ## Sobe o painel em segundo plano e abre o navegador
	./scripts/iniciar-painel.sh && open http://localhost:8765

parar:  ## Para o painel e a fila
	./scripts/parar-painel.sh

setup:  ## Confere o ambiente e localiza o ffmpeg
	python3 -m timelapse.ambiente

test:
	python3 -m pytest -q

lint:
	ruff check . && ruff format --check .

clean:  ## Apaga o cache de previa
	rm -rf .cache-previa
