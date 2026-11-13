"""Integração com IAs gratuitas (Groq, Google Gemini ou Ollama local).

Os três provedores expõem uma API compatível com a da OpenAI, então um único
cliente atende a todos — muda só o endereço, a chave e o nome do modelo.
"""

from __future__ import annotations

import re

import duckdb
import pandas as pd
from openai import OpenAI

PROVEDORES = {
    "Groq (grátis, nuvem, rápido)": {
        "base_url": "https://api.groq.com/openai/v1",
        # Ordem de preferência; o primeiro disponível vira o padrão
        "preferidos": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"],
        "env": "GROQ_API_KEY",
        "link": "https://console.groq.com/keys",
    },
    "Google Gemini (grátis, nuvem)": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "preferidos": ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"],
        "env": "GEMINI_API_KEY",
        "link": "https://aistudio.google.com/apikey",
    },
    "Ollama (grátis, local, offline)": {
        "base_url": "http://localhost:11434/v1",
        "preferidos": ["llama3.2", "qwen2.5", "llama3.1"],
        "env": None,
        "link": "https://ollama.com/download",
    },
}

# Modelos que não servem para conversa (áudio, imagem, moderação, embeddings...)
_NAO_CHAT = re.compile(
    r"whisper|guard|safeguard|orpheus|tts|embed|imagen|veo|aqa|audio|image|live|vision-only|"
    r"allam|learnlm|gemma-3n|robotics|computer-use",
    re.IGNORECASE,
)


def listar_modelos(provedor: str, api_key: str | None) -> list[str]:
    """Consulta o provedor e retorna os modelos de chat disponíveis, preferidos primeiro."""
    cfg = PROVEDORES[provedor]
    cliente = OpenAI(base_url=cfg["base_url"], api_key=api_key or "ollama", timeout=15)
    ids = {m.id.removeprefix("models/") for m in cliente.models.list().data}
    ids = sorted(i for i in ids if not _NAO_CHAT.search(i))
    preferidos = [p for p in cfg["preferidos"] if p in ids]
    return preferidos + [i for i in ids if i not in preferidos]


class ClienteIA:
    def __init__(self, provedor: str, api_key: str | None, modelo: str):
        cfg = PROVEDORES[provedor]
        self.modelo = modelo
        self.cliente = OpenAI(base_url=cfg["base_url"], api_key=api_key or "ollama", timeout=120)

    def conversar(self, mensagens: list[dict], temperatura: float = 0.2) -> str:
        resposta = self.cliente.chat.completions.create(
            model=self.modelo, messages=mensagens, temperature=temperatura
        )
        return resposta.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Relatório automático
# ---------------------------------------------------------------------------

_SISTEMA_ANALISTA = (
    "Você é um analista de dados sênior. Responda sempre em português do Brasil, "
    "de forma clara e objetiva, para um público de negócios. Baseie-se apenas nos dados "
    "fornecidos; quando algo não puder ser concluído a partir deles, diga isso."
)


def gerar_relatorio(cliente: ClienteIA, perfil: str, contexto: str = "") -> str:
    pedido = f"""Analise o perfil da base de dados abaixo e escreva um relatório em Markdown com as seções:

## Resumo da base
O que esses dados parecem representar e como estão estruturados.

## Principais descobertas
5 a 8 descobertas concretas, citando números do perfil.

## Qualidade dos dados
Problemas encontrados (vazios, duplicados, outliers, inconsistências) e como tratá-los.

## Recomendações
Ações práticas e próximas análises sugeridas.

## Perguntas para investigar
3 a 5 perguntas que valeria a pena fazer a esses dados.

{f"Contexto informado pelo usuário: {contexto}" if contexto else ""}

PERFIL DA BASE:
{perfil}"""
    return cliente.conversar(
        [{"role": "system", "content": _SISTEMA_ANALISTA}, {"role": "user", "content": pedido}],
        temperatura=0.3,
    )


# ---------------------------------------------------------------------------
# Perguntas em linguagem natural -> SQL (DuckDB) -> resultado
# ---------------------------------------------------------------------------
#
# A IA escreve uma consulta SQL, que é executada pelo DuckDB sobre uma cópia da
# base em memória. Só consultas de leitura (SELECT/WITH) são aceitas, e o DuckDB
# roda sem acesso a arquivos, rede ou extensões — seguro para uso público.

TABELA = "dados"

