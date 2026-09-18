.PHONY: painel setup test lint clean

painel:  ## Sobe o painel em http://localhost:8765
	python3 -m timelapse.servidor

setup:  ## Confere o ambiente e localiza o ffmpeg
	python3 -m timelapse.ambiente

test:
	python3 -m pytest -q

lint:
	ruff check . && ruff format --check .

clean:  ## Apaga o cache de previa
	rm -rf .cache-previa
