import sys

from timelapse.fila import comando_cli


def test_regiao_vira_texto_x_y_w_h():
    comando = comando_cli("/fotos", {"regiao_cor": [0.1, 0.2, 0.3, 0.4], "estabilizar": True,
                                     "corrigir_cor": False, "referencia": "IMG_1.JPG"})
    assert comando == [sys.executable, "-m", "timelapse.cli", "/fotos",
                       "--regiao-cor", "0.1,0.2,0.3,0.4", "--estabilizar",
                       "--referencia", "IMG_1.JPG"]


def test_parametros_antigos_continuam_iguais():
    comando = comando_cli("/fotos", {"zoom": 1.5, "pos_x": -20, "fim": None, "inverter": False})
    assert comando[4:] == ["--zoom", "1.5", "--pos-x", "-20"]
