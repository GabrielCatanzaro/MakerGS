"""Faz a cabeca seguir um rosto pela webcam, sem usar voz.

Use: python -m scripts.rastrear_cabeca   (opcoes: --porta COM7 --camera 1)
Pressione Q na janela da camera para encerrar. Se a cabeca se afastar da
pessoa em vez de segui-la, repita com --inverter.
"""

import argparse

from checkpoint_alexa import ArduinoController, HeadTracker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--porta", default="", help="Ex.: COM7; padrao: ARDUINO_PORT ou deteccao automatica")
    parser.add_argument("--camera", type=int, default=None,
                        help="Indice da webcam da cabeca; padrao: R2D2_CAMERA_CABECA ou 1 (segunda camera)")
    parser.add_argument("--inverter", action="store_true", help="Inverte o sentido do giro")
    parser.add_argument("--duracao", type=float, default=None, help="Encerra sozinho apos N segundos")
    args = parser.parse_args()

    arduino = ArduinoController(porta=args.porta)
    try:
        cabeca = HeadTracker(arduino, camera=args.camera, inverter=args.inverter or None)
        print(f"Camera {cabeca.camera}; giro {'invertido' if cabeca.inverter else 'normal'}.")
        print(cabeca.rastrear(duracao_max=args.duracao))
    finally:
        arduino.fechar()


if __name__ == "__main__":
    main()
