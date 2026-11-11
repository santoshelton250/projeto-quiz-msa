"""Utilitarios de imagem (melhoria de nitidez e redimensionamento).

Funcoes puras de manipulacao de imagem (PIL), sem dependencia de Streamlit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from PIL import Image, ImageEnhance, ImageOps


def preparar_imagem(
    caminho: Union[str, Path], largura_maxima: int, altura_maxima: int
) -> Image.Image:
    """Abre, melhora a nitidez e redimensiona uma figura (retorna PIL.Image).

    A imagem e convertida para tons de cinza, tem o contraste normalizado e
    recebe realce de contraste e nitidez. Depois e reduzida proporcionalmente
    para caber em (largura_maxima, altura_maxima), sem ampliar.
    """
    with Image.open(caminho) as arquivo:
        imagem = arquivo.copy()

    imagem = ImageOps.grayscale(imagem)
    imagem = ImageOps.autocontrast(imagem)
    imagem = ImageEnhance.Contrast(imagem).enhance(1.15)
    imagem = ImageEnhance.Sharpness(imagem).enhance(1.25)
    imagem.thumbnail((largura_maxima, altura_maxima), Image.Resampling.LANCZOS)
    return imagem


def dimensoes_por_proporcao(
    largura: int, altura: int
) -> tuple[int, int]:
    """Decide o tamanho maximo (largura, altura) de uma figura da questao.

    A escolha depende da proporcao (largura / altura):
      - figura alta  (< 0.75): limites estreitos (retrato)
      - figura larga (> 1.8):  limites largos (paisagem)
      - caso geral:            limites padrao
    """
    from app import config

    proporcao = largura / altura
    if proporcao < config.FIGURA_PROPORCAO_ESTREITA:
        return config.FIGURA_LIMITE_ESTREITA
    if proporcao > config.FIGURA_PROPORCAO_LARGA:
        return config.FIGURA_ESPACO_LARGA
    return config.FIGURA_LIMITE_PADRAO


def preparar_imagem_questao(
    caminho: Union[str, Path],
) -> Image.Image:
    """Prepara a figura principal de uma questao, aplicando a regra de tamanho."""
    from app import config

    with Image.open(caminho) as arquivo:
        largura, altura = arquivo.size

    largura_maxima, altura_maxima = dimensoes_por_proporcao(largura, altura)
    return preparar_imagem(caminho, largura_maxima, altura_maxima)


def largura_relatorio(
    largura: int, altura: int, limite: tuple[int, int] | None = None
) -> int:
    """Calcula a largura (px) para exibir a figura no relatorio, sem ampliar."""
    from app import config

    largura_maxima, altura_maxima = limite or config.RELATORIO_FIGURA_LIMITE
    fator = min(1.0, largura_maxima / largura, altura_maxima / altura)
    return max(1, int(largura * fator))
