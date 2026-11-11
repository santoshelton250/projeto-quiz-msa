"""Testes da geracao de PDF (funcoes puras)."""

from __future__ import annotations

from datetime import datetime

from app.services.pdf import gerar_pdf, nome_arquivo_pdf, texto_pdf


# --------------------------------------------------------------------------- #
# texto_pdf
# --------------------------------------------------------------------------- #
def test_texto_pdf_normaliza_tipograficos():
    assert texto_pdf("a\u2013b") == "a-b"          # en-dash
    assert texto_pdf("\u201caspas\u201d") == '"aspas"'
    assert texto_pdf("\u2026") == "..."


def test_texto_pdf_troca_caractere_fora_latin1():
    # Emoji nao existe em latin-1 -> vira "?"
    assert texto_pdf("ok 😀") == "ok ?"


def test_texto_pdf_aceita_nao_string():
    assert texto_pdf(123) == "123"


# --------------------------------------------------------------------------- #
# nome_arquivo_pdf
# --------------------------------------------------------------------------- #
def test_nome_arquivo_quiz_normal():
    nome = nome_arquivo_pdf(
        "João da Silva", 14, False, quando=datetime(2026, 1, 2, 3, 4)
    )
    # Espacos e caracteres nao alfanumericos viram "_"; letras acentuadas
    # (ex.: "ã") sao mantidas por isalnum() - comportamento original.
    assert nome.startswith("relatorio_João_da_Silva_modulo14_")
    assert nome.endswith(".pdf")


def test_nome_arquivo_simulado():
    nome = nome_arquivo_pdf(
        "Maria", 1, True, quando=datetime(2026, 1, 2, 3, 4)
    )
    assert nome.startswith("relatorio_Maria_simulado_")
    assert nome.endswith(".pdf")


def test_nome_arquivo_aluno_vazio_usa_fallback():
    nome = nome_arquivo_pdf("", 3, False, quando=datetime(2026, 1, 2, 3, 4))
    assert "aluno" in nome


# --------------------------------------------------------------------------- #
# gerar_pdf (ponta a ponta, sem Streamlit)
# --------------------------------------------------------------------------- #
def _dados_base(**overrides):
    d = {
        "aluno": "Aluno Teste",
        "modulo": 14,
        "respondidas": 2,
        "acertos": 1,
        "erros": 1,
        "modo_simulado": False,
        "fases_simulado": "",
        "saidas_tela": 0,
        "registros_erro": [
            {
                "numero": 3,
                "enunciado": "Pergunta exemplo",
                "imagem": None,
                "resposta_aluno": "B",
                "resposta_correta": "A",
            }
        ],
    }
    d.update(overrides)
    return d


def test_gerar_pdf_retorna_bytes_validos():
    pdf = gerar_pdf(_dados_base())
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"       # assinatura de PDF
    assert len(pdf) > 500


def test_gerar_pdf_sem_erros():
    pdf = gerar_pdf(_dados_base(respondidas=5, acertos=5, erros=0,
                                registros_erro=[]))
    assert pdf[:4] == b"%PDF"


def test_gerar_pdf_simulado_com_saidas():
    pdf = gerar_pdf(_dados_base(modo_simulado=True, fases_simulado="Fases 1 a 16",
                                saidas_tela=2))
    assert pdf[:4] == b"%PDF"


def test_gerar_pdf_respondidas_zero_nao_divide_por_zero():
    pdf = gerar_pdf(_dados_base(respondidas=0, acertos=0, erros=0,
                                registros_erro=[]))
    assert pdf[:4] == b"%PDF"
