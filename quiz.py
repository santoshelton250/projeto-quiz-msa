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
import random
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps, ImageEnhance
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
LIMIAR_IGUALITARIO = 30  # ate esse total usa distribuicao igualitaria


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


def _distribuir_igualitario(total: int, fases: list[int]) -> dict[int, int]:
    """Distribui o total o mais igualmente possivel entre as fases.

    Cada fase recebe no minimo 1 (desde que o total permita). As sobras sao
    distribuidas 1 a 1, de forma aleatoria, sem repetir enquanto houver fases
    que ainda possam receber.
    """
    k = len(fases)
    if total <= 0 or k == 0:
        return {f: 0 for f in fases}

    # Caso especial: pedido menor que o numero de fases -> sorteia quais fases
    # recebem 1 questao (as demais ficam com 0).
    if total < k:
        escolhidas = random.sample(fases, total)
        return {f: (1 if f in escolhidas else 0) for f in fases}

    base = total // k
    sobra = total - base * k

    dist = {f: base for f in fases}
    if sobra:
        # Sorteia quais fases recebem +1 (sem padrao fixo).
        for f in random.sample(fases, sobra):
            dist[f] += 1
    return dist


def _distribuir_proporcional(total: int, fases: list[int]) -> dict[int, int]:
    """Distribui proporcionalmente ao tamanho (n de questoes) de cada fase.

    Garante ao menos 1 questao por fase, desde que o total permita. O metodo
    do "maior resto" ajusta o arredondamento para bater exatamente o total.
    """
    k = len(fases)
    if total <= 0 or k == 0:
        return {f: 0 for f in fases}

    tamanhos = {f: len(FASES.get(f, [])) for f in fases}
    soma_tamanhos = sum(tamanhos.values())
    if soma_tamanhos == 0:
        return {f: 0 for f in fases}

    if total < k:
        escolhidas = random.sample(fases, total)
        return {f: (1 if f in escolhidas else 0) for f in fases}

    # Reserva 1 por fase e distribui o restante proporcionalmente.
    reserva = {f: 1 for f in fases}
    restante = total - k

    if restante == 0:
        return reserva

    cotas = {f: restante * tamanhos[f] / soma_tamanhos for f in fases}
    dist = {f: reserva[f] + int(cotas[f] // 1) for f in fases}

    # Ajusta pelo metodo do maior resto.
    alocado = sum(dist.values())
    faltam = total - alocado
    if faltam > 0:
        ordem = sorted(fases, key=lambda f: (cotas[f] % 1), reverse=True)
        i = 0
        while faltam > 0:
            f = ordem[i % len(ordem)]
            # Nao pedir mais do que a fase possui.
            if dist[f] < tamanhos[f]:
                dist[f] += 1
                faltam -= 1
            i += 1
            if i > len(ordem) * (len(ordem) + total):
                break
    elif faltam < 0:
        # Remove excedente das menores cotas (mantendo min 1).
        ordem = sorted(fases, key=lambda f: (cotas[f] % 1))
        i = 0
        while faltam < 0:
            f = ordem[i % len(ordem)]
            if dist[f] > 1:
                dist[f] -= 1
                faltam += 1
            i += 1
            if i > len(ordem) * (len(ordem) + total):
                break

    # Respeita o limite fisico de cada fase e redistribui o que sobrar.
    excedente = 0
    for f in fases:
        if dist[f] > tamanhos[f]:
            excedente += dist[f] - tamanhos[f]
            dist[f] = tamanhos[f]
    guard = 0
    while excedente > 0 and guard < 10000:
        guard += 1
        candidatas = [f for f in fases if dist[f] < tamanhos[f]]
        if not candidatas:
            break
        # Distribui onde ha mais espaco, sem padrao fixo.
        f = max(candidatas, key=lambda x: tamanhos[x] - dist[x])
        dist[f] += 1
        excedente -= 1

    return dist


def gerar_questoes_simulado(
    fase_ini: int, fase_fim: int, total: int
) -> list[dict]:
    """Sorteia e monta a lista de questoes do simulado.

    - Seleciona aleatoriamente as questoes dentro de cada fase.
    - Ordena por fase crescente e, dentro da fase, por numero crescente.
    - Cada questao recebe 'numero_exibicao' (1, 2, 3...) sem alterar o banco.
    """
    fases = sorted(f for f in FASES if fase_ini <= f <= fase_fim)
    if not fases:
        return []

    if total <= LIMIAR_IGUALITARIO:
        dist = _distribuir_igualitario(total, fases)
    else:
        dist = _distribuir_proporcional(total, fases)

    selecionadas: list[dict] = []
    for f in fases:
        disponiveis = FASES.get(f, [])
        qtd = min(dist.get(f, 0), len(disponiveis))
        if qtd <= 0:
            continue
        escolhidas = random.sample(disponiveis, qtd)
        for q in escolhidas:
            item = dict(q)  # copia: nao altera o banco original
            item["fase_origem"] = f
            item["numero_origem"] = q["numero"]
            selecionadas.append(item)

    # Ordena por fase crescente e numero crescente (sem embaralhar).
    selecionadas.sort(key=lambda q: (q["fase_origem"], q["numero_origem"]))

    # Numeracao sequencial so para exibicao (1, 2, 3...).
    for i, item in enumerate(selecionadas, start=1):
        item["numero_exibicao"] = i

    return selecionadas


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

    questoes = gerar_questoes_simulado(fase_ini, fase_fim, total)
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
            caminho_imagem = RAIZ / questao["imagem"]

            with Image.open(caminho_imagem) as arquivo:
                imagem = arquivo.copy()

            # Melhorar a nitidez de todas as figuras
            imagem = ImageOps.grayscale(imagem)
            imagem = ImageOps.autocontrast(imagem)
            imagem = ImageEnhance.Contrast(imagem).enhance(1.15)
            imagem = ImageEnhance.Sharpness(imagem).enhance(1.25)

            largura, altura = imagem.size
            proporcao = largura / altura

            if proporcao < 0.75:
                largura_maxima = 170
                altura_maxima = 220

            elif proporcao > 1.8:
                largura_maxima = 650
                altura_maxima = 320

            else:
                largura_maxima = 330
                altura_maxima = 300

            imagem.thumbnail(
                (largura_maxima, altura_maxima),
                Image.Resampling.LANCZOS
            )

           
            st.image(
                imagem,
                caption="Figura da questão",
                width="stretch" if imagem.width > 400 else "content"
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

                    # Tamanho máximo na tela, em pixels
                    largura_maxima = 450
                    altura_maxima = 180

                    # Reduz proporcionalmente, sem ampliar
                    fator = min(
                        1.0,
                        largura_maxima / largura,
                        altura_maxima / altura
                    )

                    largura_final = max(1, int(largura * fator))

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
    if st.session_state.get("modo_simulado"):
        return f"relatorio_{aluno}_simulado_{data}.pdf"
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
# Geracao do PDF do relatorio
# --------------------------------------------------------------------------- #
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


def _texto_pdf(texto: str) -> str:
    """Normaliza um texto para os limites das fontes core (latin-1) do PDF."""
    if not isinstance(texto, str):
        texto = str(texto)
    for origem, destino in _MAPA_PDF.items():
        texto = texto.replace(origem, destino)
    # Rede de seguranca: troca qualquer caractere fora do latin-1 por "?".
    return texto.encode("latin-1", errors="replace").decode("latin-1")


def gerar_pdf() -> bytes:
    """Monta o relatorio em PDF (fpdf2) e retorna os bytes.

    Compativel com fpdf2 1.x e 2.x: usa largura explicita nos `multi_cell`
    (evita o erro "Not enough horizontal space" da versao 2.8) e move o cursor
    para a linha seguinte de forma portavel.
    """
    from fpdf import FPDF

    aluno = _texto_pdf(st.session_state.aluno)
    modulo = st.session_state.modulo
    respondidas = st.session_state.respondidas
    acertos = st.session_state.acertos
    erros = st.session_state.erros
    porcentagem = (acertos / respondidas * 100) if respondidas else 0.0

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Detalhes de compatibilidade entre versoes do fpdf2.
    margem_esq = pdf.l_margin

    def linha(txt: str, altura: float = 7, negrito: bool = False) -> None:
        """Escreve uma linha simples ocupando toda a largura util."""
        pdf.set_font("Helvetica", "B" if negrito else "", 11)
        pdf.set_x(margem_esq)
        largura = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.multi_cell(largura, altura, _texto_pdf(txt))

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
        pdf.multi_cell(largura, altura, _texto_pdf(txt))
        if cor is not None:
            pdf.set_text_color(0, 0, 0)

    # Cabecalho
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_x(margem_esq)
    pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 10,
                   "Quiz MSA - Relatorio de Desempenho")
    linha(f"Aluno: {aluno}")
    if st.session_state.get("modo_simulado"):
        linha(f"Simulado: {st.session_state.get('fases_simulado', '')}")
    else:
        linha(f"Modulo: {modulo}")
    linha(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    pdf.ln(2)

    # Desempenho (nome do aluno ja consta no cabecalho).
    linha(f"Desempenho: {porcentagem:.1f}% de acertos", altura=8, negrito=True)
    linha(f"Acertos: {acertos} de {respondidas} respondidas")

    # Evidencia de monitoramento (somente simulado).
    if st.session_state.get("modo_simulado"):
        saidas = int(st.session_state.get("saidas_tela", 0) or 0)
        if saidas > 0:
            paragrafo(
                f"Monitoramento: o aluno saiu da tela {saidas} vez(es).",
                cor=(180, 0, 0),
            )
        else:
            paragrafo("Monitoramento: o aluno permaneceu na tela.")

    pdf.ln(3)

    # Revisao das questoes incorretas (sem listar as certas).
    if erros and st.session_state.registros_erro:
        linha("Revisao das questoes incorretas", altura=8, negrito=True)

        for registro in st.session_state.registros_erro:
            pdf.ln(1)
            paragrafo(f"Questao {registro['numero']}", negrito=True)
            paragrafo(f"Enunciado: {registro['enunciado']}")

           
            img_rel = registro.get("imagem")
            if img_rel and (RAIZ / img_rel).exists():
                try:
                    caminho = RAIZ / img_rel

                    with Image.open(caminho) as arquivo:
                        largura, altura = arquivo.size

                    # Limites máximos no PDF, em milímetros
                    largura_maxima = 70
                    altura_maxima = 40

                    # Preserva a proporção da imagem
                    fator = min(
                        largura_maxima / largura,
                        altura_maxima / altura
                    )

                    largura_pdf = largura * fator
                    altura_pdf = altura * fator

                    pdf.ln(1)
                    pdf.set_x(margem_esq)

                    pdf.image(
                        str(caminho),
                        w=largura_pdf,
                        h=altura_pdf
                    )

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
