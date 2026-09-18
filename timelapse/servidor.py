"""Servidor local do painel. Biblioteca padrao apenas: nada de pip install."""
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import acervo, ambiente, cache
from .fila import Fila

WEB = ambiente.RAIZ / "web"
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".jpg": "image/jpeg", ".json": "application/json"}

FILA = Fila()
CACHES_EM_CURSO: dict[str, str] = {}


def opcoes() -> dict:
    """painel.json, com TIMELAPSE_ACERVO e TIMELAPSE_PORTA por cima quando definidos."""
    arquivo = ambiente.RAIZ / "painel.json"
    padrao = {"acervo": "", "porta": 8765, "limite_cache": 300, "largura_cache": 700}
    if arquivo.is_file():
        padrao.update(json.loads(arquivo.read_text(encoding="utf-8")))
    if os.environ.get("TIMELAPSE_ACERVO"):
        padrao["acervo"] = os.environ["TIMELAPSE_ACERVO"]
    if os.environ.get("TIMELAPSE_PORTA"):
        padrao["porta"] = int(os.environ["TIMELAPSE_PORTA"])
    return padrao


def padroes_cli() -> dict:
    arquivo = ambiente.RAIZ / "config.json"
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}


def arquivo_enquadramento(pasta: Path) -> Path:
    return pasta / "enquadramento.json"


class Painel(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):  # silencia o log de acesso
        pass

    # ---------- utilidades ----------
    def _json(self, dados, codigo=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _arquivo(self, caminho: Path, cacheavel=False):
        if not caminho.is_file():
            return self._json({"erro": "nao encontrado"}, 404)
        corpo = caminho.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS.get(caminho.suffix.lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(len(corpo)))
        if cacheavel:
            self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self) -> dict:
        tamanho = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(tamanho)) if tamanho else {}

    # ---------- rotas ----------
    def do_GET(self):
        url = urlparse(self.path)
        consulta = {k: v[0] for k, v in parse_qs(url.query).items()}
        rota = url.path

        if rota == "/":
            return self._arquivo(WEB / "index.html")
        if rota.startswith("/web/"):
            alvo = (WEB / rota[5:]).resolve()
            if WEB.resolve() in alvo.parents:
                return self._arquivo(alvo)
            return self._json({"erro": "fora do diretorio"}, 403)

        if rota == "/api/config":
            cfg = opcoes()
            return self._json({"acervo": cfg["acervo"], "padroes": padroes_cli(),
                               "limite_cache": cfg["limite_cache"]})

        if rota == "/api/acervo":
            return self._json(acervo.listar(Path(opcoes()["acervo"])))

        if rota == "/api/manifesto":
            pasta = Path(consulta.get("pasta", ""))
            dados = cache.manifesto(pasta)
            estado = CACHES_EM_CURSO.get(str(pasta))
            return self._json({"manifesto": dados, "construindo": estado})

        if rota == "/api/enquadramento":
            arquivo = arquivo_enquadramento(Path(consulta.get("pasta", "")))
            if not arquivo.is_file():
                return self._json({"salvo": None})
            return self._json({"salvo": json.loads(arquivo.read_text(encoding="utf-8"))})

        if rota == "/api/fila":
            return self._json(FILA.estado())

        if rota.startswith("/q/"):
            partes = rota[3:].split("/")
            if len(partes) == 2:
                alvo = cache.RAIZ_CACHE / partes[0] / partes[1]
                return self._arquivo(alvo, cacheavel=True)

        return self._json({"erro": "rota desconhecida"}, 404)

    def do_POST(self):
        rota = urlparse(self.path).path
        dados = self._corpo()

        if rota == "/api/cache":
            pasta = Path(dados["pasta"])
            if CACHES_EM_CURSO.get(str(pasta)) == "construindo":
                return self._json({"estado": "construindo"})
            CACHES_EM_CURSO[str(pasta)] = "construindo"

            def tarefa():
                try:
                    cache.construir(pasta, limite=dados.get("limite", opcoes()["limite_cache"]),
                                    largura=opcoes()["largura_cache"])
                    CACHES_EM_CURSO.pop(str(pasta), None)
                except Exception as erro:  # noqa: BLE001
                    CACHES_EM_CURSO[str(pasta)] = f"erro: {erro}"

            threading.Thread(target=tarefa, daemon=True).start()
            return self._json({"estado": "construindo"})

        if rota == "/api/enquadramento":
            pasta = Path(dados["pasta"])
            arquivo_enquadramento(pasta).write_text(
                json.dumps(dados["parametros"], ensure_ascii=False, indent=1), encoding="utf-8"
            )
            return self._json({"ok": True})

        if rota == "/api/fila":
            pasta = Path(dados["pasta"])
            trabalho = FILA.adicionar(pasta, dados.get("rotulo", pasta.name),
                                      dados["parametros"], int(dados.get("total_quadros", 0)))
            return self._json({"id": trabalho.id})

        if rota == "/api/fila/cancelar":
            return self._json({"ok": FILA.cancelar(int(dados["id"]))})

        return self._json({"erro": "rota desconhecida"}, 404)


def main() -> None:
    cfg = opcoes()
    endereco = f"http://localhost:{cfg['porta']}"
    servidor = ThreadingHTTPServer(("127.0.0.1", cfg["porta"]), Painel)
    print(f"timelapse-studio — painel em {endereco}")
    print(f"acervo: {cfg['acervo']}")
    print("Feche esta janela para parar o servidor e a fila.\n")
    try:
        webbrowser.open(endereco)
    except Exception:  # noqa: BLE001
        pass
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nPainel encerrado.")


if __name__ == "__main__":
    main()
