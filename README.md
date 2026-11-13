# 📊 Analisador de Dados com IA

Envie uma planilha (Excel ou CSV) e receba automaticamente:

- **Visão geral**: linhas, colunas, vazios, duplicados, tipos de cada coluna e estatísticas.
- **Achados automáticos** (sem IA): outliers, correlações fortes, colunas com muitos vazios, categorias dominantes, período das datas.
- **Gráficos automáticos**: evolução no tempo, rankings por categoria, distribuições e mapa de correlação, além de um construtor de gráficos livre.
- **Relatório da IA**: resumo, descobertas, qualidade dos dados, recomendações e perguntas sugeridas, com download em `.md`.
- **Exportação em PDF**: resumo executivo em A4 (indicadores, gráficos e achados), com o relatório da IA incluído quando ele tiver sido gerado.
- **Pergunte aos dados (texto → SQL)**: perguntas em português ("qual o faturamento por mês?"). A IA escreve a consulta **SQL**, que o **DuckDB** executa sobre a base. O resultado sai em tabela e gráfico automático, com a explicação e a consulta SQL visível.

A limpeza é automática: remove linhas e colunas vazias e converte `R$ 1.234,56` em número e `31/12/2025` em data.

## Como usar

1. Dê dois cliques em **`iniciar.bat`**. Na primeira vez ele instala tudo sozinho.
2. O navegador abre em `http://localhost:8501`.
3. Na barra lateral, escolha a IA gratuita e cole a chave.
4. Envie sua planilha, ou clique em "Testar com uma base de exemplo".

Pelo terminal: `.venv\Scripts\python -m streamlit run app.py`

## IAs gratuitas suportadas

| Provedor | Custo | Onde pegar a chave | Observação |
|---|---|---|---|
| **Groq** (padrão) | Grátis | https://console.groq.com/keys | Muito rápido, recomendado |
| **Google Gemini** | Grátis | https://aistudio.google.com/apikey | Limite diário generoso |
| **Ollama** | Grátis | Sem chave. Instale em https://ollama.com | Roda 100% offline no seu PC |

Para não digitar a chave toda vez, copie `.env.example` para `.env` e preencha.

Se um provedor descontinuar o modelo padrão, troque o nome do modelo na barra lateral.

## Privacidade

As consultas SQL rodam no DuckDB **somente leitura e sem acesso a arquivos, rede ou extensões**. Mesmo que a IA gere algo malicioso, o banco recusa.

A IA **nunca recebe a planilha inteira**. Ela recebe só um resumo estatístico, os nomes das colunas e 5 linhas de amostra. Os cálculos rodam localmente. Para dados sigilosos, use o **Ollama**, porque com ele nada sai do seu computador.

## Publicar online (grátis) no Streamlit Community Cloud

1. Envie o projeto para um repositório **público** no GitHub. O `.gitignore` já impede o envio do `.env` com a sua chave.
2. Acesse https://share.streamlit.io, entre com o GitHub e clique em **Create app**.
3. Escolha o repositório, a branch `main` e o arquivo `app.py`. Em *Advanced settings*, selecione Python 3.11.
4. Em **Secrets**, cole o conteúdo de `.streamlit/secrets.toml.example` preenchido com a sua chave e os seus links.
5. Clique em **Deploy**. O link fica no formato `https://seu-app.streamlit.app`.

Para abrir direto na demonstração (bom para QR code no currículo), use `https://seu-app.streamlit.app/?demo=1`.

**Proteções do modo público:** a sua chave fica só no servidor (nunca vai para o navegador), cada visitante tem um limite de usos da IA (`LIMITE_IA_SESSAO`), os uploads vão até 25 MB e o SQL roda sem acesso a nada além da base enviada.

## Estrutura

```
app.py            Interface (Streamlit)
analise.py        Leitura, limpeza, estatísticas, achados e gráficos
ia.py             Conexão com as IAs, relatório e perguntas -> código -> resposta
pdf_relatorio.py  Exportação do resumo executivo em PDF
gerar_exemplo.py  Cria exemplo_vendas.xlsx (base fictícia para teste)
iniciar.bat       Atalho para instalar e abrir
```
