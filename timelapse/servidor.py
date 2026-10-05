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
# Correcao: um calculo por vez. Um pedido novo para a mesma pasta faz o antigo
# desistir no proximo quadro, em vez de terminar algo que ja nao serve.
CORRECOES: dict[str, dict] = {}
PEDIDOS_CORRECAO: dict[str, int] = {}
TRAVA_CORRECAO = threading.Lock()
# Chaves que o painel grava sozinho no enquadramento.json, sem o botao Salvar.
CHAVES_MESCLAVEIS = ("referencia", "regiao_cor", "regiao_alinhamento", "corrigir_cor",
                     "estabilizar", "peca")


def opcoes() -> dict:
    """painel.json, com TIMELAPSE_ACERVO e TIMELAPSE_PORTA por cima quando definidos."""
    arquivo = ambiente.RAIZ / "painel.json"
    padrao = {"acervo": "", "porta": 8765, "limite_cache": 300, "lado_cache": 1050,
              "pasta_brutos": ""}
    if arquivo.is_file():
        padrao.update(json.loads(arquivo.read_text(encoding="utf-8")))
    if os.environ.get("TIMELAPSE_ACERVO"):
        padrao["acervo"] = os.environ["TIMELAPSE_ACERVO"]
    if os.environ.get("TIMELAPSE_PORTA"):
        padrao["porta"] = int(os.environ["TIMELAPSE_PORTA"])
    return padrao


def salvar_opcoes(novas: dict) -> None:
    """Grava painel.json preservando o que nao foi passado."""
    arquivo = ambiente.RAIZ / "painel.json"
    atuais = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}
    atuais.update(novas)
    arquivo.write_text(json.dumps(atuais, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def padroes_cli() -> dict:
    arquivo = ambiente.RAIZ / "config.json"
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}


def arquivo_enquadramento(pasta: Path) -> Path:
    return pasta / "enquadramento.json"


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
                               "limite_cache": cfg["limite_cache"],
                               "pasta_brutos": cfg["pasta_brutos"],
                               "recentes": cfg.get("recentes", [])})

        if rota == "/api/acervo":
            return self._json(acervo.listar(Path(opcoes()["acervo"])))

        if rota == "/api/manifesto":
            pasta = Path(consulta.get("pasta", ""))
            dados = cache.manifesto(pasta)
            estado = CACHES_EM_CURSO.get(str(pasta))
            return self._json({"manifesto": dados, "construindo": estado,
                               "prontos": cache.quadros_prontos(pasta)})

        if rota == "/api/enquadramento":
            arquivo = arquivo_enquadramento(Path(consulta.get("pasta", "")))
            if not arquivo.is_file():
                return self._json({"salvo": None})
            return self._json({"salvo": json.loads(arquivo.read_text(encoding="utf-8"))})

        if rota == "/api/fila":
            return self._json(FILA.estado())

        if rota == "/api/brutos":
            base = opcoes()["pasta_brutos"]
            return self._json({"pasta": base,
                               "sugestoes": acervo.subpastas(Path(base)) if base else []})

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
                                    lado=opcoes()["lado_cache"])
                    CACHES_EM_CURSO.pop(str(pasta), None)
                except Exception as erro:  # noqa: BLE001
                    CACHES_EM_CURSO[str(pasta)] = f"erro: {erro}"

            threading.Thread(target=tarefa, daemon=True).start()
            return self._json({"estado": "construindo"})

        if rota == "/api/acervo/raiz":
            caminho = Path(dados["caminho"]).expanduser()
            if not caminho.is_dir():
                return self._json({"erro": f"Não é uma pasta: {caminho}"}, 400)
            cfg = opcoes()
            recentes = [str(caminho)] + [r for r in cfg.get("recentes", []) if r != str(caminho)]
            salvar_opcoes({"acervo": str(caminho), "recentes": recentes[:6]})
            return self._json({"acervo": str(caminho), "recentes": recentes[:6],
                               "projetos": acervo.listar(caminho)})

        if rota == "/api/enquadramento":
            pasta = Path(dados["pasta"])
            arquivo_enquadramento(pasta).write_text(
                json.dumps(dados["parametros"], ensure_ascii=False, indent=1), encoding="utf-8"
            )
            return self._json({"ok": True})

        if rota == "/api/brutos/raiz":
            caminho = Path(dados["caminho"]).expanduser()
            # is_dir segue o link: no Mac, _brutos e um symlink para o iCloud Drive.
            # Grava o caminho do link, que continua valendo se o iCloud mudar de lugar.
            if not caminho.is_dir():
                return self._json({"erro": f"Não é uma pasta: {caminho}"}, 400)
            salvar_opcoes({"pasta_brutos": str(caminho)})
            return self._json({"pasta": str(caminho), "sugestoes": acervo.subpastas(caminho)})

        if rota == "/api/enquadramento/correcao":
            pasta = Path(dados["pasta"])
            novos = {k: v for k, v in dados["correcao"].items() if k in CHAVES_MESCLAVEIS}
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
    print("Pare com Ctrl+C, ou com o atalho Parar Painel.\n")
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
