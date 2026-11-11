"""Testes dos utilitarios de imagem (funcoes puras, sem Streamlit)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app import config
from app.services.imagens import (
    dimensoes_por_proporcao,
    largura_relatorio,
    preparar_imagem,
)


def test_dimensoes_figura_estreita():
    # proporcao < 0.75 (alta/retrato) -> limites estreitos
    assert dimensoes_por_proporcao(100, 200) == config.FIGURA_LIMITE_ESTREITA


def test_dimensoes_figura_larga():
    # proporcao > 1.8 (paisagem) -> limites largos
    assert dimensoes_por_proporcao(400, 100) == config.FIGURA_ESPACO_LARGA


def test_dimensoes_figura_padrao():
    # proporcao entre 0.75 e 1.8 -> limites padrao
    assert dimensoes_por_proporcao(200, 200) == config.FIGURA_LIMITE_PADRAO


def test_largura_relatorio_nao_amplia():
    # Imagem pequena nao deve ser ampliada (fator limitado a 1.0).
    assert largura_relatorio(100, 50) == 100


def test_largura_relatorio_reduz_mantendo_proporcao():
    # Imagem grande deve caber no limite sem distorcer.
    largura = largura_relatorio(2000, 1000)
    assert largura <= config.RELATORIO_FIGURA_LIMITE[0]
    # altura correspondente nao pode passar do limite de altura
    altura = largura * (1000 / 2000)
    assert altura <= config.RELATORIO_FIGURA_LIMITE[1]


def test_preparar_imagem_respeita_limites(tmp_path: Path):
    # Cria uma imagem grande e confere que ela e reduzida.
    img = Image.new("L", (1000, 800))
    origem = tmp_path / "grande.png"
    img.save(origem)

    resultado = preparar_imagem(origem, 300, 200)
    assert resultado.width <= 300
    assert resultado.height <= 200
