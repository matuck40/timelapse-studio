"""Correcao de cor e estabilizacao contra UM quadro de referencia.

Tudo aqui trabalha na foto CRUA, sem giro: e assim que o cache e o ffmpeg
(-noautorotate) enxergam a foto. Regioes chegam normalizadas (0-1) nesse
mesmo sistema. O giro EXIF continua sendo aplicado depois, pelo video_filter.

Convencao do alinhamento: a matriz A (2x3) de um quadro leva um ponto da
REFERENCIA ao ponto correspondente NESTE quadro. Para alinhar, cada pixel u
da saida busca o quadro em A(u): warpAffine com WARP_INVERSE_MAP.
"""
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

FORMATO = 1
LADO_ANALISE = 1500
GANHO_MAXIMO = 2.0  # Q9: teto do ganho de brilho
JANELA_SUAVIZAR = 5  # Q8: media centrada
JANELA_MEDIANA = 7
DESVIO_OUTLIER = 0.12  # em log natural: ~13% fora da mediana dos vizinhos
LUMA = np.array([0.2126, 0.7152, 0.0722])
MIN_INLIERS = 12
CORRELACAO_MINIMA = 0.85  # abaixo disto o ECC nao confia no alinhamento


class Cancelado(Exception):
    """O painel pediu outra correcao antes desta terminar."""


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


# ---------- previa corrigida do painel ----------

NEUTRO = {"theta": 0.0, "tx": 0.0, "ty": 0.0, "ganho": [1.0, 1.0, 1.0]}


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
        # foto que chegou depois da analise (captura rodando) entra sem correcao
        quadro = analise["quadros"].get(nome, NEUTRO)
        with Image.open(cache.caminho_quadro(pasta, posicao)) as imagem:
            rgb = np.asarray(imagem.convert("RGB"))
        saida = aplicar(rgb, quadro, analise, cor, estabilizar)
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
        # da propria analise: a pasta pode ter ganhado fotos desde entao
        "total_fotos": len(analise["quadros"]),
        "falhas": [i for i, q in enumerate(analise["quadros"].values())
                   if q["falhou_alinhamento"]],
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
