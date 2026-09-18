"""Fila de render: um trabalhador so, em segundo plano, chamando a CLI."""
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import ambiente

QUADRO = re.compile(rb"frame=\s*(\d+)")


@dataclass
class Trabalho:
    id: int
    pasta: str
    rotulo: str
    parametros: dict
    total_quadros: int
    estado: str = "esperando"  # esperando | rodando | pronto | erro | cancelado
    quadros_feitos: int = 0
    saida: str | None = None
    erro: str | None = None
    criado_em: float = field(default_factory=time.time)
    terminado_em: float | None = None

    @property
    def progresso(self) -> float:
        if self.estado == "pronto":
            return 1.0
        if not self.total_quadros:
            return 0.0
        return min(self.quadros_feitos / self.total_quadros, 0.999)


class Fila:
    def __init__(self) -> None:
        self._trabalhos: list[Trabalho] = []
        self._proximo_id = 1
        self._trava = threading.Lock()
        self._acordar = threading.Event()
        self._atual: subprocess.Popen | None = None
        threading.Thread(target=self._rodar, daemon=True).start()

    def adicionar(self, pasta: Path, rotulo: str, parametros: dict, total: int) -> Trabalho:
        with self._trava:
            trabalho = Trabalho(
                id=self._proximo_id, pasta=str(pasta), rotulo=rotulo,
                parametros=parametros, total_quadros=total,
            )
            self._proximo_id += 1
            self._trabalhos.append(trabalho)
        self._acordar.set()
        return trabalho

    def estado(self) -> list[dict]:
        with self._trava:
            return [{**asdict(t), "progresso": t.progresso} for t in self._trabalhos]

    def cancelar(self, id_trabalho: int) -> bool:
        with self._trava:
            for trabalho in self._trabalhos:
                if trabalho.id != id_trabalho:
                    continue
                if trabalho.estado == "esperando":
                    trabalho.estado = "cancelado"
                    return True
                if trabalho.estado == "rodando" and self._atual:
                    self._atual.terminate()
                    return True
        return False

    def _proximo(self) -> Trabalho | None:
        with self._trava:
            for trabalho in self._trabalhos:
                if trabalho.estado == "esperando":
                    return trabalho
        return None

    def _rodar(self) -> None:
        while True:
            trabalho = self._proximo()
            if not trabalho:
                self._acordar.wait(timeout=2)
                self._acordar.clear()
                continue
            trabalho.estado = "rodando"
            try:
                self._executar(trabalho)
                trabalho.estado = "pronto" if not trabalho.erro else "erro"
            except Exception as erro:  # noqa: BLE001 - qualquer falha vira estado do trabalho
                trabalho.estado = "erro"
                trabalho.erro = str(erro)
            trabalho.terminado_em = time.time()

    def _executar(self, trabalho: Trabalho) -> None:
        comando = [sys.executable, "-m", "timelapse.cli", trabalho.pasta]
        for chave, valor in trabalho.parametros.items():
            bandeira = "--" + chave.replace("_", "-")
            if isinstance(valor, bool):
                if valor:
                    comando.append(bandeira)
            elif valor is not None and valor != "":
                comando += [bandeira, str(valor)]

        processo = subprocess.Popen(
            comando, cwd=str(ambiente.RAIZ),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self._atual = processo
        saida = bytearray()
        assert processo.stdout is not None
        for pedaco in iter(lambda: processo.stdout.read(512), b""):
            saida += pedaco
            achados = QUADRO.findall(pedaco)
            if achados:
                trabalho.quadros_feitos = int(achados[-1])
        processo.wait()
        self._atual = None

        texto = saida.decode("utf-8", "replace")
        if processo.returncode != 0:
            trabalho.erro = texto.strip().splitlines()[-1] if texto.strip() else "falhou"
            return
        for linha in texto.splitlines():
            if linha.startswith("Vídeo:"):
                trabalho.saida = linha.split(":", 1)[1].strip()
        trabalho.quadros_feitos = trabalho.total_quadros
