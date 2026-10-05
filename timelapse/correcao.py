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
