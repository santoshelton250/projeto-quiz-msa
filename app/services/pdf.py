"""Geracao do relatorio em PDF (fpdf2).

Funcao pura: NAO acessa `st.session_state`. Recebe um dicionario `dados` com
tudo o que precisa e devolve os bytes do PDF. Isso torna a geracao testavel
isoladamente e desacopla o PDF da interface Streamlit.

Chaves esperadas em `dados`:
    aluno: str
    modulo: int
    respondidas: int
    acertos: int
    erros: int
    modo_simulado: bool
    fases_simulado: str
    saidas_tela: int
    registros_erro: list[dict]   # cada item: numero, enunciado, imagem,
                                 # resposta_aluno, resposta_correta
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image

from app import config

# Mapa de caracteres "tipograficos"/gregos que nao existem em latin-1 (fontes
# core do PDF) para equivalentes ASCII seguros.
_MAPA_PDF = {
    "\u2013": "-",    # en-dash
    "\u2014": "-",    # em-dash
    "\u2018": "'",    # aspas simples esquerda
    "\u2019": "'",    # aspas simples direita
    "\u201c": '"',    # aspas duplas esquerda
    "\u201d": '"',    # aspas duplas direita
    "\u2026": "...",  # reticencias
    "\u2022": "-",    # bullet
    "\u00a0": " ",    # espaco nao-quebravel
    # Letras gregas que podem ter sido digitadas no lugar das latinas.
    "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u0391": "A",
    "\u0392": "B", "\u0395": "E", "\u0397": "H", "\u0399": "I",
    "\u039a": "K", "\u03a1": "P", "\u03a4": "T", "\u03a5": "Y",
    "\u03a7": "X", "\u0396": "Z",
}


def texto_pdf(texto: str) -> str:
    """Normaliza um texto para os limites das fontes core (latin-1) do PDF."""
    if not isinstance(texto, str):
        texto = str(texto)
    for origem, destino in _MAPA_PDF.items():
        texto = texto.replace(origem, destino)
    # Rede de seguranca: troca qualquer caractere fora do latin-1 por "?".
    return texto.encode("latin-1", errors="replace").decode("latin-1")


def nome_arquivo_pdf(
    aluno: str, modulo: int, modo_simulado: bool, quando: datetime | None = None
) -> str:
    """Monta o nome do arquivo PDF do relatorio."""
    quando = quando or datetime.now()
    slug = "".join(c if c.isalnum() else "_" for c in aluno).strip("_") or "aluno"
    data = quando.strftime("%Y%m%d_%H%M")
    if modo_simulado:
        return f"relatorio_{slug}_simulado_{data}.pdf"
    return f"relatorio_{slug}_modulo{modulo}_{data}.pdf"


def gerar_pdf(dados: dict, raiz: Path | None = None) -> bytes:
    """Monta o relatorio em PDF (fpdf2) e retorna os bytes.

    Compatível com fpdf2 2.x: usa `pdf.output()` (sem o parâmetro `dest`,
    deprecado desde 2.2.0) e largura explícita nos `multi_cell`.
    """
    from fpdf import FPDF

    raiz = raiz or config.RAIZ

    aluno = texto_pdf(dados.get("aluno", ""))
    modulo = dados.get("modulo")
    respondidas = int(dados.get("respondidas", 0) or 0)
    acertos = int(dados.get("acertos", 0) or 0)
    erros = int(dados.get("erros", 0) or 0)
    modo_simulado = bool(dados.get("modo_simulado"))
    registros_erro = dados.get("registros_erro") or []
    porcentagem = (acertos / respondidas * 100) if respondidas else 0.0

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    margem_esq = pdf.l_margin

    def linha(txt: str, altura: float = 7, negrito: bool = False) -> None:
        """Escreve uma linha simples ocupando toda a largura util."""
        pdf.set_font("Helvetica", "B" if negrito else "", 11)
        pdf.set_x(margem_esq)
        largura = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.multi_cell(largura, altura, texto_pdf(txt))

    def paragrafo(
        txt: str, altura: float = 6, negrito: bool = False,
        cor: tuple[int, int, int] | None = None,
    ) -> None:
        """Escreve um paragrafo com quebra de linha automatica."""
        pdf.set_font("Helvetica", "B" if negrito else "", 11)
        if cor is not None:
            pdf.set_text_color(*cor)
        pdf.set_x(margem_esq)
        largura = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.multi_cell(largura, altura, texto_pdf(txt))
        if cor is not None:
            pdf.set_text_color(0, 0, 0)

    # Cabecalho
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_x(margem_esq)
    pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 10,
                   "Quiz MSA - Relatorio de Desempenho")
    linha(f"Aluno: {aluno}")
    if modo_simulado:
        linha(f"Simulado: {dados.get('fases_simulado', '')}")
    else:
        linha(f"Modulo: {modulo}")
    linha(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    pdf.ln(2)

    # Desempenho.
    linha(f"Desempenho: {porcentagem:.1f}% de acertos", altura=8, negrito=True)
    linha(f"Acertos: {acertos} de {respondidas} respondidas")

    # Evidencia de monitoramento (somente simulado).
    if modo_simulado:
        saidas = int(dados.get("saidas_tela", 0) or 0)
        if saidas > 0:
            paragrafo(
                f"Monitoramento: o aluno saiu da tela {saidas} vez(es).",
                cor=(180, 0, 0),
            )
        else:
            paragrafo("Monitoramento: o aluno permaneceu na tela.")

    pdf.ln(3)

    # Revisao das questoes incorretas (sem listar as certas).
    if erros and registros_erro:
        linha("Revisao das questoes incorretas", altura=8, negrito=True)

        for registro in registros_erro:
            pdf.ln(1)
            paragrafo(f"Questao {registro['numero']}", negrito=True)
            paragrafo(f"Enunciado: {registro['enunciado']}")

            img_rel = registro.get("imagem")
            if img_rel and (raiz / img_rel).exists():
                try:
                    caminho = raiz / img_rel
                    with Image.open(caminho) as arquivo:
                        largura, altura = arquivo.size

                    # Limites maximos no PDF, em milimetros (config).
                    largura_maxima, altura_maxima = config.PDF_FIGURA_LIMITE_MM
                    fator = min(
                        largura_maxima / largura,
                        altura_maxima / altura,
                    )
                    largura_pdf = largura * fator
                    altura_pdf = altura * fator

                    pdf.ln(1)
                    pdf.set_x(margem_esq)
                    pdf.image(str(caminho), w=largura_pdf, h=altura_pdf)
                    pdf.set_x(margem_esq)
                except Exception:
                    pass

            pdf.ln(1)
            paragrafo(f"Sua resposta: {registro['resposta_aluno']}", cor=(180, 0, 0))
            paragrafo(
                f"Resposta correta: {registro['resposta_correta']}",
                cor=(0, 130, 0),
            )
            pdf.ln(3)
    else:
        paragrafo("Parabens! Voce acertou todas as questoes.")

    saida = pdf.output()  # fpdf2 2.x: retorna bytearray
    return bytes(saida)
