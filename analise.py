"""Leitura, limpeza, perfil estatístico e gráficos automáticos de uma base de dados."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Leitura e preparação
# ---------------------------------------------------------------------------


def listar_abas(arquivo) -> list[str]:
    """Retorna os nomes das abas de um arquivo Excel (vazio para CSV)."""
    nome = getattr(arquivo, "name", str(arquivo)).lower()
    if nome.endswith(".csv"):
        return []
    arquivo.seek(0) if hasattr(arquivo, "seek") else None
    return pd.ExcelFile(arquivo).sheet_names


def carregar_arquivo(arquivo, aba: str | None = None) -> pd.DataFrame:
    """Lê .xlsx, .xls ou .csv (detecta separador ; ou ,)."""
    nome = getattr(arquivo, "name", str(arquivo)).lower()
    if hasattr(arquivo, "seek"):
        arquivo.seek(0)
    if nome.endswith(".csv"):
        try:
            return pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            arquivo.seek(0)
            return pd.read_csv(arquivo, sep=None, engine="python", encoding="latin-1")
    return pd.read_excel(arquivo, sheet_name=aba or 0)


_PADRAO_BR = re.compile(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$|^-?\d+,\d+$")


def _tentar_numerico(serie: pd.Series) -> pd.Series | None:
    """Converte texto em número (aceita R$, %, e formato brasileiro 1.234,56)."""
    preenchidos = serie.dropna()
    if preenchidos.empty:
        return None
    limpo = serie.astype("string").str.strip().str.replace(r"[R$\s%]", "", regex=True)
    # Formato brasileiro (1.234,56) só se a maioria dos valores seguir o padrão
    if limpo.dropna().str.match(_PADRAO_BR).mean() > 0.8:
        limpo = limpo.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    convertido = pd.to_numeric(limpo, errors="coerce")
    if convertido.notna().sum() >= 0.9 * len(preenchidos):
        return convertido.astype("float64")
    return None


def _tentar_data(serie: pd.Series) -> pd.Series | None:
    s = serie.dropna().astype(str).str.strip()
    if s.empty or not s.str.contains(r"\d", regex=True).all():
        return None
    # Datas costumam ter separadores; evita confundir códigos numéricos com datas
    if not s.str.contains(r"[-/]", regex=True).mean() > 0.9:
        return None
    convertido = pd.to_datetime(serie, errors="coerce", dayfirst=True, format="mixed")
    if convertido.notna().sum() >= 0.9 * serie.notna().sum():
        return convertido
    return None


def _eh_texto(serie: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie)


def preparar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Limpa a base e converte tipos. Retorna (df_limpo, lista_de_ajustes_feitos)."""
    ajustes: list[str] = []
    df = df.copy()

    df.columns = [str(c).strip() if not str(c).startswith("Unnamed") else f"coluna_{i+1}"
                  for i, c in enumerate(df.columns)]
    # Nomes de colunas duplicados
    vistos: dict[str, int] = {}
    novas = []
    for c in df.columns:
        if c in vistos:
            vistos[c] += 1
            novas.append(f"{c}_{vistos[c]}")
        else:
            vistos[c] = 0
            novas.append(c)
    df.columns = novas

    antes = df.shape
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.shape != antes:
        ajustes.append(
            f"Removidas {antes[0] - df.shape[0]} linha(s) e {antes[1] - df.shape[1]} coluna(s) totalmente vazias."
        )

    for col in df.columns:
        if not _eh_texto(df[col]):
            continue
        num = _tentar_numerico(df[col])
        if num is not None:
            df[col] = num
            ajustes.append(f"Coluna '{col}' convertida para número.")
            continue
        data = _tentar_data(df[col])
        if data is not None:
            df[col] = data
            ajustes.append(f"Coluna '{col}' convertida para data.")

    return df.reset_index(drop=True), ajustes


# ---------------------------------------------------------------------------
# Perfil da base
# ---------------------------------------------------------------------------


def classificar_colunas(df: pd.DataFrame) -> dict[str, list[str]]:
    tipos: dict[str, list[str]] = {"numerica": [], "categorica": [], "data": [], "texto": [], "booleana": []}
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_bool_dtype(s):
            tipos["booleana"].append(col)
        elif pd.api.types.is_numeric_dtype(s):
            tipos["numerica"].append(col)
        elif pd.api.types.is_datetime64_any_dtype(s):
            tipos["data"].append(col)
        else:
            n_unicos = s.nunique(dropna=True)
            limite = max(30, int(0.05 * len(s)))
            if n_unicos <= limite or n_unicos / max(len(s), 1) < 0.5:
                tipos["categorica"].append(col)
            else:
                tipos["texto"].append(col)
    return tipos


