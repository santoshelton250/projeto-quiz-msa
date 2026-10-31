# Quiz MSA

Aplicacao de quiz interativa (Streamlit) para estudo de musica sacra, com questoes
de multipla escolha, figuras das partituras e relatorio de desempenho em PDF.

## Funcionalidades

### Quiz normal (aluno)
- Tela inicial com **nome do aluno**, **fase** e **questao inicial** (digitaveis).
- Cada questao mostra o enunciado e, quando houver, a **figura** da partitura.
- Feedback apenas de **correto/incorreto** durante o quiz (a resposta certa nao e
  revelada na hora).
- Ao terminar, e possivel **baixar o relatorio em PDF** contendo: nome do aluno,
  porcentagem de acertos e as questoes erradas (com a resposta do aluno e a
  resposta correta).
- Layout responsivo (funciona em PC e celular).

### Simulado (instrutor)
- Area **"Gerar simulado"** protegida por **senha do instrutor** (o aluno nao tem
  a senha e nao consegue gerar).
- O instrutor escolhe **fase inicial**, **fase final** e **numero de questoes**.
- As questoes sao **sorteadas** do banco e cada simulado sai diferente.
- Distribuicao das questoes:
  - Ate **30 questoes**: distribuicao **igualitaria** entre as fases.
  - Acima de **30**: distribuicao **proporcional** ao tamanho de cada fase.
  - Nenhuma fase fica sem questao, salvo se o pedido for menor que o numero de fases.
- As questoes aparecem **ordenadas por fase e por numero** (sem embaralhar), com
  numeracao sequencial (1, 2, 3...) apenas para exibicao.
- Durante o simulado o app **registra** quando o aluno sai da tela (troca de aba
  ou janela). O numero de saidas aparece no relatorio e no PDF.
- A senha volta a ser exigida assim que o simulado e gerado, ao terminar, ao sair
  do simulado ou ao recarregar a pagina.

## Estrutura do projeto

```
quiz.py                  # aplicacao Streamlit (consome dados/questoes.json)
extrator.py              # gera dados/questoes.json + figuras (offline)
requirements.txt
dados/
    questoes.json        # banco de questoes (fonte da verdade)
imagens_quiz/            # figuras das questoes
.streamlit/
    secrets.toml         # senha do instrutor (NAO versionado)
DEPLOY.md                # instrucoes de deploy e configuracao da senha
```

> O app **nao** le os PDFs das apostilas em tempo de execucao - usa o
> `questoes.json` ja processado.

## Como rodar localmente

```bash
pip install -r requirements.txt
python -m streamlit run quiz.py
```

## Senha do instrutor

A senha fica em `.streamlit/secrets.toml` (nao vai para o GitHub):

```toml
senha_instrutor = "MSA_394"
```

Para trocar a senha, basta editar esse arquivo e reiniciar o app. Detalhes de
deploy e configuracao online no **[DEPLOY.md](DEPLOY.md)**.

## Regenerar os dados (opcional)

Caso tenha os PDFs das apostilas e queira reprocessar:

```bash
python extrator.py
```

## Tecnologias

- [Streamlit](https://streamlit.io/)
- [PyMuPDF](https://pymupdf.readthedocs.io/) (extracao das figuras, no extrator)
- [pandas](https://pandas.pydata.org/) (no extrator)
- [fpdf2](https://py-pdf.github.io/fpdf2/) (relatorio em PDF)
