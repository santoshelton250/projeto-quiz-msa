# Deploy - Quiz MSA

Guia para publicar o app e configurar a senha do instrutor.

---

## 1. Rodar localmente

```bash
pip install -r requirements.txt
python -m streamlit run quiz.py
```

> Se `streamlit` nao for reconhecido no terminal, use `python -m streamlit run quiz.py`.

O app abre em `http://localhost:8501`.

---

## 2. A senha do instrutor (IMPORTANTE)

A senha que libera a geracao de simulados **nao fica no codigo**. Ela e lida de
`.streamlit/secrets.toml` (arquivo que **nao vai para o GitHub**, pois esta no
`.gitignore`).

### Localmente

O arquivo `.streamlit/secrets.toml` deve conter:

```toml
senha_instrutor = "MSA_394"
```

### Como trocar a senha

1. Abra `.streamlit/secrets.toml`
2. Altere o valor de `senha_instrutor`
3. Salve e reinicie o app

Nao e necessario alterar nenhum codigo.

### Sem o arquivo de secrets

Se o `secrets.toml` nao existir (ou nao tiver a chave `senha_instrutor`), o app
**nao autoriza** a geracao de simulados (comportamento seguro por padrao). O quiz
normal continua funcionando.

---

## 3. Publicar no Streamlit Community Cloud (gratuito)

1. Acesse <https://share.streamlit.io> e entre com a conta do GitHub.
2. Clique em **New app**.
3. Preencha:
   - **Repository:** `santoshelton250/projeto-quiz-msa`
   - **Branch:** `main`
   - **Main file path:** `quiz.py`
4. **Antes de clicar em Deploy**, configure a senha:
   - Abra **Advanced settings** (ou **Settings > Secrets**).
   - Cole exatamente:

     ```toml
     senha_instrutor = "MSA_394"
     ```

   - Salve.
5. Clique em **Deploy**.

Em alguns minutos o app fica disponivel em um link publico, acessivel no
computador e no celular, sem instalar nada.

> **Atencao:** o Streamlit Cloud **nao le** o `.streamlit/secrets.toml` local.
> A senha precisa ser colada manualmente na tela de **Secrets** do painel.
> Sem isso, ninguem conseguira gerar simulados online (por seguranca).

### Trocar a senha no Streamlit Cloud

1. Abra o app no painel do Streamlit Cloud.
2. **Settings > Secrets**.
3. Altere o valor de `senha_instrutor`.
4. Salve (o app reinicia automaticamente).

---

## 4. Sobre o repositorio publico

O repositorio e publico: qualquer pessoa pode ver o codigo e o historico.
**A senha nao esta no repositorio** (fica apenas nos Secrets do Streamlit
Cloud e no `secrets.toml` local, que e ignorado pelo git).

Para conferir que o arquivo esta protegido:

```bash
git check-ignore .streamlit/secrets.toml
# deve imprimir: .streamlit/secrets.toml
```

---

## 5. Gerar simulado (para o instrutor)

1. Preencha o **Nome do aluno**.
2. Abra **Gerar simulado (instrutor)**.
3. Digite a senha e clique em **Liberar geracao**.
4. Informe **Fase inicial**, **Fase final** e **Numero de questoes**.
5. Clique em **Gerar simulado**.

Regras de distribuicao:

- Ate 30 questoes: distribuicao **igualitaria** entre as fases.
- Acima de 30: distribuicao **proporcional** ao tamanho de cada fase.
- Nenhuma fase fica sem questao (salvo se o pedido for menor que o numero de
  fases).
- As questoes sao sorteadas e depois ordenadas por fase e por numero.

A senha volta a ser exigida assim que o simulado e gerado, ao terminar, ao sair
do simulado ou ao recarregar a pagina.

---

## 6. Monitoramento de troca de tela

Durante o simulado, o app **registra** (nao bloqueia) quando o aluno sai da aba
ou da janela. O numero de saidas aparece:

- No aviso exibido ao aluno ao voltar para a tela.
- No relatorio de desempenho.
- No PDF do relatorio.

> Limitacao: o navegador nao permite **impedir** a troca de aba; apenas detectar.
> O registro serve como evidencia para o professor.

---

## 7. Estrutura do projeto

```
quiz.py                  # aplicacao Streamlit
extrator.py              # gera dados/questoes.json (offline)
requirements.txt         # dependencias do app
dados/questoes.json      # banco de questoes
imagens_quiz/            # figuras das questoes
.streamlit/secrets.toml  # senha do instrutor (NAO versionado)
```
