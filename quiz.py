import streamlit as st
import pandas as pd
from fpdf import FPDF
import unicodedata

# --- 1. CONFIGURAÇÕES E DADOS ---
st.set_page_config(page_title="Quiz MSA", page_icon="🎵")

@st.cache_data
def carregar_dados():
    try:
        # Lê o CSV forçando a coluna Módulo como texto para evitar problemas de tipagem
        return pd.read_csv("arquivo1.csv", dtype={'Modulo': str})
    except Exception:
        st.error("Erro: O arquivo 'arquivo1.csv' não foi encontrado ou está corrompido.")
        st.stop()

df = carregar_dados()

# --- 2. GERENCIADOR DE MEMÓRIA (SESSION STATE) ---
def inicializar_memoria():
    if 'tela' not in st.session_state: st.session_state.tela = "login" # Telas: login, menu, quiz, pausa, fim
    if 'nome_aluno' not in st.session_state: st.session_state.nome_aluno = ""
    if 'modulo_atual' not in st.session_state: st.session_state.modulo_atual = None
    if 'indice' not in st.session_state: st.session_state.indice = 0
    if 'respondido' not in st.session_state: st.session_state.respondido = False
    
    # Memória visual do feedback (para não sumir se a tela piscar)
    if 'feedback_tipo' not in st.session_state: st.session_state.feedback_tipo = None
    if 'feedback_msg' not in st.session_state: st.session_state.feedback_msg = None
    if 'feedback_exp' not in st.session_state: st.session_state.feedback_exp = None
    
    # Estatísticas
    if 'total_mod' not in st.session_state: st.session_state.total_mod = {}
    if 'acertos_mod' not in st.session_state: st.session_state.acertos_mod = {}
    if 'erros' not in st.session_state: st.session_state.erros = []

inicializar_memoria()

# --- 3. FUNÇÕES AUXILIARES ---
def limpar_texto(texto):
    """Remove acentos para evitar que o gerador de PDF quebre com caracteres especiais."""
    texto = str(texto)
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')

def gerar_pdf_boletim():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Boletim de Desempenho - Quiz MSA", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, limpar_texto(f"Aluno(a): {st.session_state.nome_aluno}"), ln=True)
    
    # Cálculos Gerais
    total_acertos = sum(st.session_state.acertos_mod.values())
    total_resp = sum(st.session_state.total_mod.values())
    pct_geral = (total_acertos / total_resp * 100) if total_resp > 0 else 0
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, limpar_texto(f"Rendimento Geral: {pct_geral:.1f}% ({total_acertos} acertos de {total_resp} questoes)"), ln=True)
    pdf.ln(5)
    
    # Rendimento por Módulo (Garante ordem crescente na exibição do boletim também)
    pdf.cell(0, 10, "Rendimento por Modulo:", ln=True)
    pdf.set_font("Arial", size=11)
    # Ordena as chaves do dicionário numericamente para o PDF
    modulos_ordenados = sorted(st.session_state.total_mod.keys(), key=int)
    for mod in modulos_ordenados:
        total = st.session_state.total_mod[mod]
        acertos = st.session_state.acertos_mod.get(mod, 0)
        pct = (acertos / total * 100) if total > 0 else 0
        pdf.cell(0, 8, limpar_texto(f"  - Modulo {mod}: {pct:.1f}% ({acertos}/{total})"), ln=True)
        
    pdf.ln(5)
    
    # Relatório de Erros Atualizado e Estilizado
    if st.session_state.erros:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Questoes que precisam de revisao:", ln=True)
        pdf.set_font("Arial", size=10)
        for erro in st.session_state.erros:
            pdf.multi_cell(0, 6, limpar_texto(f"Modulo {erro['modulo']} | Pergunta: {erro['pergunta']}"))
            pdf.multi_cell(0, 6, limpar_texto(f"   -> Sua resposta: {erro['sua_resposta']}"))
            pdf.multi_cell(0, 6, limpar_texto(f"   -> Resposta correta: {erro['resposta_correta']}"))
            pdf.cell(0, 4, "-"*60, ln=True)
    else:
        pdf.set_font("Arial", 'I', 12)
        pdf.cell(0, 10, "Parabens! Nenhum erro registrado.", ln=True)
        
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- 4. FLUXO DE TELAS ---
st.title("Quiz MSA")

