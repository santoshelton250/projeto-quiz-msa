"""s
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

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from app import config
from app.services.imagens import (
    largura_relatorio,
    preparar_imagem,
    preparar_imagem_questao,
)
from app.services.pdf import gerar_pdf, nome_arquivo_pdf
from app.services.simulados import gerar_questoes_simulado
# --------------------------------------------------------------------------- #
# Configuracao geral
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Quiz MSA",
    page_icon="🎵",
    layout="wide",                 # aproveita telas largas (PC); empilha no celular
    initial_sidebar_state="collapsed",
)

RAIZ = config.RAIZ
ARQUIVO_JSON = config.ARQUIVO_JSON
PASTA_RELATORIOS = config.PASTA_RELATORIOS

LETRAS = config.LETRAS

# Ajustes de estilo para melhor leitura no celular (texto e botoes maiores).
st.markdown(
    """
    <style>
        [data-testid="stImage"] img {
        max-width: 100% !important;
        height: auto !important;
        object-fit: contain;
    }
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
@st.cache_data(show_spinner=False, ttl=60)
def carregar_dados() -> dict:
    """Le o banco de questoes gerado pelo extrator."""
    if not ARQUIVO_JSON.exists():
        return {"fases": [], "total_questoes": 0, "total_figuras": 0}
    with open(ARQUIVO_JSON, encoding="utf-8") as f:
        return json.load(f)


DADOS = carregar_dados()
FASES = {fase["fase"]: fase["questoes"] for fase in DADOS.get("fases", [])}


# --------------------------------------------------------------------------- #
# Geracao de simulado (somente instrutor, protegido por senha)
# --------------------------------------------------------------------------- #
# A logica de distribuicao/sorteio vive em app/services/simulados.py
# (testada em tests/test_simulados.py). Aqui so chamamos gerar_questoes_simulado.


def senha_instrutor_confere(tentativa: str) -> bool:
    """Compara a senha digitada com a guardada em .streamlit/secrets.toml."""
    try:
        senha_correta = str(st.secrets.get("senha_instrutor", ""))
    except Exception:
        # Sem secrets configurado: nao autoriza (seguro por padrao).
        return False
    if not senha_correta:
        return False
    return tentativa == senha_correta


# --------------------------------------------------------------------------- #
# Detector de troca de aba/app (Page Visibility API)
# --------------------------------------------------------------------------- #
def _render_detector_visibilidade() -> None:
    """Conta quantas vezes a pagina ficou oculta (aluno saiu da tela).

    Estrategia: o JavaScript acumula a contagem no localStorage do navegador e
    grava o valor na URL (hash). O Python le esse hash via st.query_params e
    sincroniza para o session_state. Nao bloqueia nada: apenas registra.

    Limitacao honesta: o navegador nao permite IMPEDIR a troca de aba, apenas
    detecta. O registro serve como evidencia para o professor no relatorio.
    """
    components.html(
        """<div id="silent"></div>
        <script>
        (function () {
            const CHAVE = "quiz_msa_saidas_tela";
            try {
                if (localStorage.getItem(CHAVE) === null) {
                    localStorage.setItem(CHAVE, "0");
                }
                function contar() {
                    let n = parseInt(localStorage.getItem(CHAVE) || "0", 10);
                    n += 1;
                    localStorage.setItem(CHAVE, String(n));
                    // Publica a contagem na URL do frame pai para o Python ler.
                    try {
                        const base = window.parent.location.href.split("#")[0];
                        window.parent.location.hash = "saidas=" + n;
                    } catch (e) {}
                }
                document.addEventListener("visibilitychange", function () {
                    if (document.visibilityState === "hidden") { contar(); }
                });
                window.addEventListener("blur", function () {
                    const agora = Date.now();
                    const ultimo = parseInt(localStorage.getItem(CHAVE + "_ts") || "0", 10);
                    if (agora - ultimo > 500) {
                        localStorage.setItem(CHAVE + "_ts", String(agora));
                        contar();
                    }
                });
                // Repassa o valor atual para a URL assim que carrega.
                const atual = localStorage.getItem(CHAVE) || "0";
                try {
                    window.parent.location.hash = "saidas=" + atual;
                } catch (e) {}
            } catch (e) {}
        })();
        </script>""",
        height=0,
        width=0,
    )