NOMES_TIPO = {"numerica": "Numérica", "categorica": "Categórica", "data": "Data",
              "texto": "Texto livre", "booleana": "Sim/Não"}


def resumo_geral(df: pd.DataFrame) -> dict:
    total_celulas = df.size or 1
    return {
        "linhas": len(df),
        "colunas": df.shape[1],
        "celulas_vazias_pct": round(100 * df.isna().sum().sum() / total_celulas, 1),
        "linhas_duplicadas": int(df.duplicated().sum()),
    }


def perfil_colunas(df: pd.DataFrame) -> pd.DataFrame:
    tipos = classificar_colunas(df)
    tipo_de = {c: NOMES_TIPO[t] for t, cols in tipos.items() for c in cols}
    linhas = []
    for col in df.columns:
        s = df[col]
        exemplo = s.dropna().iloc[0] if s.notna().any() else ""
        linhas.append({
            "Coluna": col,
            "Tipo": tipo_de.get(col, "?"),
            "Preenchidos": int(s.notna().sum()),
            "Vazios (%)": round(100 * s.isna().mean(), 1),
            "Valores únicos": int(s.nunique(dropna=True)),
            "Exemplo": str(exemplo)[:40],
        })
    return pd.DataFrame(linhas)


def estatisticas_numericas(df: pd.DataFrame) -> pd.DataFrame:
    cols = classificar_colunas(df)["numerica"]
    if not cols:
        return pd.DataFrame()
    desc = df[cols].describe().T
    desc = desc.rename(columns={"count": "qtd", "mean": "média", "std": "desvio padrão", "min": "mínimo",
                                "25%": "Q1 (25%)", "50%": "mediana", "75%": "Q3 (75%)", "max": "máximo"})
    desc["soma"] = df[cols].sum()
    return desc.round(2)


def correlacoes_fortes(df: pd.DataFrame, limite: float = 0.6) -> list[tuple[str, str, float]]:
    cols = classificar_colunas(df)["numerica"]
    if len(cols) < 2:
        return []
    corr = df[cols].corr(numeric_only=True)
    pares = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            v = corr.loc[a, b]
            if pd.notna(v) and abs(v) >= limite:
                pares.append((a, b, round(float(v), 2)))
    return sorted(pares, key=lambda p: -abs(p[2]))


def contar_outliers(serie: pd.Series) -> int:
    s = serie.dropna()
    if len(s) < 10:
        return 0
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return 0
    return int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())


def insights_automaticos(df: pd.DataFrame) -> list[tuple[str, str]]:
    """Achados baseados em regras (funcionam mesmo sem IA).

    Retorna pares (categoria, texto), com categoria em: "Qualidade", "Destaque", "Padrão".
    """
    achados: list[tuple[str, str]] = []
    tipos = classificar_colunas(df)
    r = resumo_geral(df)

    if r["linhas_duplicadas"]:
        achados.append(("Qualidade", f"Há <b>{r['linhas_duplicadas']}</b> linha(s) duplicada(s) na base."))

    for col in df.columns:
        pct = 100 * df[col].isna().mean()
        if pct >= 20:
            achados.append(("Qualidade", f"A coluna <b>{col}</b> tem <b>{pct:.0f}%</b> de valores vazios."))
        if df[col].nunique(dropna=True) == 1 and len(df) > 1:
            achados.append(("Qualidade", f"A coluna <b>{col}</b> tem o mesmo valor em todas as linhas."))

    for a, b, v in correlacoes_fortes(df):
        direcao = "positiva" if v > 0 else "negativa"
        achados.append(("Destaque", f"Correlação {direcao} forte entre <b>{a}</b> e <b>{b}</b> (r = {v})."))

    for col in tipos["categorica"]:
        vc = df[col].value_counts(normalize=True, dropna=True)
        if len(vc) > 1 and vc.iloc[0] > 0.5:
            achados.append(("Destaque", f"Em <b>{col}</b>, <b>{vc.index[0]}</b> concentra "
                                        f"{100 * vc.iloc[0]:.0f}% dos registros."))

    for col in tipos["numerica"]:
        n = contar_outliers(df[col])
        if n:
            achados.append(("Padrão", f"<b>{col}</b> tem <b>{n}</b> valor(es) atípico(s) (critério IQR)."))
        s = df[col].dropna()
        if len(s) > 10 and s.std() > 0:
            assim = s.skew()
            if abs(assim) > 1.5:
                lado = "poucos valores muito altos" if assim > 0 else "poucos valores muito baixos"
                achados.append(("Padrão", f"<b>{col}</b> é assimétrica, puxada por {lado}."))

    for col in tipos["data"]:
        s = df[col].dropna()
        if not s.empty:
            achados.append(("Padrão", f"<b>{col}</b> cobre de {s.min():%d/%m/%Y} a {s.max():%d/%m/%Y}."))

    return achados or [("Padrão", "Nenhum problema evidente encontrado na base.")]