# TELA 1: LOGIN
if st.session_state.tela == "login":
    st.subheader("Bem-vindo(a) ao seu treinamento musical!")
    nome = st.text_input("Por favor, digite o seu nome para começar:")
    if st.button("Entrar no Quiz"):
        if nome.strip():
            st.session_state.nome_aluno = nome.strip()
            st.session_state.tela = "menu"
            st.rerun()
        else:
            st.warning("O nome não pode ficar em branco.")

# TELA 2: MENU DE MÓDULOS
elif st.session_state.tela == "menu":
    st.write(f"Olá, **{st.session_state.nome_aluno}**! De onde vamos partir hoje?")
    
    # Escolha do Módulo: Ordena numericamente os módulos extraídos da base de dados
    modulos_disponiveis = sorted(df['Modulo'].unique(), key=int)
    mod_escolhido = st.selectbox("Escolha o Módulo:", modulos_disponiveis)
    
    # Escudo: Verifica se o módulo possui perguntas
    df_preview = df[df['Modulo'] == mod_escolhido]
    total_perguntas_mod = len(df_preview)
    
    if total_perguntas_mod > 0:
        # Escolha da Pergunta Inicial
        pergunta_escolhida = st.number_input(
            f"Escolha a pergunta inicial (1 a {total_perguntas_mod}):", 
            min_value=1, 
            max_value=total_perguntas_mod, 
            value=1
        )
        
        st.write("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ Iniciar Módulo"):
                st.session_state.modulo_atual = mod_escolhido
                st.session_state.indice = pergunta_escolhida - 1 
                st.session_state.respondido = False
                
                # Zera memórias e erros APENAS deste módulo específico para recomeçar limpo
                mod_str = str(mod_escolhido)
                st.session_state.total_mod[mod_str] = 0
                st.session_state.acertos_mod[mod_str] = 0
                st.session_state.erros = [e for e in st.session_state.erros if e['modulo'] != mod_str]
                
                st.session_state.tela = "quiz"
                st.rerun()
                
        with col2:
            if sum(st.session_state.total_mod.values()) > 0:
                if st.button("⏹️ Finalizar e Gerar Boletim"):
                    st.session_state.tela = "fim"
                    st.rerun()
    else:
        st.warning("⚠️ Este módulo ainda não possui perguntas na base de dados.")

