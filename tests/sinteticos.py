"""Imagens de teste geradas por codigo: nada depende do HD Workflow."""
import cv2
import numpy as np


def textura(largura=600, altura=400, semente=1):
    """Ruido suavizado: textura rica, boa para o ORB e o ECC acharem pontos."""
    gerador = np.random.default_rng(semente)
    ruido = gerador.integers(0, 256, (altura // 8, largura // 8), dtype=np.uint8)
    return cv2.resize(ruido, (largura, altura), interpolation=cv2.INTER_CUBIC)
