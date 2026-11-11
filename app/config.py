"""Configuracao central da aplicacao (caminhos e constantes de exibicao).

Concentra "numeros magicos" e caminhos que antes estavam espalhados pelo
quiz.py, para que ajustes de layout aconteçam em um unico lugar.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Caminhos
# --------------------------------------------------------------------------- #
RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_JSON = RAIZ / "dados" / "questoes.json"
PASTA_RELATORIOS = RAIZ / "relatorios"
PASTA_IMAGENS = RAIZ / "imagens_quiz"

# Letras usadas para rotular alternativas (A, B, C, ...).
LETRAS = "ABCDEFGH"

# --------------------------------------------------------------------------- #
# Regras de simulado
# --------------------------------------------------------------------------- #
# Ate esse total usa distribuicao igualitaria; acima, proporcional.
# (A constante "oficial" vive em app/services/simulados.py; reexportada aqui
#  para conveniencia de quem configura o app.)
LIMIAR_IGUALITARIO = 30

# --------------------------------------------------------------------------- #
# Tamanhos das figuras (em pixels) - tela do quiz
# --------------------------------------------------------------------------- #
# Regra por proporcao (largura / altura) da figura da questao:
#   - figura "alta"  (proporcao < 0.75): 170 x 220
#   - figura "larga" (proporcao > 1.8):  650 x 320
#   - caso geral:                        330 x 300
FIGURA_LIMITE_ESTREITA = (170, 220)
FIGURA_ESPACO_LARGA = (650, 320)
FIGURA_LIMITE_PADRAO = (330, 300)
FIGURA_PROPORCAO_ESTREITA = 0.75
FIGURA_PROPORCAO_LARGA = 1.8

# Figuras nas ALTERNATIVAS ilustradas (layout especial).
FIGURA_ALTERNATIVA_PRINCIPAL = (460, 220)   # figura de referencia no topo
FIGURA_ALTERNATIVA_IMAGEM = (420, 170)      # figura de cada alternativa

# Limite para exibir a figura "esticada" na largura da coluna.
FIGURA_LARGURA_STRETCH_PX = 400

# --------------------------------------------------------------------------- #
# Tamanhos das figuras (em pixels) - tela do RELATORIO
# --------------------------------------------------------------------------- #
RELATORIO_FIGURA_LIMITE = (450, 180)

# --------------------------------------------------------------------------- #
# Tamanhos das figuras (em MILIMETROS) - PDF do relatorio
# --------------------------------------------------------------------------- #
PDF_FIGURA_LIMITE_MM = (70, 40)
