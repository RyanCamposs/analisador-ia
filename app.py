"""Analisador de Dados com IA — envie um Excel/CSV e receba a análise automaticamente.

Execute com:  streamlit run app.py
"""

from __future__ import annotations

import html
import io
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import analise as an
import ia
import pdf_relatorio

load_dotenv(Path(__file__).parent / ".env")
PASTA = Path(__file__).parent
EXEMPLO = PASTA / "exemplo_vendas.xlsx"



def config(nome: str, padrao: str | None = None) -> str | None:
    """Lê uma configuração dos secrets (Streamlit Cloud) ou do .env (local)."""
    try:
        if nome in st.secrets:
            return str(st.secrets[nome])
    except Exception:  # noqa: BLE001 - sem secrets.toml
        pass
    return os.getenv(nome, padrao)


MODO_PUBLICO = config("MODO_PUBLICO", "0") == "1"
LIMITE_IA = int(config("LIMITE_IA_SESSAO", "0") or 0)  # 0 = sem limite
AUTOR, LINK_GITHUB, LINK_LINKEDIN = config("AUTOR"), config("LINK_GITHUB"), config("LINK_LINKEDIN")

st.set_page_config(page_title="Analisador de Dados", page_icon=":material/monitoring:", layout="wide")

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1320px;}
  [data-testid="stHeader"] {background: transparent;}
  [data-testid="stDecoration"], [data-testid="stStatusWidget"], .stDeployButton,
  [data-testid="stAppDeployButton"], footer {display: none !important;}

  /* Cabeçalho */
  .cab {display:flex; justify-content:space-between; align-items:flex-end; gap:24px;
        border-bottom:1px solid #e3e6eb; padding-bottom:18px; margin-bottom:22px; flex-wrap:wrap;}
  .cab .sobre {font-size:11px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:#1c5cab;}
  .cab h1 {font-size:28px; font-weight:700; color:#0f1b2d; margin:4px 0 0; padding:0; line-height:1.2;}
  .cab .meta {font-size:13px; color:#5b6577; text-align:right; line-height:1.6;}

  /* KPIs */
  .kpis {display:grid; grid-template-columns:repeat(auto-fit, minmax(165px, 1fr)); gap:12px; margin:4px 0 26px;}
  .kpi {background:#fff; border:1px solid #e3e6eb; border-radius:8px; padding:16px 18px 14px;
        border-top:3px solid #1c5cab;}
  .kpi .rot {font-size:11px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:#5b6577;}
  .kpi .val {font-size:22px; font-weight:700; color:#0f1b2d; margin:6px 0 4px; line-height:1.2;
             font-variant-numeric: tabular-nums; overflow-wrap:anywhere;}
  .kpi .sub {font-size:12px; color:#5b6577;}

  /* Títulos de seção */
  .secao {font-size:12px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:#5b6577;
          margin:26px 0 12px; display:flex; align-items:center; gap:12px;}
  .secao::after {content:""; flex:1; height:1px; background:#e3e6eb;}

  /* Achados */
  .achados {display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:10px;}
  .achado {background:#fff; border:1px solid #e3e6eb; border-radius:8px; padding:12px 14px;
           font-size:14px; color:#28334a; display:flex; gap:12px; align-items:flex-start;}
  .tag {font-size:10px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; padding:3px 8px;
        border-radius:4px; white-space:nowrap; margin-top:1px;}
  .tag-Qualidade {background:#fff4dc; color:#8a5a00;}
  .tag-Destaque  {background:#e3eefb; color:#184f95;}
  .tag-Padrão    {background:#eef0f3; color:#3d4759;}

  /* Gráficos e cartões */
  [data-testid="stPlotlyChart"] {background:#fff; border:1px solid #e3e6eb; border-radius:8px; padding:6px 6px 0;}
  [data-testid="stVerticalBlockBorderWrapper"] {background:#fff;}

  /* Abas */
  .stTabs [data-baseweb="tab-list"] {gap:28px; border-bottom:1px solid #e3e6eb;}
  .stTabs [data-baseweb="tab"] {padding:10px 2px; font-weight:500;}

  /* Tela inicial */
  .vazio {background:#fff; border:1px solid #e3e6eb; border-radius:10px; padding:40px 44px; margin-top:8px;}
  .vazio h2 {font-size:24px; color:#0f1b2d; margin:0 0 8px; padding:0;}
  .vazio p {color:#5b6577; font-size:15px; max-width:640px;}
  .passos {display:grid; grid-template-columns:repeat(auto-fit, minmax(200px,1fr)); gap:18px; margin-top:26px;}
  .passo .n {font-size:12px; font-weight:700; color:#1c5cab; letter-spacing:.08em;}
  .passo .t {font-weight:600; color:#0f1b2d; margin:4px 0 2px;}
  .passo .d {font-size:13px; color:#5b6577;}

  /* Barra lateral */
  [data-testid="stSidebar"] .marca {font-size:17px; font-weight:700; letter-spacing:.01em; margin-bottom:2px;}
  [data-testid="stSidebar"] .marca span {color:#7fb0ee;}
  [data-testid="stSidebar"] .sec-lat {font-size:11px; font-weight:600; letter-spacing:.12em;
          text-transform:uppercase; color:#8d9bb3; margin:18px 0 6px;}
</style>
""", unsafe_allow_html=True)


def secao(titulo: str) -> None:
    st.markdown(f'<div class="secao">{html.escape(titulo)}</div>', unsafe_allow_html=True)


def cartoes_kpi(itens: list[tuple[str, str, str]]) -> None:
    corpo = "".join(
        f'<div class="kpi"><div class="rot">{html.escape(r)}</div>'
        f'<div class="val" title="{html.escape(v)}">{html.escape(v)}</div>'
        f'<div class="sub">{html.escape(s)}</div></div>'
        for r, v, s in itens
    )
    st.markdown(f'<div class="kpis">{corpo}</div>', unsafe_allow_html=True)


def grafico(fig, chave: str) -> None:
    st.plotly_chart(fig, width="stretch", key=chave, theme=None, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Carregamento (com cache para não reprocessar a cada clique)
# ---------------------------------------------------------------------------

def _arquivo_em_memoria(conteudo: bytes, nome: str) -> io.BytesIO:
    buf = io.BytesIO(conteudo)
    buf.name = nome
    return buf


@st.cache_data(show_spinner=False)
def abas_do_arquivo(conteudo: bytes, nome: str) -> list[str]:
    return an.listar_abas(_arquivo_em_memoria(conteudo, nome))


@st.cache_data(show_spinner="Lendo e preparando a base...")
def base_preparada(conteudo: bytes, nome: str, aba: str | None):
    bruto = an.carregar_arquivo(_arquivo_em_memoria(conteudo, nome), aba)
    return an.preparar(bruto)


@st.cache_data(show_spinner=False, ttl=3600)
def modelos_disponiveis(provedor: str, chave: str | None) -> list[str]:
    try:
        return ia.listar_modelos(provedor, chave)
    except Exception:  # noqa: BLE001 - sem conexão/chave inválida: cai no campo de texto
        return []


@st.cache_data(show_spinner="Gerando PDF...")
def pdf_resumo(df: pd.DataFrame, nome: str, titulo: str, metrica: str | None, relatorio: str | None) -> bytes:
    return pdf_relatorio.gerar_pdf(df, nome, titulo, metrica, relatorio)


def botao_pdf(chave: str, rotulo: str = "Exportar PDF", primario: bool = False) -> None:
    try:
        dados = pdf_resumo(df, nome, titulo, metrica, st.session_state.relatorio)
    except Exception as e:  # noqa: BLE001
        st.error(f"Não foi possível gerar o PDF: {e}")
        return
    st.download_button(rotulo, data=dados, file_name=f"resumo_{Path(nome).stem}.pdf",
                       mime="application/pdf", icon=":material/picture_as_pdf:", key=chave,
                       type="primary" if primario else "secondary", width="stretch")


@st.cache_data(show_spinner=False)
def perfil_ia(df: pd.DataFrame) -> str:
    return an.perfil_para_ia(df)


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<div class="marca">Analisador <span>de Dados</span></div>', unsafe_allow_html=True)
    st.caption("Análise automática com inteligência artificial")

    st.markdown('<div class="sec-lat">Base de dados</div>', unsafe_allow_html=True)
    enviado = st.file_uploader("Planilha Excel ou CSV", type=["xlsx", "xls", "csv"],
                               label_visibility="collapsed")

    st.markdown('<div class="sec-lat">Inteligência artificial</div>', unsafe_allow_html=True)
    opcoes = [p for p in ia.PROVEDORES if not (MODO_PUBLICO and not ia.PROVEDORES[p]["env"])]
    provedor = st.selectbox("Provedor", opcoes)
    cfg = ia.PROVEDORES[provedor]

    chave, usando_servidor = None, False
    if cfg["env"]:
        chave_servidor = config(cfg["env"])
        if chave_servidor:
            st.caption(":material/check_circle: IA pronta para uso.")
            propria = st.text_input("Sua própria chave (opcional)", type="password",
                                    help="Com a sua chave não há limite de perguntas.")
        else:
            propria = st.text_input("Chave da API", type="password",
                                    help=f"Também pode ser definida no arquivo .env como {cfg['env']}=...")
            st.caption(f"[Obter chave gratuita]({cfg['link']})")
        chave = propria or chave_servidor
        usando_servidor = bool(chave_servidor) and not propria
    else:
        st.caption(f"Requer o [Ollama]({cfg['link']}) instalado e um modelo baixado "
                   f"(ex.: `ollama pull {cfg['preferidos'][0]}`). Os dados não saem do computador.")

    modelos = modelos_disponiveis(provedor, chave) if (chave or not cfg["env"]) else []
    if modelos:
        modelo = st.selectbox("Modelo", modelos, key=f"modelo_{provedor}",
                              help="Lista obtida do provedor agora. O primeiro é o recomendado.")
    else:
        modelo = st.text_input("Modelo", value=cfg["preferidos"][0], key=f"modelo_txt_{provedor}",
                               help="Não consegui listar os modelos do provedor; digite o nome manualmente.")

    contexto = st.text_area(
        "Contexto da análise (opcional)",
        placeholder="Ex.: vendas de 2025; quero entender quais produtos dão mais lucro.",
        help="Ajuda a IA a direcionar o relatório.",
    )

if "uso_ia" not in st.session_state:
    st.session_state.uso_ia = 0
limite_ativo = usando_servidor and LIMITE_IA > 0
restantes = max(LIMITE_IA - st.session_state.uso_ia, 0) if limite_ativo else None
with st.sidebar:
    contador_uso = st.empty()  # preenchido no fim da página, depois das chamadas à IA
    if AUTOR or LINK_GITHUB or LINK_LINKEDIN:
        links = " · ".join(f"[{n}]({u})" for n, u in (("GitHub", LINK_GITHUB), ("LinkedIn", LINK_LINKEDIN)) if u)
        st.markdown('<div class="sec-lat">Projeto de portfólio</div>', unsafe_allow_html=True)
        if AUTOR:
            st.caption(f"Desenvolvido por **{AUTOR}**")
        if links:
            st.caption(links)


def registrar_uso_ia() -> None:
    st.session_state.uso_ia += 1


ia_pronta = (bool(chave) or not cfg["env"]) and restantes != 0
cliente = ia.ClienteIA(provedor, chave, modelo) if ia_pronta else None

# ---------------------------------------------------------------------------
# Tela inicial (sem base)
# ---------------------------------------------------------------------------

if st.query_params.get("demo"):
    st.session_state.usar_exemplo = True

if enviado is not None:
    conteudo, nome = enviado.getvalue(), enviado.name
elif st.session_state.get("usar_exemplo") and EXEMPLO.exists():
    conteudo, nome = EXEMPLO.read_bytes(), EXEMPLO.name
else:
    st.markdown("""
    <div class="vazio">
      <div class="cab" style="border:none; padding:0; margin:0 0 6px;"><div class="sobre">Análise de dados com IA · Python · SQL · IA generativa</div></div>
      <h2>Transforme sua planilha em um relatório executivo</h2>
      <p>Envie um arquivo Excel ou CSV pela barra lateral. O sistema limpa os dados, calcula os indicadores,
         monta os gráficos e a IA escreve as conclusões — em segundos.</p>
      <div class="passos">
        <div class="passo"><div class="n">01</div><div class="t">Envie a base</div>
          <div class="d">.xlsx, .xls ou .csv, com várias abas ou não.</div></div>
        <div class="passo"><div class="n">02</div><div class="t">Veja os indicadores</div>
          <div class="d">Totais, períodos, líderes e alertas de qualidade.</div></div>
        <div class="passo"><div class="n">03</div><div class="t">Leia o relatório</div>
          <div class="d">Descobertas e recomendações escritas pela IA.</div></div>
        <div class="passo"><div class="n">04</div><div class="t">Faça perguntas</div>
          <div class="d">Em português, com resposta calculada sobre os dados.</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    if EXEMPLO.exists():
        st.write("")
        if st.button("Ver demonstração com base de exemplo", icon=":material/play_arrow:"):
            st.session_state.usar_exemplo = True
            st.rerun()
    st.stop()

# ---------------------------------------------------------------------------
# Leitura da base
# ---------------------------------------------------------------------------

abas = abas_do_arquivo(conteudo, nome)
aba = abas[0] if abas else None
if len(abas) > 1:
    with st.sidebar:
        aba = st.selectbox("Aba da planilha", abas)

try:
    df, ajustes = base_preparada(conteudo, nome, aba)
except Exception as e:  # noqa: BLE001
    st.error(f"Não consegui ler o arquivo: {e}")
    st.stop()

if df.empty:
    st.warning("A planilha (ou aba) selecionada está vazia.")
    st.stop()

# Ao trocar de arquivo/aba, limpa relatório e conversa anteriores
id_base = f"{nome}|{len(conteudo)}|{aba}"
if st.session_state.get("id_base") != id_base:
    st.session_state.update(id_base=id_base, relatorio=None, conversa=[])

tipos = an.classificar_colunas(df)
num, cat, datas = tipos["numerica"], tipos["categorica"], tipos["data"]

sugerida = an.metrica_principal(df)
with st.sidebar:
    if num:
        metrica = st.selectbox("Indicador principal", num,
                               index=num.index(sugerida) if sugerida in num else 0,
                               help="Coluna usada nos totais, rankings e evolução no tempo.")
    else:
        metrica = None

# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------

r = an.resumo_geral(df)
titulo = Path(nome).stem.replace("_", " ").replace("-", " ").strip().capitalize()
detalhe_aba = f" · aba {html.escape(aba)}" if aba and len(abas) > 1 else ""
st.markdown(f"""
<div class="cab">
  <div><div class="sobre">Relatório de análise</div><h1>{html.escape(titulo)}</h1></div>
  <div class="meta">{html.escape(nome)}{detalhe_aba}<br>
    {an.formatar_numero(r['linhas'])} registros · {r['colunas']} colunas ·
    atualizado em {an.agora():%d/%m/%Y às %H:%M}</div>
</div>
""", unsafe_allow_html=True)

aba_resumo, aba_painel, aba_relatorio, aba_chat, aba_dados = st.tabs([
    ":material/dashboard: Resumo executivo",
    ":material/bar_chart: Painel",
    ":material/description: Relatório da IA",
    ":material/forum: Consulta aos dados",
    ":material/table: Dados",
])


# ---------------------------------------------------------------------------
# 1) Resumo executivo
# ---------------------------------------------------------------------------

with aba_resumo:
    nota, col_pdf = st.columns([4, 1], vertical_alignment="center")
    with col_pdf:
        botao_pdf("pdf_resumo", primario=True)
    if not st.session_state.relatorio:
        nota.caption("Dica: gere o **Relatório da IA** antes de exportar para incluí-lo no PDF.")

    kpis = an.indicadores_chave(df, metrica)
    cartoes_kpi(kpis[:5])

    col_a, col_b = st.columns([3, 2], gap="medium")
    with col_a:
        fig = an.serie_temporal(df, datas[0], metrica, altura=380) if datas else None
        if fig is None and len(cat) > 1:
            fig = an.grafico_categoria(df, cat[1], metrica)
        if fig is not None:
            grafico(fig, "res_a")
    with col_b:
        if cat:
            grafico(an.grafico_categoria(df, cat[0], metrica, top=8, altura=380), "res_b")
        elif metrica:
            grafico(an.grafico_distribuicao(df, metrica), "res_b")

    secao("Achados automáticos")
    achados = an.insights_automaticos(df)
    ordem = {"Destaque": 0, "Qualidade": 1, "Padrão": 2}
    achados = sorted(achados, key=lambda a: ordem.get(a[0], 3))
    st.markdown(
        '<div class="achados">' + "".join(
            f'<div class="achado"><span class="tag tag-{c}">{c}</span><span>{t}</span></div>'
            for c, t in achados
        ) + "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# 2) Painel completo + gráfico livre
# ---------------------------------------------------------------------------

with aba_painel:
    secao("Rankings")
    if cat:
        colunas = st.columns(2, gap="medium")
        for i, c in enumerate(cat[:4]):
            with colunas[i % 2]:
                grafico(an.grafico_categoria(df, c, metrica), f"rank_{i}")
    else:
        st.caption("A base não tem colunas de categoria para ranking.")

    if num:
        secao("Distribuições")
        colunas = st.columns(3, gap="medium")
        for i, c in enumerate(num[:6]):
            with colunas[i % 3]:
                grafico(an.grafico_distribuicao(df, c), f"dist_{i}")

    heat = an.heatmap_correlacao(df)
    if heat is not None:
        secao("Relações entre indicadores")
        grafico(heat, "heat")

    secao("Análise personalizada")
    with st.container(border=True):
        tipo = st.segmented_control("Tipo de gráfico", ["Ranking", "Evolução", "Dispersão", "Distribuição"],
                                    default="Ranking")
        c1, c2, c3 = st.columns(3)
        fig = None
        try:
            if tipo == "Ranking" and cat:
                x = c1.selectbox("Agrupar por", cat)
                y = c2.selectbox("Medida", ["Contagem de registros"] + num)
                top = c3.slider("Quantidade de itens", 5, 30, 10)
                fig = an.grafico_categoria(df, x, None if y.startswith("Contagem") else y, top=top)
            elif tipo == "Evolução" and datas:
                x = c1.selectbox("Data", datas)
                y = c2.selectbox("Medida", ["Contagem de registros"] + num)
                fig = an.serie_temporal(df, x, None if y.startswith("Contagem") else y)
            elif tipo == "Dispersão" and len(num) >= 2:
                x = c1.selectbox("Eixo horizontal", num)
                y = c2.selectbox("Eixo vertical", num, index=1)
                cor = c3.selectbox("Separar por", ["Nenhum"] + cat)
                fig = an.dispersao(df, x, y, None if cor == "Nenhum" else cor)
            elif tipo == "Distribuição" and num:
                fig = an.grafico_distribuicao(df, c1.selectbox("Indicador", num))
            elif tipo:
                st.info("A base não tem as colunas necessárias para este tipo de gráfico.")
            if fig is not None:
                grafico(fig, "livre")
        except Exception as e:  # noqa: BLE001
            st.error(f"Não foi possível gerar o gráfico: {e}")

# ---------------------------------------------------------------------------
# 3) Relatório escrito pela IA
# ---------------------------------------------------------------------------

AVISO_CHAVE = ("Limite de uso da IA desta demonstração atingido. Para continuar, cole a sua própria chave "
               "gratuita na barra lateral." if restantes == 0 else
               "Informe a chave da API na barra lateral (é gratuita) para usar a IA.")


def erro_ia(e: Exception) -> None:
    msg, baixo = str(e), str(e).lower()
    if "401" in msg or ("invalid" in baixo and "key" in baixo):
        st.error("Chave da API inválida. Confira a chave na barra lateral.")
    elif "429" in msg:
        st.error("Limite gratuito do provedor atingido. Aguarde um pouco ou troque de provedor.")
    elif "Connection" in type(e).__name__ or "connect" in baixo:
        st.error("Não consegui conectar ao provedor. Se for Ollama, verifique se ele está aberto.")
    elif "404" in msg or ("model" in baixo and any(
            t in baixo for t in ("not found", "does not exist", "decommission", "deprecated"))):
        modelos_disponiveis.clear()
        st.error("Este modelo não está mais disponível no provedor. Escolha outro no campo "
                 "**Modelo** da barra lateral (a lista foi atualizada).")
    else:
        st.error(f"Erro na IA: {msg}")


with aba_relatorio:
    topo_a, topo_b = st.columns([3, 1], vertical_alignment="center")
    topo_a.markdown("**Relatório analítico** — resumo, descobertas, qualidade dos dados e recomendações.")
    if not ia_pronta:
        st.warning(AVISO_CHAVE)
    else:
        rotulo = "Gerar novamente" if st.session_state.relatorio else "Gerar relatório"
        if topo_b.button(rotulo, type="primary", icon=":material/auto_awesome:", width="stretch"):
            with st.spinner("A IA está analisando seus dados..."):
                try:
                    registrar_uso_ia()
                    st.session_state.relatorio = ia.gerar_relatorio(cliente, perfil_ia(df), contexto)
                except Exception as e:  # noqa: BLE001
                    erro_ia(e)

    if st.session_state.relatorio:
        with st.container(border=True):
            st.markdown(st.session_state.relatorio)
        b1, b2, _ = st.columns([1, 1, 2])
        with b1:
            botao_pdf("pdf_relatorio", "Baixar PDF completo", primario=True)
        b2.download_button(
            "Baixar texto (.md)", icon=":material/download:", width="stretch",
            data=f"# Relatório — {nome}\n_Gerado em {an.agora():%d/%m/%Y %H:%M}_\n\n"
                 + st.session_state.relatorio,
            file_name=f"relatorio_{Path(nome).stem}.md",
            mime="text/markdown",
        )
    elif ia_pronta:
        st.caption("Clique em **Gerar relatório**. A IA recebe apenas um resumo estatístico da base, "
                   "nunca os dados completos.")

# ---------------------------------------------------------------------------
# 4) Perguntas em linguagem natural
# ---------------------------------------------------------------------------


def mostrar_resposta(resp: dict, indice: int, ultima: bool = False) -> None:
    if "erro" in resp:
        st.error(f"Não consegui responder: {resp['erro']}")
    else:
        st.markdown(resp["explicacao"])
        res = resp["resultado"]
        if res.shape == (1, 1):
            st.metric(str(res.columns[0]), an.formatar_numero(res.iat[0, 0], 2)
                      if isinstance(res.iat[0, 0], (int, float)) else str(res.iat[0, 0]))
        else:
            fig = an.grafico_resultado(res)
            if fig is not None:
                grafico(fig, f"chat_{indice}")
            st.dataframe(res, width="stretch", hide_index=True)
    if resp.get("sql"):
        with st.expander("Consulta SQL gerada", icon=":material/database:", expanded=ultima):
            st.code(resp["sql"], language="sql")


AVATAR = {"user": ":material/person:", "assistant": ":material/insights:"}

with aba_chat:
    st.caption("Pergunte em português — a IA escreve a consulta **SQL**, que é executada sobre os dados "
               "(DuckDB, somente leitura). Exemplos: *Qual o total por região?* · "
               "*Quais os 10 itens mais vendidos?* · *Como evoluiu o faturamento mês a mês?*")
    if not ia_pronta:
        st.warning(AVISO_CHAVE)

    for i, msg in enumerate(st.session_state.conversa):
        with st.chat_message(msg["papel"], avatar=AVATAR[msg["papel"]]):
            if msg["papel"] == "user":
                st.write(msg["texto"])
            else:
                mostrar_resposta(msg["resposta"], i)

    pergunta = st.chat_input("Faça uma pergunta sobre os dados...", disabled=not ia_pronta)
    if pergunta:
        st.session_state.conversa.append({"papel": "user", "texto": pergunta})
        with st.chat_message("user", avatar=AVATAR["user"]):
            st.write(pergunta)
        with st.chat_message("assistant", avatar=AVATAR["assistant"]):
            with st.spinner("Calculando..."):
                try:
                    registrar_uso_ia()
                    resposta = ia.responder_pergunta(cliente, df, perfil_ia(df), pergunta)
                except Exception as e:  # noqa: BLE001
                    erro_ia(e)
                    resposta = None
            if resposta:
                indice = len(st.session_state.conversa)
                mostrar_resposta(resposta, indice, ultima=True)
                st.session_state.conversa.append({"papel": "assistant", "resposta": resposta})

# ---------------------------------------------------------------------------
# 5) Dados
# ---------------------------------------------------------------------------

with aba_dados:
    if ajustes:
        with st.expander(f"{len(ajustes)} ajuste(s) automático(s) aplicados na base", icon=":material/cleaning_services:"):
            for a in ajustes:
                st.write("•", a)

    secao("Estrutura das colunas")
    st.dataframe(an.perfil_colunas(df), hide_index=True, width="stretch")

    estat = an.estatisticas_numericas(df)
    if not estat.empty:
        secao("Estatísticas dos indicadores")
        st.dataframe(estat, width="stretch")

    secao("Base completa")
    st.dataframe(df, height=420, width="stretch", hide_index=True)

# Atualiza o contador de uso depois de eventuais chamadas à IA nesta execução
if limite_ativo:
    contador_uso.caption(f"Uso da IA nesta sessão: {st.session_state.uso_ia}/{LIMITE_IA}")