_PALAVRAS_METRICA = ("fatur", "receita", "venda", "valor", "total", "lucro", "preço", "preco",
                     "custo", "montante", "quantidade", "qtd")


def metrica_principal(df: pd.DataFrame) -> str | None:
    """Escolhe a coluna numérica que mais parece um indicador de negócio (ex.: Faturamento)."""
    nums = [c for c in classificar_colunas(df)["numerica"]
            if not re.search(r"(^|_|\s)(id|cod|código|codigo|cep|ano|mes|mês)($|_|\s)", c.lower())]
    if not nums:
        return None
    for palavra in _PALAVRAS_METRICA:
        for c in nums:
            if palavra in c.lower():
                return c
    return max(nums, key=lambda c: abs(df[c].sum()))


def formatar_numero(valor: float, casas: int = 0) -> str:
    """Formato brasileiro compacto: 1,2 mi / 345,6 mil / 1.234."""
    if valor is None or pd.isna(valor):
        return "—"
    v = abs(valor)
    if v >= 1e9:
        texto = f"{valor / 1e9:,.1f} bi"
    elif v >= 1e6:
        texto = f"{valor / 1e6:,.1f} mi"
    elif v >= 1e4:
        texto = f"{valor / 1e3:,.1f} mil"
    else:
        texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def perfil_para_ia(df: pd.DataFrame, max_caracteres: int = 12000) -> str:
    """Resumo compacto da base para enviar à IA (não envia a base inteira)."""
    tipos = classificar_colunas(df)
    tipo_de = {c: t for t, cols in tipos.items() for c in cols}
    partes = [f"Base com {len(df)} linhas e {df.shape[1]} colunas.", "", "COLUNAS:"]
    for col in df.columns:
        s = df[col]
        linha = f"- {col!r} | tipo={tipo_de.get(col)} | dtype={s.dtype} | vazios={s.isna().mean():.0%} | únicos={s.nunique()}"
        t = tipo_de.get(col)
        if t == "numerica" and s.notna().any():
            linha += (f" | min={s.min():.4g} média={s.mean():.4g} mediana={s.median():.4g} "
                      f"max={s.max():.4g} soma={s.sum():.4g}")
        elif t == "data" and s.notna().any():
            linha += f" | de {s.min():%Y-%m-%d} até {s.max():%Y-%m-%d}"
        elif t in ("categorica", "booleana", "texto"):
            top = s.value_counts().head(8)
            linha += " | mais frequentes: " + ", ".join(f"{k} ({v})" for k, v in top.items())
        partes.append(linha)

    corr = correlacoes_fortes(df, 0.5)
    if corr:
        partes += ["", "CORRELAÇÕES RELEVANTES:"] + [f"- {a} x {b}: {v}" for a, b, v in corr[:10]]

    partes += ["", "ACHADOS AUTOMÁTICOS:"] + [
        f"- [{cat}] " + re.sub(r"</?b>", "", texto) for cat, texto in insights_automaticos(df)
    ]
    partes += ["", "AMOSTRA (5 primeiras linhas):", df.head(5).to_string(max_colwidth=30)]

    texto = "\n".join(partes)
    return texto[:max_caracteres]




# ---------------------------------------------------------------------------
# Gráficos — tema executivo
# ---------------------------------------------------------------------------

# Paleta categórica validada para daltonismo (ordem fixa, nunca reciclada)
PALETA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
COR_PRINCIPAL = PALETA[0]
TINTA, TINTA_2, GRADE = "#0f1b2d", "#5b6577", "#e8ebf0"
FONTE = "Inter, 'Segoe UI', system-ui, sans-serif"

_TEMPLATE = go.layout.Template(layout=dict(
    font=dict(family=FONTE, size=12, color=TINTA_2),
    title=dict(font=dict(size=15, color=TINTA, weight=600), x=0, xanchor="left", y=0.97, pad=dict(l=4)),
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    colorway=PALETA,
    margin=dict(l=12, r=20, t=60, b=24),
    xaxis=dict(automargin=True, ticklabelstandoff=6, showgrid=False, linecolor=GRADE, ticks="", zeroline=False, title_font=dict(size=11)),
    yaxis=dict(automargin=True, ticklabelstandoff=8, gridcolor=GRADE, griddash="dot", linecolor="rgba(0,0,0,0)", zeroline=False,
               title_font=dict(size=11)),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title_text="",
                font=dict(size=11)),
    hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRADE, font=dict(family=FONTE, size=12, color=TINTA)),
    bargap=0.35,
))