_SISTEMA_SQL = f"""Você é um analista de dados que escreve SQL para o DuckDB.

Regras:
- Existe uma única tabela chamada `{TABELA}`. Use apenas as colunas listadas no perfil.
- Coloque nomes de colunas entre aspas duplas, exatamente como estão (ex.: "Preço Unitário").
- Escreva UMA consulta SELECT (pode usar WITH). Nunca altere dados.
- Arredonde valores decimais com ROUND(..., 2) e dê nomes claros às colunas do resultado (em português).
- Para agrupar por mês use date_trunc('month', "coluna_data").
- Limite resultados longos com LIMIT 50.
- Responda APENAS com um bloco ```sql ... ```, sem explicações."""

_SQL_PROIBIDO = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|export|import|install|load|"
    r"pragma|set|call|checkpoint|vacuum|read_\w+|glob|httpfs|getenv)\b",
    re.IGNORECASE,
)


def extrair_sql(texto: str) -> str:
    bloco = re.search(r"```(?:sql)?\s*\n(.*?)```", texto, re.DOTALL | re.IGNORECASE)
    sql = (bloco.group(1) if bloco else texto).strip()
    return sql.rstrip(";").strip()


def _conexao_segura(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:", config={
        "enable_external_access": False,   # sem arquivos, rede ou extensões
        "autoinstall_known_extensions": False,
        "autoload_known_extensions": False,
        "lock_configuration": True,         # a consulta não pode reabilitar nada
    })
    con.register(TABELA, df)
    return con


def executar_sql(sql: str, df: pd.DataFrame, limite_linhas: int = 1000) -> dict:
    """Executa uma consulta de leitura sobre a base. Retorna {'resultado'} ou {'erro'}."""
    sem_comentarios = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.DOTALL).strip()
    if not re.match(r"^(select|with)\b", sem_comentarios, re.IGNORECASE):
        return {"erro": "Apenas consultas SELECT são permitidas."}
    if ";" in sem_comentarios:
        return {"erro": "Envie apenas uma consulta por vez."}
    proibido = _SQL_PROIBIDO.search(sem_comentarios)
    if proibido:
        return {"erro": f"Comando não permitido: '{proibido.group(0)}'."}
    try:
        con = _conexao_segura(df)
        try:
            resultado = con.execute(sem_comentarios).fetch_df().head(limite_linhas)
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001 - qualquer erro volta para a IA corrigir
        return {"erro": f"{type(e).__name__}: {e}".split("\n")[0][:500]}
    # Somas de inteiros voltam como float (38.0); mostra como inteiro quando for o caso
    for col in resultado.select_dtypes("float").columns:
        valores = resultado[col].dropna()
        if len(valores) and (valores == valores.round()).all() and valores.abs().max() < 2**53:
            resultado[col] = resultado[col].astype("Int64")
    return {"resultado": resultado}


def _resultado_em_texto(resultado: pd.DataFrame, limite: int = 3000) -> str:
    return resultado.head(50).to_string(index=False)[:limite]


def responder_pergunta(cliente: ClienteIA, df: pd.DataFrame, perfil: str, pergunta: str,
                       tentativas: int = 3) -> dict:
    """Gera SQL, executa, corrige se der erro e explica o resultado."""
    mensagens = [
        {"role": "system", "content": _SISTEMA_SQL},
        {"role": "user", "content": f"PERFIL DA TABELA `{TABELA}`:\n{perfil}\n\nPERGUNTA: {pergunta}"},
    ]
    execucao: dict = {}
    sql = ""
    for _ in range(tentativas):
        resposta = cliente.conversar(mensagens, temperatura=0.1)
        sql = extrair_sql(resposta)
        execucao = executar_sql(sql, df)
        if "erro" not in execucao:
            break
        mensagens += [
            {"role": "assistant", "content": resposta},
            {"role": "user", "content": f"A consulta falhou: {execucao['erro']}\n"
                                        "Corrija e responda só com o SQL."},
        ]

    if "erro" in execucao:
        return {"sql": sql, "erro": execucao["erro"]}

    resultado = execucao["resultado"]
    explicacao = cliente.conversar(
        [
            {"role": "system", "content": _SISTEMA_ANALISTA},
            {"role": "user", "content": (
                f"Pergunta do usuário: {pergunta}\n\nResultado da consulta SQL nos dados:\n"
                f"{_resultado_em_texto(resultado) if not resultado.empty else '(nenhuma linha)'}\n\n"
                "Responda à pergunta em 2 a 5 frases, interpretando o resultado para um gestor. "
                "Não invente números que não estejam no resultado."
            )},
        ],
        temperatura=0.3,
    )
    return {"sql": sql, "resultado": resultado, "explicacao": explicacao}