def _sincronizar_saidas_tela() -> None:
    """Le o hash 'saidas=N' da URL e guarda no session_state (so aumenta)."""
    try:
        params = st.query_params
        valor = params.get("saidas")
        if valor is not None:
            n = int(str(valor).split("=")[-1] if "=" in str(valor) else valor)
            atual = int(st.session_state.get("saidas_tela", 0) or 0)
            if n > atual:
                st.session_state.saidas_tela = n
    except Exception:
        pass


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
        "modo_simulado": False,      # True quando a sessao eh um simulado
        "fases_simulado": "",        # texto "Fase 1 a 16" para exibicao
        "senha_liberada": False,     # instrutor autenticou nesta sessao
        "saidas_tela": 0,            # n de vezes que saiu da tela no simulado
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
        "Fase",
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

    st.divider()

    # --- Area do instrutor: gerar simulado (protegido por senha) ---
    with st.expander("🔒 Gerar simulado (instrutor)"):
        st.caption(
            "Área exclusiva do instrutor/professor. Informe a senha para "
            "gerar um simulado com questões sorteadas do banco."
        )
        senha_digitada = st.text_input(
            "Senha do instrutor",
            type="password",
            key="campo_senha",
        )
        if st.button("Liberar geração", use_container_width=True):
            if senha_instrutor_confere(senha_digitada):
                st.session_state.senha_liberada = True
                st.success("Senha correta. Preencha os dados do simulado abaixo.")
            else:
                st.session_state.senha_liberada = False
                st.error("Senha incorreta.")

        if st.session_state.get("senha_liberada"):
            _form_gerar_simulado()


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
        st.warning("Digite um número de fase válido.")
        return
    if modulo not in FASES:
        st.warning(
            f"Fase {modulo} não encontrada. "
            f"Fases disponíveis: {modulos_disponiveis}."
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
                f"A questão {numero_inicial} não existe na fase {modulo}. "
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
# Formulario de geracao de simulado (exibido apos senha correta)
# --------------------------------------------------------------------------- #
def _form_gerar_simulado() -> None:
    modulos_disponiveis = sorted(FASES.keys())
    minimo, maximo = modulos_disponiveis[0], modulos_disponiveis[-1]

    st.markdown("**Configurar simulado**")
    col1, col2 = st.columns(2)
    with col1:
        fase_ini_txt = st.text_input(
            "Fase inicial", key="sim_fase_ini",
            placeholder=f"{minimo} a {maximo}",
        )
    with col2:
        fase_fim_txt = st.text_input(
            "Fase final", key="sim_fase_fim",
            placeholder=f"{minimo} a {maximo}",
        )

    total_txt = st.text_input(
        "Número de questões", key="sim_total",
        placeholder="Ex.: 30",
    )

    if st.button("Gerar simulado", type="primary", use_container_width=True):
        _iniciar_simulado(
            fase_ini_txt, fase_fim_txt, total_txt, modulos_disponiveis
        )


def _iniciar_simulado(
    fase_ini_txt: str, fase_fim_txt: str, total_txt: str,
    modulos_disponiveis: list[int],
) -> None:
    # Valida fase inicial e final.
    try:
        fase_ini = int(str(fase_ini_txt).strip())
        fase_fim = int(str(fase_fim_txt).strip())
    except (TypeError, ValueError):
        st.warning("Digite números de fase válidos.")
        return

    if fase_ini > fase_fim:
        st.warning("A fase inicial deve ser menor ou igual à fase final.")
        return

    fases_existentes = [f for f in modulos_disponiveis
                        if fase_ini <= f <= fase_fim]
    if not fases_existentes:
        st.warning(
            f"Não há fases entre {fase_ini} e {fase_fim}. "
            f"Fases disponíveis: {modulos_disponiveis}."
        )
        return

    # Valida total de questoes.
    try:
        total = int(str(total_txt).strip())
    except (TypeError, ValueError):
        st.warning("Digite um número de questões válido.")
        return
    if total <= 0:
        st.warning("O número de questões deve ser maior que zero.")
        return

    disponiveis_total = sum(
        len(FASES[f]) for f in fases_existentes
    )
    if total > disponiveis_total:
        st.warning(
            f"Você pediu {total} questões, mas as fases selecionadas têm "
            f"apenas {disponiveis_total} no total."
        )
        return

    questoes = gerar_questoes_simulado(FASES, fase_ini, fase_fim, total)
    if not questoes:
        st.warning("Não foi possível gerar o simulado. Verifique os dados.")
        return

    # Aplica a sessao do simulado. Nome do aluno vem do campo da tela inicial.
    nome = (st.session_state.get("campo_nome") or "").strip()
    if not nome:
        st.warning(
            "Preencha o nome do aluno no campo acima antes de gerar o simulado."
        )
        return

    st.session_state.aluno = nome
    st.session_state.modulo = fase_ini
    st.session_state.questoes = questoes
    st.session_state.indice = 0
    st.session_state.respondidas = 0
    st.session_state.acertos = 0
    st.session_state.erros = 0
    st.session_state.registros_erro = []
    st.session_state.ja_respondida = False
    st.session_state.ultimo_acerto = None
    st.session_state.pdf_bytes = None
    st.session_state.modo_simulado = True
    st.session_state.fases_simulado = (
        f"Fase {fase_ini}" if fase_ini == fase_fim
        else f"Fases {fase_ini} a {fase_fim}"
    )
    st.session_state.saidas_tela = 0  # zera o contador para este simulado
    # Seguranca: destrava a senha imediatamente. Para gerar outro simulado,
    # o instrutor precisara digitar a senha novamente.
    st.session_state.senha_liberada = False
    st.session_state.tela = "quiz"
    st.rerun()



# --------------------------------------------------------------------------- #
# Tela 2 - Quiz
# --------------------------------------------------------------------------- #
def _marcar_alternativa(chave: str, indice: int) -> None:
    """Guarda a alternativa selecionada (mutuamente exclusiva)."""
    st.session_state[chave] = indice


def _navegacao_pos_resposta() -> None:
    """Feedback (sem revelar a correta) + botoes Proxima/Terminar."""
    indice = st.session_state.indice
    questoes = st.session_state.questoes

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


def _tela_quiz_alternativas_ilustradas(questao: dict, numero) -> None:
    """Layout especial para questoes cujas ALTERNATIVAS tem figura propria.

    Usado SOMENTE quando a questao possui o campo opcional
    `imagens_alternativas` (dict letra -> caminho). Questoes sem esse campo
    seguem o fluxo tradicional do tela_quiz() e nao passam por aqui.

    Estrutura: enunciado -> figura principal (referencia, separada) ->
    cada alternativa (letra + sua figura; letras sem figura = so texto).
    """
    imgs_alt = questao.get("imagens_alternativas") or {}
    principal = questao.get("imagem")
    tem_principal = bool(principal) and (RAIZ / principal).exists()

    # Enunciado destacado.
    st.markdown(f"**{questao['enunciado']}**")

        # Figura principal de referencia (nao vinculada a nenhuma alternativa),
    # separada do bloco de alternativas.
    if tem_principal:
        st.caption("Figura de referência:")
        largura_p, altura_p = config.FIGURA_ALTERNATIVA_PRINCIPAL
        img_principal = preparar_imagem(RAIZ / principal, largura_p, altura_p)
        st.image(img_principal, width="content")

    st.write("")

    chave_sel = f"alt_sel_{numero}"
    alternativas = questao["alternativas"]

    # Alternativas ilustradas, uma por linha (empilham no celular).
    for i, texto in enumerate(alternativas):
        letra = LETRAS[i]
        caminho_alt = imgs_alt.get(letra)
        tem_img_alt = bool(caminho_alt) and (RAIZ / caminho_alt).exists()

        with st.container(border=True):
            if tem_img_alt:
                # PC: letra+radio a esquerda, figura a direita (empilha no mobile).
                col_marca, col_img = st.columns([2, 3], gap="small")
                with col_marca:
                    st.radio(
                        f"Alternativa {letra}",
                        options=[letra],
                        index=(0 if st.session_state.get(chave_sel) == i else None),
                        key=f"alt_radio_{numero}_{letra}",
                        disabled=st.session_state.ja_respondida,
                        on_change=_marcar_alternativa,
                        args=(chave_sel, i),
                    )
                with col_img:
                    largura_a, altura_a = config.FIGURA_ALTERNATIVA_IMAGEM
                    img_alt = preparar_imagem(RAIZ / caminho_alt, largura_a, altura_a)
                    st.image(img_alt, width="content")
            else:
                # Alternativa apenas textual (ex.: "Nenhuma das alternativas").
                st.radio(
                    f"{letra}) {texto}",
                    options=[letra],
                    index=(0 if st.session_state.get(chave_sel) == i else None),
                    key=f"alt_radio_{numero}_{letra}",
                    disabled=st.session_state.ja_respondida,
                    on_change=_marcar_alternativa,
                    args=(chave_sel, i),
                )

    st.divider()

    if not st.session_state.ja_respondida:
        if st.button("Confirmar resposta", type="primary", use_container_width=True):
            escolhida = st.session_state.get(chave_sel)
            if escolhida is None:
                st.warning("Selecione uma alternativa antes de confirmar.")
                return
            _registrar_resposta(questao, escolhida)
            st.rerun()
        return

    _navegacao_pos_resposta()


def tela_quiz() -> None:
    questoes = st.session_state.questoes
    indice = st.session_state.indice

    # No simulado: monitora troca de aba/app (apenas registra, nao impede).
    simulado_ativo = st.session_state.get("modo_simulado")
    if simulado_ativo:
        _render_detector_visibilidade()
        _sincronizar_saidas_tela()

    if not questoes or indice >= len(questoes):
        st.session_state.tela = "relatorio"
        st.rerun()
        return

    questao = questoes[indice]
    # No simulado exibimos numero sequencial (1, 2, 3...); no quiz normal,
    # o numero real da questao no banco.
    simulado = st.session_state.get("modo_simulado")
    if simulado:
        numero = questao.get("numero_exibicao", indice + 1)
        titulo = f"### Simulado — Questão {numero}"
    else:
        numero = questao["numero"]
        titulo = f"### Fase {st.session_state.modulo} — Questão {numero}"

    alternativas = questao["alternativas"]
    tem_imagem = bool(questao.get("imagem")) and (RAIZ / questao["imagem"]).exists()

    st.markdown(titulo)
    if simulado_ativo and int(st.session_state.get("saidas_tela", 0) or 0) > 0:
        st.warning(
            "⚠️ Detectamos que você saiu da tela do simulado. "
            "Isso está sendo registrado no relatório."
        )
    st.caption(
        f"Aluno: {st.session_state.aluno}  |  "
        f"Questão {indice + 1} de {len(questoes)}"
    )
    st.progress((indice) / len(questoes))
    st.divider()

    # DESVIO OPCIONAL: questoes com figuras individuais nas alternativas usam
    # um layout dedicado. Questoes sem o campo seguem o fluxo tradicional.
    if questao.get("imagens_alternativas"):
        _tela_quiz_alternativas_ilustradas(questao, numero)
        return

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
                imagem = preparar_imagem_questao(RAIZ / questao["imagem"])
                st.image(
                    imagem,
                    caption='Figura da questao',
                    width=(
                        'stretch'
                        if imagem.width > config.FIGURA_LARGURA_STRETCH_PX
                        else 'content'
                    ),
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
        # No simulado usamos o numero sequencial; no quiz normal, o do banco.
        if st.session_state.get("modo_simulado"):
            numero_exibir = questao.get("numero_exibicao", questao["numero"])
        else:
            numero_exibir = questao["numero"]
        st.session_state.registros_erro.append(
            {
                "numero": numero_exibir,
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
    if st.session_state.get("modo_simulado"):
        st.markdown(f"**Simulado:** {st.session_state.get('fases_simulado', '')}")
    else:
        st.markdown(f"**Fase:** {st.session_state.modulo}")
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

    # Evidencia de comportamento (somente no simulado).
    if st.session_state.get("modo_simulado"):
        saidas = int(st.session_state.get("saidas_tela", 0) or 0)
        if saidas > 0:
            st.warning(
                f"⚠️ Registro de monitoramento: o aluno saiu da tela do "
                f"simulado **{saidas} vez(es)**."
            )
        else:
            st.info(
                "✅ Monitoramento: o aluno permaneceu na tela durante todo "
                "o simulado."
            )
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
                    caminho = RAIZ / registro["imagem"]

                    with Image.open(caminho) as arquivo:
                        largura, altura = arquivo.size

                    largura_final = largura_relatorio(largura, altura)

                    st.image(
                        str(caminho),
                        width=largura_final
                    )

                st.markdown(f"❌ **Sua resposta:** {registro['resposta_aluno']}")
                st.markdown(
                    f"✅ **Resposta correta:** {registro['resposta_correta']}"
                )

    st.divider()

        # Geracao/Download do PDF.
    if st.session_state.pdf_bytes is None:
        st.session_state.pdf_bytes = gerar_pdf(_dados_relatorio())
    st.download_button(
        "📄 Baixar relatório em PDF",
        data=st.session_state.pdf_bytes,
        file_name=_nome_arquivo_pdf(),
        mime="application/pdf",
        use_container_width=True,
    )

    _botoes_finais()


def _dados_relatorio() -> dict:
    """Empacota o estado da sessao nos dados que o gerador de PDF espera."""
    return {
        "aluno": st.session_state.aluno,
        "modulo": st.session_state.modulo,
        "respondidas": st.session_state.respondidas,
        "acertos": st.session_state.acertos,
        "erros": st.session_state.erros,
        "modo_simulado": bool(st.session_state.get("modo_simulado")),
        "fases_simulado": st.session_state.get("fases_simulado", ""),
        "saidas_tela": int(st.session_state.get("saidas_tela", 0) or 0),
        "registros_erro": st.session_state.registros_erro,
    }


def _nome_arquivo_pdf() -> str:
    return nome_arquivo_pdf(
        st.session_state.aluno,
        st.session_state.modulo,
        bool(st.session_state.get('modo_simulado')),
    )

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

    # No simulado, oferece saida para a tela inicial (volta a pedir senha).
    if st.session_state.get("modo_simulado"):
        if st.button(
            "🔚 Sair do simulado (voltar ao início)",
            use_container_width=True,
        ):
            reiniciar()  # limpa a sessao: senha volta a ser exigida
            st.rerun()


def tela_encerrado() -> None:
    st.title("🎵 Quiz MSA")
    st.success("Sessão encerrada. Você já pode fechar esta aba.")
    if st.button("Iniciar novamente", use_container_width=True):
        reiniciar()
        st.rerun()


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
