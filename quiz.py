"""
Quiz MSA - aplicacao interativa (Streamlit).

Fluxo:
  1. Tela inicial: nome do aluno (digitado), MODULO e QUESTAO digitados.
  2. Quiz: cada questao mostra enunciado (+ figura, se houver) e alternativas.
     Ao responder, recebe apenas o feedback CORRETO/INCORRETO (sem revelar a
     resposta certa). Botoes: "Proxima pergunta" e "Terminar e emitir relatorio".
  3. Relatorio: nome, desempenho (%), acertos e erros; para cada erro:
     enunciado -> resposta do aluno -> resposta correta. Pode ser baixado em PDF.
     Botoes: "Encerrar" e "Reiniciar".

Os dados vem de dados/questoes.json (gerado por extrator.py). O app NAO le
PDFs em tempo de execucao.

Executar:
    streamlit run quiz.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

# --------------------------------------------------------------------------- #
# Configuracao geral
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Quiz MSA",
    page_icon="🎵",
    layout="wide",                 # aproveita telas largas (PC); empilha no celular
    initial_sidebar_state="collapsed",
)

RAIZ = Path(__file__).resolve().parent
ARQUIVO_JSON = RAIZ / "dados" / "questoes.json"
PASTA_RELATORIOS = RAIZ / "relatorios"

LETRAS = "ABCDEFGH"

# Ajustes de estilo para melhor leitura no celular (texto e botoes maiores).
st.markdown(
    """
    <style>
    @media (max-width: 640px) {
        .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
        h1, h2, h3 { font-size: 1.3rem !important; }
        .stRadio label { font-size: 1.05rem !important; }
        .stButton button { width: 100%; font-size: 1.05rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Carregamento dos dados
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def carregar_dados() -> dict:
    """Le o banco de questoes gerado pelo extrator."""
    if not ARQUIVO_JSON.exists():
        return {"fases": [], "total_questoes": 0, "total_figuras": 0}
    with open(ARQUIVO_JSON, encoding="utf-8") as f:
        return json.load(f)


DADOS = carregar_dados()
FASES = {fase["fase"]: fase["questoes"] for fase in DADOS.get("fases", [])}


# --------------------------------------------------------------------------- #
# Estado da sessao
# --------------------------------------------------------------------------- #
def inicializar_estado() -> None:
    padroes = {
        "tela": "inicio",            # inicio | quiz | relatorio | encerrado
        "aluno": "",
        "modulo": None,
        "questoes": [],              # questoes da sessao atual
        "indice": 0,
        "respondidas": 0,
        "acertos": 0,
        "erros": 0,
        "registros_erro": [],
        "ja_respondida": False,
        "ultimo_acerto": None,
        "pdf_bytes": None,           # relatorio em PDF (cache da sessao)
    }
    for chave, valor in padroes.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def reiniciar() -> None:
    for chave in list(st.session_state.keys()):
        del st.session_state[chave]
    inicializar_estado()


# --------------------------------------------------------------------------- #
# Tela 1 - Inicio (campos digitaveis)
# --------------------------------------------------------------------------- #
def tela_inicio() -> None:
    st.title("🎵 Quiz MSA")
    st.write("Bem-vindo! Preencha os campos abaixo para começar.")

    if not FASES:
        st.error(
            "Nenhuma questão encontrada. Rode o extrator primeiro: "
            "`python extrator.py`."
        )
        return

    modulos_disponiveis = sorted(FASES.keys())

    # Campos empilhados (um abaixo do outro).
    nome = st.text_input("Nome do aluno", key="campo_nome")
    modulo = st.text_input(
        "Módulo (fase)",
        key="campo_modulo",
        placeholder=f"Digite um número de {modulos_disponiveis[0]} a "
        f"{modulos_disponiveis[-1]}",
    )
    numero_txt = st.text_input(
        "Questão (nº)",
        key="campo_numero",
        placeholder="Ex.: 1 (começa a partir desta questão)",
    )

    if st.button("Iniciar Quiz", type="primary", use_container_width=True):
        _iniciar_quiz(nome, modulo, numero_txt, modulos_disponiveis)


def _iniciar_quiz(
    nome: str, modulo_txt: str, numero_txt: str, modulos_disponiveis: list[int]
) -> None:
    if not nome.strip():
        st.warning("Por favor, insira o nome do aluno.")
        return

    # Valida modulo digitado.
    try:
        modulo = int(str(modulo_txt).strip())
    except (TypeError, ValueError):
        st.warning("Digite um número de módulo válido.")
        return
    if modulo not in FASES:
        st.warning(
            f"Módulo {modulo} não encontrado. "
            f"Módulos disponíveis: {modulos_disponiveis}."
        )
        return

    numeros = [q["numero"] for q in FASES[modulo]]

    # Questao inicial: se em branco, comeca da primeira.
    if str(numero_txt).strip() == "":
        numero_inicial = numeros[0]
    else:
        try:
            numero_inicial = int(str(numero_txt).strip())
        except (TypeError, ValueError):
            st.warning("Digite um número de questão válido.")
            return
        if numero_inicial not in numeros:
            st.warning(
                f"A questão {numero_inicial} não existe no módulo {modulo}. "
                f"Faixa disponível: {numeros[0]} a {numeros[-1]}."
            )
            return

    selecionadas = [q for q in FASES[modulo] if q["numero"] >= numero_inicial]
    if not selecionadas:
        st.warning("Nenhuma questão para iniciar.")
        return

    st.session_state.aluno = nome.strip()
    st.session_state.modulo = modulo
    st.session_state.questoes = selecionadas
    st.session_state.indice = 0
    st.session_state.respondidas = 0
    st.session_state.acertos = 0
    st.session_state.erros = 0
    st.session_state.registros_erro = []
    st.session_state.ja_respondida = False
    st.session_state.ultimo_acerto = None
    st.session_state.pdf_bytes = None
    st.session_state.tela = "quiz"
    st.rerun()


# --------------------------------------------------------------------------- #
# Tela 2 - Quiz
# --------------------------------------------------------------------------- #
def tela_quiz() -> None:
    questoes = st.session_state.questoes
    indice = st.session_state.indice

    if not questoes or indice >= len(questoes):
        st.session_state.tela = "relatorio"
        st.rerun()
        return

    questao = questoes[indice]
    numero = questao["numero"]
    alternativas = questao["alternativas"]
    tem_imagem = bool(questao.get("imagem")) and (RAIZ / questao["imagem"]).exists()

    st.markdown(f"### Módulo {st.session_state.modulo} — Questão {numero}")
    st.caption(
        f"Aluno: {st.session_state.aluno}  |  "
        f"Questão {indice + 1} de {len(questoes)}"
    )
    st.progress((indice) / len(questoes))
    st.divider()

    # Layout: no PC, enunciado a esquerda e figura a direita; no celular as
    # colunas empilham automaticamente (comportamento nativo do Streamlit).
    if tem_imagem:
        col_texto, col_img = st.columns([3, 2], gap="large")
    else:
        col_texto, col_img = st.container(), None

    alternativa_escolhida = None
    with col_texto:
        st.markdown(f"**{questao['enunciado']}**")
        st.write("")
        rotulos = [f"{LETRAS[i]}) {t}" for i, t in enumerate(alternativas)]
        alternativa_escolhida = st.radio(
            "Selecione sua resposta:",
            options=list(range(len(alternativas))),
            format_func=lambda i: rotulos[i],
            index=None,
            key=f"radio_{numero}",
            disabled=st.session_state.ja_respondida,
        )

    if col_img is not None:
        with col_img:
            st.image(
                str(RAIZ / questao["imagem"]),
                caption="Figura da questão",
                width=340,
            )

    st.divider()

    if not st.session_state.ja_respondida:
        if st.button("Confirmar resposta", type="primary", use_container_width=True):
            if alternativa_escolhida is None:
                st.warning("Selecione uma alternativa antes de confirmar.")
                return
            _registrar_resposta(questao, alternativa_escolhida)
            st.rerun()
        return

    # Ja respondida: apenas o feedback (sem revelar a resposta correta).
    if st.session_state.get("ultimo_acerto"):
        st.success("✅ Resposta correta!")
    else:
        st.error("❌ Resposta incorreta.")

    col_a, col_b = st.columns(2)
    tem_proxima = indice < len(questoes) - 1
    with col_a:
        if tem_proxima:
            if st.button("Próxima pergunta", use_container_width=True):
                st.session_state.indice += 1
                st.session_state.ja_respondida = False
                st.session_state.ultimo_acerto = None
                st.rerun()
        else:
            st.info("Esta foi a última pergunta.")
    with col_b:
        if st.button(
            "Terminar e emitir relatório",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.tela = "relatorio"
            st.rerun()


def _registrar_resposta(questao: dict, indice_escolhido: int) -> None:
    """Atualiza contadores e registra o erro (se houver)."""
    correta = questao["correta"]
    acertou = indice_escolhido == correta

    st.session_state.respondidas += 1
    if acertou:
        st.session_state.acertos += 1
    else:
        st.session_state.erros += 1
        st.session_state.registros_erro.append(
            {
                "numero": questao["numero"],
                "enunciado": questao["enunciado"],
                "imagem": questao.get("imagem"),
                "resposta_aluno": questao["alternativas"][indice_escolhido],
                "resposta_correta": questao["alternativas"][correta],
            }
        )

    st.session_state.ultimo_acerto = acertou
    st.session_state.ja_respondida = True


# --------------------------------------------------------------------------- #
# Tela 3 - Relatorio
# --------------------------------------------------------------------------- #
def tela_relatorio() -> None:
    st.title("📊 Relatório de Desempenho")
    st.markdown(f"**Aluno:** {st.session_state.aluno}")
    st.markdown(f"**Módulo:** {st.session_state.modulo}")
    st.divider()

    respondidas = st.session_state.respondidas
    acertos = st.session_state.acertos
    erros = st.session_state.erros

    if respondidas == 0:
        st.warning("Nenhuma questão foi respondida.")
        _botoes_finais()
        return

    porcentagem = (acertos / respondidas) * 100
    col1, col2, col3 = st.columns(3)
    col1.metric("Desempenho", f"{porcentagem:.1f}%")
    col2.metric("Acertos", acertos)
    col3.metric("Erros", erros)
    st.divider()

    if erros == 0:
        st.success("Parabéns! Você acertou todas as questões respondidas.")
    else:
        st.subheader("Revisão das questões incorretas")
        for i, registro in enumerate(st.session_state.registros_erro, start=1):
            with st.container(border=True):
                st.markdown(f"**Questão {registro['numero']}**")
                st.markdown(f"*Enunciado:* {registro['enunciado']}")
                if registro.get("imagem") and (RAIZ / registro["imagem"]).exists():
                    st.image(str(RAIZ / registro["imagem"]), width=300)
                st.markdown(f"❌ **Sua resposta:** {registro['resposta_aluno']}")
                st.markdown(
                    f"✅ **Resposta correta:** {registro['resposta_correta']}"
                )

    st.divider()

    # Geracao/Download do PDF.
    if st.session_state.pdf_bytes is None:
        st.session_state.pdf_bytes = gerar_pdf()
    st.download_button(
        "📄 Baixar relatório em PDF",
        data=st.session_state.pdf_bytes,
        file_name=_nome_arquivo_pdf(),
        mime="application/pdf",
        use_container_width=True,
    )

    _botoes_finais()


def _nome_arquivo_pdf() -> str:
    aluno = "".join(
        c if c.isalnum() else "_" for c in st.session_state.aluno
    ).strip("_") or "aluno"
    data = datetime.now().strftime("%Y%m%d_%H%M")
    return f"relatorio_{aluno}_modulo{st.session_state.modulo}_{data}.pdf"


def _botoes_finais() -> None:
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Reiniciar", use_container_width=True):
            reiniciar()
            st.rerun()
    with col_b:
        if st.button("Encerrar", type="primary", use_container_width=True):
            st.session_state.tela = "encerrado"
            st.rerun()


def tela_encerrado() -> None:
    st.title("🎵 Quiz MSA")
    st.success("Sessão encerrada. Você já pode fechar esta aba.")
    if st.button("Iniciar novamente", use_container_width=True):
        reiniciar()
        st.rerun()


# --------------------------------------------------------------------------- #
# Geracao do PDF do relatorio
# --------------------------------------------------------------------------- #
def gerar_pdf() -> bytes:
    """Monta o relatorio em PDF (fpdf2) e retorna os bytes."""
    from fpdf import FPDF

    aluno = st.session_state.aluno
    modulo = st.session_state.modulo
    respondidas = st.session_state.respondidas
    acertos = st.session_state.acertos
    erros = st.session_state.erros
    porcentagem = (acertos / respondidas * 100) if respondidas else 0.0

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Cabecalho
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Quiz MSA - Relatorio de Desempenho", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Aluno: {aluno}", ln=1)
    pdf.cell(0, 7, f"Modulo: {modulo}", ln=1)
    pdf.cell(
        0,
        7,
        f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ln=1,
    )
    pdf.ln(2)

    # Desempenho (nome do aluno ja consta no cabecalho).
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Desempenho: {porcentagem:.1f}% de acertos", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Acertos: {acertos} de {respondidas} respondidas", ln=1)
    pdf.ln(3)

    # Revisao das questoes incorretas (sem listar as certas).
    if erros and st.session_state.registros_erro:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Revisao das questoes incorretas", ln=1)
        pdf.set_font("Helvetica", "", 11)

        for registro in st.session_state.registros_erro:
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 6, f"Questao {registro['numero']}")
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, f"Enunciado: {registro['enunciado']}")

            img_rel = registro.get("imagem")
            if img_rel and (RAIZ / img_rel).exists():
                try:
                    pdf.ln(1)
                    pdf.image(str(RAIZ / img_rel), w=70)
                except Exception:
                    pass

            pdf.ln(1)
            pdf.set_text_color(180, 0, 0)
            pdf.multi_cell(0, 6, f"Sua resposta: {registro['resposta_aluno']}")
            pdf.set_text_color(0, 130, 0)
            pdf.multi_cell(
                0, 6, f"Resposta correta: {registro['resposta_correta']}"
            )
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)
    else:
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, "Parabens! Voce acertou todas as questoes.")

    saida = pdf.output(dest="S")
    # fpdf2 (v1.x) devolve str codificada em latin-1 quando dest="S".
    if isinstance(saida, str):
        return saida.encode("latin-1", errors="replace")
    return bytes(saida)


# --------------------------------------------------------------------------- #
# Roteador
# --------------------------------------------------------------------------- #
def main() -> None:
    inicializar_estado()
    tela = st.session_state.tela
    if tela == "inicio":
        tela_inicio()
    elif tela == "quiz":
        tela_quiz()
    elif tela == "relatorio":
        tela_relatorio()
    elif tela == "encerrado":
        tela_encerrado()


if __name__ == "__main__":
    main()
