# 🎵 Quiz MSA

Aplicação de quiz interativa (Streamlit) para estudo de música sacra, com questões
de múltipla escolha, figuras das partituras e relatório de desempenho em PDF.

## Funcionalidades

- Tela inicial com **nome do aluno**, **módulo (fase)** e **questão inicial**
  (digitáveis).
- Cada questão mostra o enunciado e, quando houver, a **figura** da partitura.
- Feedback apenas de **correto/incorreto** durante o quiz (a resposta certa não é
  revelada na hora).
- Ao terminar, é possível **baixar o relatório em PDF** contendo: nome do aluno,
  porcentagem de acertos e as questões erradas (com a resposta do aluno e a
  resposta correta).
- Layout responsivo (funciona em PC e celular).

## Estrutura do projeto

```
├── quiz.py                  # aplicação Streamlit (consome dados/questoes.json)
├── extrator.py              # gera dados/questoes.json + figuras (offline)
├── requirements.txt
├── dados/
│   └── questoes.json        # banco de questões (fonte da verdade)
└── imagens_quiz/            # figuras das questões
```

> O app **não** lê os PDFs das apostilas em tempo de execução — usa o
> `questoes.json` já processado.

## Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run quiz.py
```

## Regenerar os dados (opcional)

Caso tenha os PDFs das apostilas e queira reprocessar:

```bash
python extrator.py
```

## Tecnologias

- [Streamlit](https://streamlit.io/)
- [PyMuPDF](https://pymupdf.readthedocs.io/) (extração das figuras)
- [pandas](https://pandas.pydata.org/)
- [fpdf2](https://py-pdf.github.io/fpdf2/) (relatório em PDF)
