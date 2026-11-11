"""Geracao de questoes de simulado (logica pura, sem dependencia de Streamlit).

Este modulo concentra as regras de distribuicao e sorteio das questoes do
simulado. Ele NAO importa `streamlit` de proposito: assim pode ser testado
isoladamente (ver tests/test_simulados.py).

Interface principal:
    gerar_questoes_simulado(fases, fase_ini, fase_fim, total) -> list[dict]

`fases` e um mapeamento {numero_da_fase: [questoes...]}, o mesmo formato
usado pela aplicacao (dicionario FASES).
"""

from __future__ import annotations

import random

# Ate esse total usa distribuicao igualitaria; acima, proporcional.
LIMIAR_IGUALITARIO = 30


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


def _distribuir_proporcional(
    total: int, fases: list[int], tamanhos: dict[int, int]
) -> dict[int, int]:
    """Distribui proporcionalmente ao tamanho (n de questoes) de cada fase.

    Garante ao menos 1 questao por fase, desde que o total permita. O metodo
    do "maior resto" ajusta o arredondamento para bater exatamente o total.
    """
    k = len(fases)
    if total <= 0 or k == 0:
        return {f: 0 for f in fases}

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
    fases_disponiveis: dict[int, list[dict]],
    fase_ini: int,
    fase_fim: int,
    total: int,
) -> list[dict]:
    """Sorteia e monta a lista de questoes do simulado.

    - Seleciona aleatoriamente as questoes dentro de cada fase.
    - Ordena por fase crescente e, dentro da fase, por numero crescente.
    - Cada questao recebe 'numero_exibicao' (1, 2, 3...) sem alterar o banco.

    `fases_disponiveis`: {numero_da_fase: [questoes...]}.
    """
    fases = sorted(f for f in fases_disponiveis if fase_ini <= f <= fase_fim)
    if not fases:
        return []

    if total <= LIMIAR_IGUALITARIO:
        dist = _distribuir_igualitario(total, fases)
    else:
        tamanhos = {f: len(fases_disponiveis.get(f, [])) for f in fases}
        dist = _distribuir_proporcional(total, fases, tamanhos)

    selecionadas: list[dict] = []
    for f in fases:
        disponiveis = fases_disponiveis.get(f, [])
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