def _finalizar(fig, altura: int = 360):
    fig.update_layout(height=altura, separators=",.")
    return fig


def grafico_distribuicao(df: pd.DataFrame, col: str):
    fig = px.histogram(df, x=col, nbins=30, template=_TEMPLATE, title=f"Distribuição · {col}",
                       color_discrete_sequence=[COR_PRINCIPAL])
    fig.update_traces(marker_line_color="#ffffff", marker_line_width=1,
                      hovertemplate=f"{col}: %{{x}}<br>Registros: %{{y}}<extra></extra>")
    fig.update_layout(bargap=0.04, yaxis_title="Registros", xaxis_title=None)
    return _finalizar(fig)


def grafico_categoria(df: pd.DataFrame, col: str, valor: str | None = None, top: int = 10,
                      altura: int | None = None):
    """Ranking horizontal ordenado (maior no topo)."""
    if valor:
        dados = df.groupby(col, dropna=True)[valor].sum().sort_values(ascending=False).head(top)
        titulo, eixo = f"{valor} por {col}", valor
    else:
        dados = df[col].value_counts().head(top)
        titulo, eixo = f"Registros por {col}", "Registros"
    dados = dados.rename_axis(col).reset_index(name=eixo).iloc[::-1]
    dados[col] = dados[col].astype(str)
    fig = px.bar(dados, x=eixo, y=col, orientation="h", template=_TEMPLATE, title=titulo,
                 color_discrete_sequence=[COR_PRINCIPAL], text=dados[eixo].map(formatar_numero))
    fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=TINTA_2, size=11),
                      hovertemplate=f"%{{y}}<br>{eixo}: %{{x:,.2f}}<extra></extra>")
    maximo = float(dados[eixo].max()) if len(dados) else 1
    fig.update_layout(xaxis=dict(showgrid=False, showticklabels=False, title=None,
                                 range=[0, maximo * 1.18]),
                      yaxis=dict(showgrid=False, title=None, type="category"))
    return _finalizar(fig, altura or max(260, 34 * len(dados) + 90))


def heatmap_correlacao(df: pd.DataFrame):
    cols = classificar_colunas(df)["numerica"]
    if len(cols) < 2:
        return None
    corr = df[cols].corr(numeric_only=True).round(2)
    # Divergente: laranja (negativa) — cinza neutro (zero) — azul (positiva)
    escala = [[0, "#d95926"], [0.5, "#f1f2f4"], [1, "#1c5cab"]]
    fig = px.imshow(corr, text_auto=True, color_continuous_scale=escala, zmin=-1, zmax=1,
                    template=_TEMPLATE, title="Correlação entre indicadores", aspect="auto")
    fig.update_traces(xgap=2, ygap=2, hovertemplate="%{x} × %{y}<br>r = %{z}<extra></extra>")
    fig.update_layout(coloraxis_colorbar=dict(thickness=10, outlinewidth=0, title=None),
                      xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))
    return _finalizar(fig, max(320, 60 * len(cols) + 100))


def serie_temporal(df: pd.DataFrame, col_data: str, col_valor: str | None = None,
                   altura: int = 360):
    s = df.dropna(subset=[col_data]).set_index(col_data).sort_index()
    if s.empty:
        return None
    dias = (s.index.max() - s.index.min()).days
    freq, nome = ("D", "dia") if dias <= 60 else ("W", "semana") if dias <= 180 else ("MS", "mês")
    if col_valor:
        dados = s[col_valor].resample(freq).sum().reset_index()
        titulo, y = f"{col_valor} por {nome}", col_valor
    else:
        dados = s.resample(freq).size().reset_index(name="Registros")
        titulo, y = f"Registros por {nome}", "Registros"
    fig = px.area(dados, x=col_data, y=y, template=_TEMPLATE, title=titulo,
                  color_discrete_sequence=[COR_PRINCIPAL], markers=True)
    fig.update_traces(line=dict(width=2), marker=dict(size=7, line=dict(width=2, color="#ffffff")),
                      fillcolor="rgba(42,120,214,0.08)",
                      hovertemplate="%{x|%d/%m/%Y}<br>" + y + ": %{y:,.2f}<extra></extra>")
    formato = "%m/%Y" if freq == "MS" else "%d/%m"
    fig.update_layout(xaxis_title=None, yaxis_title=None, hovermode="x unified",
                      xaxis=dict(tickformat=formato))
    return _finalizar(fig, altura)