# TELA 3: QUIZ (RESPONDENDO)
elif st.session_state.tela == "quiz":
    col_esq, col_dir = st.columns([3, 1])
    with col_dir:
        if st.button("⏸️ Parar (Pausa)"):
            st.session_state.tela = "pausa"
            st.rerun()
            
    df_modulo = df[df['Modulo'] == st.session_state.modulo_atual].reset_index(drop=True)
    total_perguntas = len(df_modulo)
    
    if st.session_state.indice < total_perguntas:
        linha = df_modulo.iloc[st.session_state.indice]
        
        st.subheader(f"Módulo {st.session_state.modulo_atual} - Pergunta {st.session_state.indice + 1} de {total_perguntas}")
        st.write(linha['Pergunta'])
        
        opcoes = { "A": linha['Alternativa_A'], "B": linha['Alternativa_B'], "C": linha['Alternativa_C'], "D": linha['Alternativa_D'] }
        
        # O disabled=True bloqueia as alternativas depois de responder, evitando bugs visuais
        escolha = st.radio("Sua resposta:", list(opcoes.keys()), format_func=lambda x: f"{x}) {opcoes[x]}", index=None, disabled=st.session_state.respondido)
        
        # AÇÃO DE CONFIRMAR
        if not st.session_state.respondido:
            if st.button("Confirmar Resposta"):
                if escolha is None:
                    st.warning("⚠️️ Selecione uma alternativa antes de confirmar!")
                else:
                    st.session_state.respondido = True
                    mod_str = str(st.session_state.modulo_atual)
                    st.session_state.total_mod[mod_str] += 1
                    
                    if escolha == linha['Resposta_Correta']:
                        st.session_state.feedback_tipo = "sucesso"
                        st.session_state.feedback_msg = "✨ Resposta Correta!"
                        st.session_state.acertos_mod[mod_str] += 1
                    else:
                        st.session_state.feedback_tipo = "erro"
                        st.session_state.feedback_msg = f"❌ Incorreto. A resposta certa era: {linha['Resposta_Correta']}"
                        
                        st.session_state.erros.append({
                            "modulo": mod_str,
                            "pergunta": str(linha['Pergunta']),
                            "sua_resposta": f"{escolha}) {opcoes[escolha]}",
                            "resposta_correta": f"{linha['Resposta_Correta']}) {opcoes[linha['Resposta_Correta']]}"
                        })
                    
                    if pd.notna(linha['Explicacao']) and str(linha['Explicacao']).strip() != "":
                        st.session_state.feedback_exp = f"💡 Explicação: {linha['Explicacao']}"
                    else:
                        st.session_state.feedback_exp = None
                        
                    st.rerun() # Recarrega a tela para cravar o bloqueio das alternativas e mostrar o feedback
                    
        # EXIBIÇÃO DO FEEDBACK SALVO E BOTÃO PRÓXIMA
        if st.session_state.respondido:
            if st.session_state.feedback_tipo == "sucesso":
                st.success(st.session_state.feedback_msg)
            elif st.session_state.feedback_tipo == "erro":
                st.error(st.session_state.feedback_msg)
                
            if st.session_state.feedback_exp:
                st.info(st.session_state.feedback_exp)

            if st.button("Próxima Pergunta"):
                st.session_state.indice += 1
                st.session_state.respondido = False
                st.session_state.feedback_tipo = None
                st.session_state.feedback_msg = None
                st.session_state.feedback_exp = None
                st.rerun()
    else:
        st.success(f"Você concluiu todas as perguntas a partir da escolha inicial no Módulo {st.session_state.modulo_atual}!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Voltar ao Menu de Módulos"):
                st.session_state.tela = "menu"
                st.rerun()
        with col2:
            if st.button("⏹️ Finalizar Programa e Gerar PDF"):
                st.session_state.tela = "fim"
                st.rerun()

# TELA 4: PAUSADO
elif st.session_state.tela == "pausa":
    st.warning("⏱️ Programa Pausado.")
    st.write("O que você deseja fazer agora?")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Voltar a resolver"):
            st.session_state.tela = "quiz"
            st.rerun()
    with col2:
        if st.button("⏹ Gerar relatório"):
            st.session_state.tela = "fim"
            st.rerun()

# TELA 5: FINALIZADO / RELATÓRIO
elif st.session_state.tela == "fim":
    st.header("Resumo do seu Treinamento 🎯")
    
    total_resp = sum(st.session_state.total_mod.values())
    if total_resp == 0:
        st.info("Você não respondeu a nenhuma pergunta.")
        if st.button("Voltar ao Menu"):
            st.session_state.tela = "menu"
            st.rerun()
    else:
        total_acertos = sum(st.session_state.acertos_mod.values())
        pct_geral = (total_acertos / total_resp) * 100
        
        st.subheader(f"Rendimento Geral: {pct_geral:.1f}%")
        st.write(f"Você acertou **{total_acertos}** de **{total_resp}** questões respondidas.")
        
        pdf_bytes = gerar_pdf_boletim()
        
        # Limpa o nome do aluno apenas para o título do arquivo baixado (evita bugs no navegador)
        nome_arquivo_seguro = limpar_texto(st.session_state.nome_aluno).replace(' ', '_')
        
        st.download_button(
            label="📄 Baixar Boletim de Desempenho (PDF)",
            data=pdf_bytes,
            file_name=f"Boletim_{nome_arquivo_seguro}.pdf",
            mime="application/pdf"
        )
        
        st.write("---")
        if st.button("🔄 Reiniciar o Aplicativo (Zerar tudo)"):
            st.session_state.clear()
            st.rerun()