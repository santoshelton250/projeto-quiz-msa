"""
Extrator de questoes do Quiz MSA.

Le os arquivos-fonte:
  - arquivo1.csv ............ enunciados, alternativas e respostas corretas
  - caderno*.pdf ............ figuras (imagens) associadas as questoes

Gera:
  - dados/questoes.json ..... fonte da verdade consumida por quiz.py
  - imagens_quiz/ ........... figuras extraidas, nomeadas fase_X_pergunta_N

Execute UMA vez (e novamente sempre que os PDFs/CSV mudarem):
    python extrator.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import pymupdf  # PyMuPDF

# --------------------------------------------------------------------------- #
# Configuracao
# --------------------------------------------------------------------------- #
RAIZ = Path(__file__).resolve().parent
CSV_FONTE = RAIZ / "arquivo1.csv"
PASTA_IMAGENS = RAIZ / "imagens_quiz"
PASTA_DADOS = RAIZ / "dados"
ARQUIVO_JSON = PASTA_DADOS / "questoes.json"

# Padrao que identifica o cabecalho de uma questao, ex.: "12. O que e ...?"
RE_CABECALHO = re.compile(r"^\s*(\d{1,3})\s*\.\s+(.*)$")

# Alternativas A-D (aceita "(A)", "A)" e variacoes)
RE_ALTERNATIVA = re.compile(r"^\s*\(?\s*([A-Da-d])\s*[\)\.]\s*(.*)$")


# --------------------------------------------------------------------------- #
# 1) Leitura das respostas corretas (CSV)
# --------------------------------------------------------------------------- #
def carregar_csv() -> dict[int, list[dict]]:
    """Retorna {fase: [ {numero, enunciado, alternativas, correta}, ... ]}."""
    df = pd.read_csv(CSV_FONTE)
    df.columns = [c.strip() for c in df.columns]

    por_fase: dict[int, list[dict]] = {}
    for fase, grupo in df.groupby("Modulo", sort=True):
        questoes: list[dict] = []
        numero = 0
        for _, linha in grupo.iterrows():
            alternativas = []
            for letra in "ABCD":
                valor = linha.get(f"Alternativa_{letra}")
                if isinstance(valor, str) and valor.strip():
                    alternativas.append(valor.strip())

            correta_letra = str(linha.get("Resposta_Correta", "")).strip().upper()
            indice_correto = "ABCD".find(correta_letra)

            # Pula itens que nao sao questoes de multipla escolha validas:
            #   - sem alternativas (ex.: instrucoes de exercicio);
            #   - resposta correta ausente ou apontando para alternativa
            #     inexistente (inconsistencia na fonte).
            if not alternativas or not (0 <= indice_correto < len(alternativas)):
                continue

            numero += 1
            questoes.append(
                {
                    "numero": numero,
                    "enunciado": str(linha["Pergunta"]).strip(),
                    "alternativas": alternativas,
                    "correta": indice_correto,  # indice em 'alternativas'
                    "imagem": None,             # preenchido na etapa de PDF
                }
            )
        por_fase[int(fase)] = questoes
    return por_fase


# --------------------------------------------------------------------------- #
# 2) Extracao das figuras dos PDFs e associacao as questoes
# --------------------------------------------------------------------------- #
def _localizar_pdfs() -> dict[int, Path]:
    """Mapeia {fase: caminho_do_pdf}."""
    pdfs: dict[int, Path] = {}
    for caminho in sorted(RAIZ.glob("caderno*.pdf")):
        m = re.search(r"FASE\s+(\d+)", caminho.name, re.IGNORECASE)
        if m:
            pdfs[int(m.group(1))] = caminho
    return pdfs


def _numero_da_linha(texto_linha: str) -> int | None:
    m = RE_CABECALHO.match(texto_linha)
    return int(m.group(1)) if m else None





def _render_png(bmp: pymupdf.Pixmap) -> bytes:
    """Converte o recorte do pixmap em bytes PNG (ja renderizado em RGB)."""
    return bmp.tobytes("png")


def extrair_figuras_do_pdf(caminho_pdf: Path) -> list[tuple[int, bytes]]:
    """
    Extrai as figuras visiveis do PDF, agrupadas por questao.

    Retorna uma lista de (numero_da_questao, bytes_png), onde os bytes de cada
    questao correspondem a UMA imagem que e a uniao (caixa envolvente) de todas
    as figuras daquela questao. Isso preserva figuras lado a lado (ex.: 3
    colcheias em sequencia) e figuras empilhadas, que de outra forma seriam
    sobrescritas por terem o mesmo nome de arquivo.

    Regra de associacao (deterministica, por posicao vertical):
      - Enumera, na ordem do documento, os cabecalhos de questao ("N.") e as
        imagens, cada um com sua coordenada Y.
      - Cada imagem pertence a questao cujo cabecalho esta IMEDIATAMENTE
        ACIMA dela. Se a imagem estiver acima do primeiro cabecalho da pagina
        (figura "acima" da questao), ela pertence a primeira questao que vem
        depois dela na mesma pagina.
    """
    documento = pymupdf.open(caminho_pdf)
    resultados: list[tuple[int, bytes]] = []
    MARGEM = 4  # respiro em pontos ao redor da caixa, para nao cortar tracos

    for pagina in documento:
        blocos = pagina.get_text("dict")["blocks"]

        marcadores: list[tuple[float, str, object]] = []
        for bloco in blocos:
            if bloco.get("type") == 1:  # imagem
                marcadores.append((bloco["bbox"][1], "IMG", bloco))
            else:
                for linha in bloco.get("lines", []):
                    texto = "".join(span["text"] for span in linha["spans"])
                    numero = _numero_da_linha(texto)
                    if numero is not None:
                        marcadores.append((linha["bbox"][1], "Q", numero))

        marcadores.sort(key=lambda t: t[0])

        cabecalhos = [(y, v) for (y, tipo, v) in marcadores if tipo == "Q"]
        imagens = [(y, v) for (y, tipo, v) in marcadores if tipo == "IMG"]

        # Agrupa os retangulos das imagens por questao.
        caixas: dict[int, pymupdf.Rect] = {}
        for y_img, bloco in imagens:
            numero = _associar_questao(y_img, cabecalhos)
            if numero is None:
                continue
            caixa = pymupdf.Rect(bloco["bbox"])
            if numero in caixas:
                caixas[numero] |= caixa  # uniao das caixas
            else:
                caixas[numero] = caixa

        for numero, caixa in caixas.items():
            caixa = pymupdf.Rect(caixa)
            caixa.x0 = max(0, caixa.x0 - MARGEM)
            caixa.y0 = max(0, caixa.y0 - MARGEM)
            caixa.x1 = min(pagina.rect.x1, caixa.x1 + MARGEM)
            caixa.y1 = min(pagina.rect.y1, caixa.y1 + MARGEM)
            recorte = pagina.get_pixmap(clip=caixa, dpi=220, alpha=False)
            resultados.append((numero, _render_png(recorte)))

    documento.close()
    return resultados


def _associar_questao(y_img: float, cabecalhos: list[tuple[float, int]]) -> int | None:
    """Dado o Y de uma imagem, retorna o numero da questao correspondente."""
    if not cabecalhos:
        return None

    anterior: tuple[float, int] | None = None
    for y_q, numero in cabecalhos:  # cabecalhos ja ordenados por Y
        if y_q <= y_img:
            anterior = (y_q, numero)
        else:
            # Imagem esta acima deste cabecalho.
            if anterior is None:
                # Imagem no topo da pagina: figura "acima" -> primeira questao.
                return numero
            return anterior[1]
    # Imagem abaixo do ultimo cabecalho -> ultima questao da pagina.
    return anterior[1] if anterior else None


# --------------------------------------------------------------------------- #
# 3) Geracao do JSON consolidado
# --------------------------------------------------------------------------- #
def normalizar(texto: str) -> str:
    return unicodedata.normalize("NFKC", texto).strip().lower()


def gerar_json() -> dict:
    por_fase = carregar_csv()
    pdfs = _localizar_pdfs()

    PASTA_IMAGENS.mkdir(exist_ok=True)
    PASTA_DADOS.mkdir(exist_ok=True)

    fases_saida = []
    total_questoes = 0
    total_figuras = 0

    for fase in sorted(por_fase):
        questoes = por_fase[fase]
        por_numero = {q["numero"]: q for q in questoes}

        if fase in pdfs:
            for numero, png in extrair_figuras_do_pdf(pdfs[fase]):
                questao = por_numero.get(numero)
                if questao is None:
                    continue
                destino = PASTA_IMAGENS / f"fase_{fase}_pergunta_{numero}.png"
                destino.write_bytes(png)
                questao["imagem"] = f"imagens_quiz/{destino.name}"
                total_figuras += 1

        total_questoes += len(questoes)
        fases_saida.append({"fase": fase, "questoes": questoes})

    dados = {
        "fases": fases_saida,
        "total_questoes": total_questoes,
        "total_figuras": total_figuras,
    }

    ARQUIVO_JSON.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return dados


if __name__ == "__main__":
    resultado = gerar_json()
    print(f"OK - {resultado['total_questoes']} questoes em "
          f"{len(resultado['fases'])} fases.")
    print(f"OK - {resultado['total_figuras']} figuras associadas.")
    print(f"Arquivo gerado: {ARQUIVO_JSON}")
