"""Testes da geracao de simulado.

Objetivo: travar as regras de negocio ANTES de qualquer refatoracao, para que
qualquer mudanca futura que quebre o comportamento seja detectada na hora.

Rodar com:
    pytest -q
"""

from __future__ import annotations

import random

import pytest

from app.services.simulados import (
    LIMIAR_IGUALITARIO,
    _distribuir_igualitario,
    _distribuir_proporcional,
    gerar_questoes_simulado,
)


def _fazer_fases(tamanhos: dict[int, int]) -> dict[int, list[dict]]:
    """Cria um banco sintetico {fase: [questoes]} com os tamanhos indicados."""
    fases: dict[int, list[dict]] = {}
    for fase, n in tamanhos.items():
        fases[fase] = [
            {
                "numero": i,
                "enunciado": f"Q{fase}-{i}",
                "alternativas": ["a", "b"],
                "correta": 0,
                "imagem": None,
            }
            for i in range(1, n + 1)
        ]
    return fases


# --------------------------------------------------------------------------- #
# _distribuir_igualitario
# --------------------------------------------------------------------------- #
def test_igualitario_soma_exata_e_minimo_um():
    fases = [1, 2, 3, 4, 5]
    dist = _distribuir_igualitario(17, fases)
    assert sum(dist.values()) == 17
    assert all(dist[f] >= 1 for f in fases)
    # Diferenca entre maior e menor deve ser no maximo 1.
    assert max(dist.values()) - min(dist.values()) <= 1


def test_igualitario_total_menor_que_fases_sorteia_quais():
    fases = [1, 2, 3, 4, 5]
    dist = _distribuir_igualitario(2, fases)
    assert sum(dist.values()) == 2
    assert sum(1 for v in dist.values() if v == 1) == 2
    assert all(v in (0, 1) for v in dist.values())


def test_igualitario_total_zero():
    dist = _distribuir_igualitario(0, [1, 2, 3])
    assert dist == {1: 0, 2: 0, 3: 0}


def test_igualitario_sem_fases():
    assert _distribuir_igualitario(10, []) == {}


# --------------------------------------------------------------------------- #
# _distribuir_proporcional
# --------------------------------------------------------------------------- #
def test_proporcional_soma_exata_e_minimo_um():
    fases = [1, 2, 3]
    tamanhos = {1: 10, 2: 50, 3: 40}
    dist = _distribuir_proporcional(60, fases, tamanhos)
    assert sum(dist.values()) == 60
    assert all(dist[f] >= 1 for f in fases)


def test_proporcional_respeita_limite_da_fase():
    # Pede um total grande: nenhuma fase pode receber mais do que possui.
    fases = [1, 2, 3]
    tamanhos = {1: 5, 2: 8, 3: 7}
    total = 20  # exatamente o disponivel
    dist = _distribuir_proporcional(total, fases, tamanhos)
    for f in fases:
        assert dist[f] <= tamanhos[f]
    assert sum(dist.values()) == total


def test_proporcional_fase_menor_recebe_menos():
    # A fase com mais questoes deve receber mais (em geral).
    random.seed(0)
    fases = [1, 2]
    tamanhos = {1: 10, 2: 90}
    dist = _distribuir_proporcional(50, fases, tamanhos)
    assert dist[2] > dist[1]


# --------------------------------------------------------------------------- #
# gerar_questoes_simulado (regras de ponta a ponta)
# --------------------------------------------------------------------------- #
def test_gerar_respeita_total_e_ordenacao():
    random.seed(42)
    fases = _fazer_fases({f: 20 for f in range(1, 6)})  # 5 fases x 20
    questoes = gerar_questoes_simulado(fases, 1, 5, 25)

    assert len(questoes) == 25
    # Ordenadas por (fase, numero).
    chaves = [(q["fase_origem"], q["numero_origem"]) for q in questoes]
    assert chaves == sorted(chaves)
    # Numeracao de exibicao sequencial 1..N.
    assert [q["numero_exibicao"] for q in questoes] == list(range(1, 26))


def test_gerar_nao_duplica_questoes():
    random.seed(7)
    fases = _fazer_fases({1: 10, 2: 10})
    questoes = gerar_questoes_simulado(fases, 1, 2, 15)
    identidades = [(q["fase_origem"], q["numero_origem"]) for q in questoes]
    assert len(identidades) == len(set(identidades))


def test_gerar_nao_altera_banco_original():
    random.seed(1)
    fases = _fazer_fases({1: 5})
    copia_antes = {k: [dict(q) for q in v] for k, v in fases.items()}
    gerar_questoes_simulado(fases, 1, 1, 3)
    # O banco original nao pode ganhar 'fase_origem'/'numero_exibicao'.
    assert fases == copia_antes


def test_gerar_usa_igualitario_ate_o_limiar_e_proporcional_acima():
    # Ate o limiar: todas as fases devem ser contempladas com quase o mesmo.
    random.seed(3)
    fases = _fazer_fases({f: 100 for f in range(1, 7)})  # 6 fases iguais
    q_ig = gerar_questoes_simulado(fases, 1, 6, LIMIAR_IGUALITARIO)
    por_fase = {f: 0 for f in range(1, 7)}
    for q in q_ig:
        por_fase[q["fase_origem"]] += 1
    assert max(por_fase.values()) - min(por_fase.values()) <= 1


def test_gerar_intervalo_sem_fases_retorna_vazio():
    fases = _fazer_fases({1: 5})
    assert gerar_questoes_simulado(fases, 10, 20, 5) == []


def test_gerar_pedido_maior_que_disponivel_nao_explode():
    # Nao deve lancar excecao; devolve o que for possivel sem duplicar.
    random.seed(5)
    fases = _fazer_fases({1: 3, 2: 2})
    questoes = gerar_questoes_simulado(fases, 1, 2, 100)
    assert len(questoes) <= 5
    identidades = [(q["fase_origem"], q["numero_origem"]) for q in questoes]
    assert len(identidades) == len(set(identidades))


@pytest.mark.parametrize("total", [1, 2, 5, 30, 31, 60])
def test_gerar_nunca_excede_total_nem_duplica(total: int):
    random.seed(total)
    fases = _fazer_fases({f: 30 for f in range(1, 5)})
    questoes = gerar_questoes_simulado(fases, 1, 4, total)
    assert len(questoes) == total
    identidades = [(q["fase_origem"], q["numero_origem"]) for q in questoes]
    assert len(identidades) == len(set(identidades))
