"""Imagens de teste geradas por codigo: nada depende do HD Workflow."""
import cv2
import numpy as np


def textura(largura=600, altura=400, semente=1):
    """Ruido suavizado: textura rica, boa para o ORB e o ECC acharem pontos."""
    gerador = np.random.default_rng(semente)
    ruido = gerador.integers(0, 256, (altura // 8, largura // 8), dtype=np.uint8)
    return cv2.resize(ruido, (largura, altura), interpolation=cv2.INTER_CUBIC)


def sequencia(pasta):
    """Cinco PNGs: tremor, um salto, luz caindo, e a do meio com uma mao na frente."""
    from PIL import Image

    from timelapse import correcao as c

    base = cv2.cvtColor(textura(900, 600), cv2.COLOR_GRAY2RGB)
    base[400:560, 650:850] = (140, 140, 140)  # area lisa para medir a cor
    deslizes = [(0, 0), (3, -2), (0, 0), (40, 25), (41, 24)]
    luzes = [1.0, 0.9, 1.0, 0.8, 0.8]
    fotos = []
    for i, ((dx, dy), luz) in enumerate(zip(deslizes, luzes, strict=True)):
        quadro = cv2.warpAffine(base, c.euclidiana(0, dx, dy), (900, 600),
                                borderMode=cv2.BORDER_REFLECT)
        linear = c.srgb_para_linear(quadro) * luz
        quadro = np.round(c.linear_para_srgb(linear)).astype(np.uint8)
        if i == 2:
            quadro[50:590, 100:880] = (20, 15, 10)
        caminho = pasta / f"IMG_{i:04d}.png"
        Image.fromarray(quadro).save(caminho)
        fotos.append(caminho)
    return fotos
