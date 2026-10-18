# timelapse-studio

[![CI](https://github.com/matuck40/timelapse-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/matuck40/timelapse-studio/actions/workflows/ci.yml)

A local tool that turns the photo sequence of a 3D print into a timelapse video. The panel is set up for vertical 9:16 output (1080x1920 by default); the CLI keeps the source resolution unless told otherwise. It has a web panel served on `127.0.0.1` and a command-line interface, both built on FFmpeg. It can also correct colour drift and camera shake against a reference frame, using numpy, Pillow and OpenCV. Everything runs on your own machine, with no external service.

## What it is

- A web panel to browse print photo sequences, frame the 9:16 crop with an instant preview, and queue renders.
- A CLI (`python -m timelapse.cli`) that does the actual render and works on its own, without the panel.
- Optional colour correction and stabilization, both measured against one reference frame chosen by the user.

## The problem

The 9:16 framing has to be decided before the render. A print grows during the job, so a centred vertical crop that looks fine on the first photos can cut off a part that sits off-centre on the bed. That only shows up at the end of the print, when the part is at full size. The panel shows any frame of the sequence with the crop applied, as you move the sliders, so the framing can be checked on the last frame before spending a render.

<!-- TODO: panel GIF (docs/painel.gif) -->

## How it works

**Instant preview.** On first use of a sequence, `timelapse/cache.py` makes one FFmpeg pass that writes a downscaled copy of each sampled frame (up to `limite_cache` frames, longest side `lado_cache` pixels), plus a manifest with the source dimensions and the EXIF rotation. The cache keeps the full frame, unrotated. The browser (`web/app.js`) applies rotation, zoom and position with CSS, so the zoom and position sliders make no request to the server. The frame slider only loads a JPEG that is already in the cache.

**One crop formula in two places.** The crop maths in `janelaVisivel` in `web/app.js` mirrors the FFmpeg filter chain built by `video_filter` in `timelapse/cli.py`: zoom crops first, positioned by pos-x and pos-y, then the image is scaled to fit (with black bars) or to fill (cropped again by pos-x and pos-y). `tests/test_recorte.py` pins the CLI side, so a change to `video_filter` that the JavaScript does not follow shows up as a failing test.

**Background render queue.** `timelapse/fila.py` runs one worker thread that takes jobs in order and runs the CLI as a subprocess for each. Progress is read from FFmpeg's `frame=` output. Jobs can be cancelled while waiting or running. Closing the browser tab does not stop the queue, because it lives in the server process.

**Colour correction** (`timelapse/correcao.py`). The user picks a reference frame and draws a still, flat area (for example the wall). For every frame, the mean of each RGB channel inside that area is measured in linear light (sRGB decoded to linear). The gain per channel is reference / frame. Outliers against a moving median of the neighbours are replaced by interpolation, the gains are smoothed with a centred moving average, and the brightness gain is capped at 2x. The gain is applied to the whole frame in linear light through a lookup table.

**Stabilization** (`timelapse/correcao.py`). The user draws a still area with texture. Each frame is aligned to the reference with a Euclidean transform (rotation plus translation, no scale or perspective): ORB features with RANSAC give an initial estimate, and ECC (`cv2.findTransformECC`) refines it inside a mask of that area. A frame is marked as failed when ECC raises an error or its correlation is below 0.85 (if ORB finds too few matches, ECC starts from the identity instead). Failed frames get their motion by linear interpolation between the neighbouring frames that did align. The tool then finds, by bisection, the smallest centred zoom that hides the moving border in every frame.

**Corrected render.** When colour correction or stabilization is on, the CLI decodes each photo in Python, applies the correction, and writes the frames to FFmpeg as raw RGB on `pipe:0`. Without correction, FFmpeg reads the photos directly. The original photos are never modified.

## Install

Requirements: Python 3.11 or newer, and FFmpeg.

```bash
make setup                                  # creates .venv, installs pinned deps, reports which FFmpeg it found
cp painel.example.json painel.json          # panel settings; edit "acervo"
cp config.example.json config.json          # optional: default CLI options
```

`make setup` installs the package in editable mode with the development tools, using `requirements-dev.txt` as the constraints file. Without the `.venv`, the panel and the CLI still run with the system `python3`, but colour correction and stabilization are not available (they need numpy, Pillow and OpenCV).

FFmpeg is looked up in `bin/ffmpeg` first (not tracked in git), then in the Homebrew paths or `PATH`. On macOS: `brew install ffmpeg`. With FFmpeg older than 5, the CLI uses `-vsync` instead of `-fps_mode`.

## Usage

### Panel

```bash
make painel     # foreground, Ctrl+C to stop; opens the browser
make iniciar    # background (PID in .painel.pid, log in .painel.log), then opens http://localhost:8765
make parar      # stops the background panel
```

`make iniciar` and `make parar` use zsh scripts and the macOS `open` command. The two launchers in `Atalhos/` (`▶ Iniciar Painel.app`, `■ Parar Painel.app`) are macOS-only shortcuts for the same thing.

Workflow in the panel:

1. Pick a sequence in the left column. The first time, the preview cache is built.
2. Adjust zoom, pos-x and pos-y. The preview updates as you drag.
3. Drag the frame slider to check that the framing still works as the part grows. The slider opens on the last frame.
4. Optional correction: go to a good frame and click **Usar este quadro como referência**, then draw **Área para cor** (still and flat) and/or **Área para alinhar** (still and textured). After the analysis, **Ver antes / Ver depois** compares the result, and frames that failed to align are marked in red on the slider.
5. **Gerar timelapse** adds the job to the queue and returns control, so the next sequence can be framed while the first one renders.

**Salvar enquadramento** writes `enquadramento.json` in the sequence folder, and it is loaded again next time. With the "peça" (part) field filled in, the output goes to `<pasta_brutos>/<part>/timelapse/timelapse_<YYYY-MM-DD>.mp4`; otherwise it goes to the project's `render/` folder.

The panel expects one folder per project under `acervo`, with the photos in `fotos/` or `fotos-<variant>/` (at least 20 photos) and videos in `render/`. A project with no `fotos*` folder can keep its photos loose in the project root.

### CLI

```bash
.venv/bin/python -m timelapse.cli /path/to/photos --resolucao 1080x1920 --enquadramento preencher --zoom 1.3 --pos-x -25
```

- `--previa` renders only a PNG of the first selected frame, with the current settings.
- `--conferir` prints the final sequence and its duration without rendering.
- `--girar auto` (the default) follows the EXIF orientation tag, so photos taken with the camera in portrait come out upright, and zoom and position apply to the rotated frame. A fixed value (`nao`, `90`, `180`, `270`) ignores the tag.
- `--corrigir-cor`, `--estabilizar`, `--referencia`, `--regiao-cor` and `--regiao-alinhamento` run the correction described above.

Next to each MP4 the CLI writes a CSV that maps each video frame to its source photo. It never overwrites an existing file. `docs-cli.md` has the full option reference (in Portuguese). `python -m timelapse.cli --help` lists all options.

## Configuration

`painel.json` in the repository root (copy it from `painel.example.json`):

| Field | Meaning |
|---|---|
| `acervo` | root folder that holds the print projects, one folder per project |
| `porta` | port of the local server (default 8765) |
| `limite_cache` | maximum number of frames the preview cache keeps per sequence (default 300) |
| `lado_cache` | longest side, in pixels, of each cached frame (default 1050) |
| `pasta_brutos` | output root used when the "peça" field is filled in |
| `recentes` | recently used `acervo` folders, written by the panel |

Environment variables `TIMELAPSE_ACERVO` and `TIMELAPSE_PORTA` override `acervo` and `porta` without editing the file.

`config.json` (copy it from `config.example.json`) sets default CLI options. `--config <file>` uses another file, and `--sem-config` ignores it.

## Tests

```bash
make test     # pytest
make lint     # ruff check and ruff format --check
```

95 tests pass at the time of writing (`pytest -q`). Two test files run JavaScript from `web/` and need Node; they are skipped when Node is missing. CI runs lint and tests on Python 3.11, 3.12 and 3.13 (Ubuntu), plus a gitleaks scan of the git history.

## Security

The server has no authentication. It listens only on `127.0.0.1` (`timelapse/servidor.py`), so it is not reachable from other machines. It checks each request against the browser-based attacks a local server is exposed to:

- The `Host` header must be `127.0.0.1:<port>` or `localhost:<port>`, otherwise the answer is 403. This blocks DNS rebinding, where another domain is made to resolve to `127.0.0.1`.
- A POST must have `Content-Type: application/json`, and if it carries an `Origin` header, that must be `http://127.0.0.1:<port>` or `http://localhost:<port>`. Otherwise the answer is 403. A page on another site cannot send a JSON POST to the server without a CORS preflight, which the server does not grant. GET routes do not write anything.
- Frame images are served under `/q/` only for paths shaped like the cache's own files (`<id>/q_NNNNNN.jpg` and `<id>/corrigido/q_NNNNNN.jpg`). Anything else, including `..`, gets a 404. Files under `/web/` must resolve inside the `web/` folder.

That does not make it private:

- Any local process or user on the same machine can call its API, since it can send whatever headers it wants.
- The API reads folders it is given, and it also writes: `enquadramento.json` into any folder it is given, the settings in `painel.json`, and MP4 and CSV files into any output folder (`pasta_saida`) passed to a render.

Run it only while you use it, and do not expose it through a reverse proxy, a tunnel or port forwarding.

## Limits

- The UI text and most identifiers in the code are in Portuguese. `docs-cli.md` and `docs/correcao-estabilizacao.md` are also in Portuguese.
- Developed and used on macOS. CI runs on Linux. Windows has not been tried.
- Stabilization is Euclidean (rotation and translation). It does not correct scale or perspective changes.
- The alignment area must contain still texture. Areas that move during the print (the nozzle, a moving bed, the part itself) will not align.

## License

MIT. See `LICENSE`.
