"""Teste de fumaca da aplicacao via AppTest (sem servidor).

- Sobe o app e confere que a tela inicial renderiza sem excecao.
- Navega pelo fluxo do quiz normal (Fase 14, Q15 e Q35 ilustradas).
- Confere o relatorio.

Nao substitui testes unitarios: e uma checagem de "abre e nao explode".
"""

from streamlit.testing.v1 import AppTest

import json
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path e resolva o quiz.py
# independentemente do diretorio de onde o teste e executado.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
QUIZ = str(RAIZ / "quiz.py")


def _sem_excecao(at, etapa):
    print(f"[{etapa}] excecoes: {len(at.exception)}")
    for e in at.exception:
        print("   ERRO:", e.value)
    assert not at.exception, f"Excecao em: {etapa}"


# 1) Tela inicial
at = AppTest.from_file(QUIZ, default_timeout=30)
at.run()
_sem_excecao(at, "tela inicial")

# 2) Injeta estado de quiz como se o aluno tivesse clicado "Iniciar"
d = json.loads((RAIZ / "dados" / "questoes.json").read_text(encoding="utf-8"))
f14 = next(f for f in d["fases"] if f["fase"] == 14)["questoes"]
sel = [q for q in f14 if q["numero"] >= 15]

at.session_state["tela"] = "quiz"
at.session_state["aluno"] = "Aluno Teste"
at.session_state["modulo"] = 14
at.session_state["questoes"] = sel
at.session_state["indice"] = 0
at.session_state["ja_respondida"] = False
at.session_state["ultimo_acerto"] = None
at.session_state["modo_simulado"] = False
at.run()
_sem_excecao(at, "quiz Q15 (ilustrada)")

# 3) Avanca para a Q35 (ilustrada)
idx_q35 = next(i for i, q in enumerate(sel) if q["numero"] == 35)
at.session_state["indice"] = idx_q35
at.session_state["ja_respondida"] = False
at.run()
_sem_excecao(at, "quiz Q35 (ilustrada)")

# 4) Relatorio
at.session_state["tela"] = "relatorio"
at.session_state["respondidas"] = 1
at.session_state["acertos"] = 1
at.session_state["erros"] = 0
at.session_state["registros_erro"] = []
at.run()
_sem_excecao(at, "relatorio")

print("OK - fluxo do quiz/relatorio renderizou sem excecao")