def dispersao(df: pd.DataFrame, x: str, y: str, cor: str | None = None):
    dados = df
    if cor:  # no máximo 3 cores distintas em dispersão; o resto vira "Outros"
        principais = df[cor].value_counts().head(3).index
        dados = df.assign(**{cor: df[cor].where(df[cor].isin(principais), "Outros")})
    fig = px.scatter(dados, x=x, y=y, color=cor, template=_TEMPLATE, title=f"{y} × {x}",
                     color_discrete_sequence=PALETA[:3] + ["#9aa3b2"])
    fig.update_traces(marker=dict(size=8, opacity=0.75, line=dict(width=1, color="#ffffff")))
    return _finalizar(fig, 420)


# ---------------------------------------------------------------------------
# Indicadores-chave (usados na tela e no PDF)
# ---------------------------------------------------------------------------

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def mes_ano(ts) -> str:
    return f"{MESES[ts.month - 1]}/{ts.year}"


def indicadores_chave(df: pd.DataFrame, metrica: str | None) -> list[tuple[str, str, str]]:
    """Até 5 KPIs no formato (rótulo, valor, complemento)."""
    tipos = classificar_colunas(df)
    datas, cat = tipos["data"], tipos["categorica"]
    kpis: list[tuple[str, str, str]] = []

    if metrica:
        s = df[metrica]
        kpis.append((f"{metrica} · total", formatar_numero(s.sum(), 2 if abs(s.sum()) < 1e4 else 0),
                     f"média {formatar_numero(s.mean(), 2)} / registro"))
    if datas:
        d = df[datas[0]].dropna()
        if not d.empty:
            periodo = (f"{MESES[d.min().month - 1]}–{mes_ano(d.max())}" if d.min().year == d.max().year
                       else f"{mes_ano(d.min())}–{mes_ano(d.max())}")
            kpis.append(("Período", periodo, f"{(d.max() - d.min()).days + 1} dias de dados"))
            if metrica:
                por_mes = df.dropna(subset=[datas[0]]).set_index(datas[0])[metrica].resample("MS").sum()
                if len(por_mes) > 1:
                    kpis.append(("Melhor mês", mes_ano(por_mes.idxmax()),
                                 f"{formatar_numero(por_mes.max())} em {metrica.lower()}"))
    if cat:
        c0 = cat[0]
        g = (df.groupby(c0)[metrica].sum() if metrica else df[c0].value_counts()).sort_values(ascending=False)
        participacao = 100 * g.iloc[0] / g.sum() if g.sum() else 0
        kpis.append((f"Líder em {c0}", str(g.index[0]), f"{participacao:.0f}% do total"))

    preenchido = 100 - resumo_geral(df)["celulas_vazias_pct"]
    kpis.append(("Registros", formatar_numero(len(df)), f"{preenchido:.1f}% preenchido".replace(".", ",")))
    return kpis[:5]


def grafico_resultado(res: pd.DataFrame):
    """Gráfico automático para o resultado de uma consulta (rótulo + valor)."""
    if not isinstance(res, pd.DataFrame) or res.shape[1] != 2 or not 2 <= len(res) <= 40:
        return None
    rotulo, valor = res.columns
    if not pd.api.types.is_numeric_dtype(res[valor]) or pd.api.types.is_numeric_dtype(res[rotulo]):
        return None
    if pd.api.types.is_datetime64_any_dtype(res[rotulo]):
        fig = px.line(res.sort_values(rotulo), x=rotulo, y=valor, markers=True, template=_TEMPLATE,
                      color_discrete_sequence=[COR_PRINCIPAL], title=f"{valor} por {rotulo}")
        fig.update_traces(line=dict(width=2), marker=dict(size=7, line=dict(width=2, color="#ffffff")))
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        return _finalizar(fig)
    dados = res.iloc[::-1].copy()
    dados[rotulo] = dados[rotulo].astype(str)
    fig = px.bar(dados, x=valor, y=rotulo, orientation="h", template=_TEMPLATE, title=f"{valor} por {rotulo}",
                 color_discrete_sequence=[COR_PRINCIPAL], text=dados[valor].map(formatar_numero))
    fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=TINTA_2, size=11))
    fig.update_layout(xaxis=dict(showgrid=False, showticklabels=False, title=None,
                                 range=[0, float(dados[valor].max()) * 1.18]),
                      yaxis=dict(showgrid=False, title=None, type="category"))
    return _finalizar(fig, max(240, 32 * len(dados) + 90))
