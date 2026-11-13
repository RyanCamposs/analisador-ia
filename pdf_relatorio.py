"""Exporta o resumo executivo (e o relatório da IA, se houver) em PDF."""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sem janela; só gera imagens
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import pandas as pd  # noqa: E402
from fpdf import FPDF, FontFace  # noqa: E402

import analise as an  # noqa: E402

# Cores (mesmas da tela)
MARINHO = (15, 27, 45)
AZUL = (28, 92, 171)
AZUL_CLARO = (127, 176, 238)
TINTA = (15, 27, 45)
TINTA_2 = (91, 101, 119)
BORDA = (227, 230, 235)
FUNDO = (245, 246, 248)
ETIQUETAS = {
    "Destaque": ((227, 238, 251), (24, 79, 149)),
    "Qualidade": ((255, 244, 220), (138, 90, 0)),
    "Padrão": ((238, 240, 243), (61, 71, 89)),
}

_FONTES = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
_EMOJI = re.compile("[\U00010000-\U0010FFFF☀-➿️‍⃣⬀-⯿]")


def _limpar(texto: str) -> str:
    return _EMOJI.sub("", str(texto))


# ---------------------------------------------------------------------------
# Gráficos estáticos (matplotlib) no mesmo estilo da tela
# ---------------------------------------------------------------------------

def _estilo(ax) -> None:
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color("#e3e6eb")
    ax.tick_params(colors="#5b6577", labelsize=8, length=0)
    ax.yaxis.grid(True, color="#e8ebf0", linestyle=(0, (1, 2)))
    ax.set_axisbelow(True)


def _png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _grafico_tempo(df: pd.DataFrame, col_data: str, metrica: str | None) -> io.BytesIO | None:
    s = df.dropna(subset=[col_data]).set_index(col_data).sort_index()
    if s.empty:
        return None
    dados = s[metrica].resample("MS").sum() if metrica else s.resample("MS").size()
    if len(dados) < 2:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.plot(dados.index, dados.values, color="#2a78d6", linewidth=1.8, marker="o", markersize=4,
            markeredgecolor="white", markeredgewidth=1)
    ax.fill_between(dados.index, dados.values, color="#2a78d6", alpha=0.08)
    ax.set_xticks(dados.index)
    ax.set_xticklabels([f"{an.MESES[d.month - 1]}/{str(d.year)[2:]}" for d in dados.index], fontsize=7.5)
    if len(dados) > 14:
        for i, rot in enumerate(ax.get_xticklabels()):
            rot.set_visible(i % max(1, len(dados) // 12) == 0)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: an.formatar_numero(v)))
    ax.set_ylim(bottom=0)
    _estilo(ax)
    return _png(fig)


def _grafico_ranking(df: pd.DataFrame, col: str, metrica: str | None, top: int = 8) -> io.BytesIO:
    dados = (df.groupby(col)[metrica].sum() if metrica else df[col].value_counts())
    dados = dados.sort_values(ascending=False).head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(3.6, 0.32 * len(dados) + 0.5))
    barras = ax.barh([str(i) for i in dados.index], dados.values, color="#2a78d6", height=0.62)
    maximo = float(dados.max()) or 1
    for b, v in zip(barras, dados.values):
        ax.text(b.get_width() + maximo * 0.02, b.get_y() + b.get_height() / 2, an.formatar_numero(v),
                va="center", fontsize=7.5, color="#5b6577")
    ax.set_xlim(0, maximo * 1.22)
    ax.set_xticks([])
    _estilo(ax)
    ax.yaxis.grid(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", labelsize=8, colors="#28334a")
    return _png(fig)


# ---------------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------------

class _PDF(FPDF):
    rodape = ""

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", size=7)
        self.set_text_color(*TINTA_2)
        self.cell(0, 5, self.rodape, align="L")
        self.set_x(self.l_margin)
        self.cell(0, 5, f"Página {self.page_no()} de {{nb}}", align="R")


def _secao(pdf: FPDF, titulo: str) -> None:
    pdf.ln(4)
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*TINTA_2)
    pdf.set_char_spacing(0.8)
    pdf.cell(pdf.get_string_width(titulo.upper()) + 3, 6, titulo.upper())
    pdf.set_char_spacing(0)
    y = pdf.get_y() + 3
    pdf.set_draw_color(*BORDA)
    pdf.set_line_width(0.2)
    pdf.line(pdf.get_x() + 1, y, pdf.w - pdf.r_margin, y)
    pdf.ln(8)


def _cabecalho(pdf: FPDF, titulo: str, nome: str, linhas: int, colunas: int) -> None:
    pdf.set_fill_color(*MARINHO)
    pdf.rect(0, 0, pdf.w, 34, style="F")
    pdf.set_xy(pdf.l_margin, 9)
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*AZUL_CLARO)
    pdf.set_char_spacing(1)
    pdf.cell(0, 4, "RELATÓRIO DE ANÁLISE")
    pdf.set_char_spacing(0)
    pdf.set_xy(pdf.l_margin, 14)
    pdf.set_font("DejaVu", "B", 19)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(110, 10, _limpar(titulo)[:48])
    pdf.set_font("DejaVu", size=7.5)
    pdf.set_text_color(200, 210, 225)
    meta = [nome[:60], f"{an.formatar_numero(linhas)} registros · {colunas} colunas",
            f"Gerado em {datetime.now():%d/%m/%Y às %H:%M}"]
    for i, linha in enumerate(meta):
        pdf.set_xy(pdf.w - pdf.r_margin - 75, 11 + i * 4.5)
        pdf.cell(75, 4, linha, align="R")
    pdf.set_y(42)


def _kpis(pdf: FPDF, kpis: list[tuple[str, str, str]]) -> None:
    if not kpis:
        return
    gap = 3
    largura = (pdf.epw - gap * (len(kpis) - 1)) / len(kpis)
    altura, x0, y0 = 25, pdf.l_margin, pdf.get_y()
    for i, (rot, val, sub) in enumerate(kpis):
        x = x0 + i * (largura + gap)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(*BORDA)
        pdf.set_line_width(0.2)
        pdf.rect(x, y0, largura, altura, style="DF")
        pdf.set_fill_color(*AZUL)
        pdf.rect(x, y0, largura, 0.9, style="F")
        interno = largura - 6

        pdf.set_xy(x + 3, y0 + 3.5)
        pdf.set_font("DejaVu", "B", 6)
        pdf.set_text_color(*TINTA_2)
        rot = _limpar(rot).upper()
        while pdf.get_string_width(rot) > interno and len(rot) > 4:
            rot = rot[:-2] + "…"
        pdf.cell(interno, 3, rot)

        tamanho = 14.0
        pdf.set_font("DejaVu", "B", tamanho)
        val = _limpar(val)
        while pdf.get_string_width(val) > interno and tamanho > 8:
            tamanho -= 0.5
            pdf.set_font("DejaVu", "B", tamanho)
        pdf.set_xy(x + 3, y0 + 9)
        pdf.set_text_color(*TINTA)
        pdf.cell(interno, 6, val)

        pdf.set_xy(x + 3, y0 + 17)
        pdf.set_font("DejaVu", size=6.2)
        pdf.set_text_color(*TINTA_2)
        pdf.multi_cell(interno, 2.8, _limpar(sub), align="L")
    pdf.set_y(y0 + altura + 2)


def _altura_cartao(img: io.BytesIO, w: float) -> float:
    from PIL import Image

    img.seek(0)
    larg_px, alt_px = Image.open(img).size
    img.seek(0)
    return (w - 6) * alt_px / larg_px + 13


def _imagem_em_cartao(pdf: FPDF, img: io.BytesIO, titulo: str, x: float, y: float, w: float,
                      h: float | None = None) -> float:
    """Desenha um cartão com título e imagem; retorna a altura usada."""
    h = h or _altura_cartao(img, w)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(*BORDA)
    pdf.rect(x, y, w, h, style="DF")
    pdf.set_xy(x + 3, y + 3)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*TINTA)
    pdf.cell(w - 6, 5, _limpar(titulo)[:70])
    pdf.image(img, x=x + 3, y=y + 10, w=w - 6)
    return h


def _achados(pdf: FPDF, achados: list[tuple[str, str]]) -> None:
    ordem = {"Destaque": 0, "Qualidade": 1, "Padrão": 2}
    for cat, texto in sorted(achados, key=lambda a: ordem.get(a[0], 3)):
        if pdf.get_y() > pdf.h - 30:
            pdf.add_page()
        fundo, cor = ETIQUETAS.get(cat, ETIQUETAS["Padrão"])
        y = pdf.get_y()
        pdf.set_font("DejaVu", "B", 6)
        pdf.set_fill_color(*fundo)
        pdf.set_text_color(*cor)
        pdf.set_xy(pdf.l_margin, y + 0.6)
        pdf.cell(20, 4.4, cat.upper(), align="C", fill=True)
        pdf.set_xy(pdf.l_margin + 23, y)
        pdf.set_font("DejaVu", size=8.5)
        pdf.set_text_color(40, 51, 74)
        texto_md = re.sub(r"</?b>", "**", _limpar(texto))
        pdf.multi_cell(pdf.epw - 23, 5.2, texto_md, markdown=True)
        pdf.ln(1.6)


def _inline(texto: str) -> str:
    """Converte markdown em linha para a sintaxe do fpdf (**negrito**, __itálico__)."""
    t = _limpar(texto)
    t = re.sub(r"<br\s*/?>", " ", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)          # links -> texto
    t = t.replace("`", "")
    t = t.replace("--", "–").replace("__", "")              # evita marcações acidentais
    t = re.sub(r"(?<![*\w])\*(?!\s)([^*\n]+?)\*(?!\*)", r"__\1__", t)  # *itálico*
    return t


def _tabela_md(pdf: FPDF, linhas: list[str]) -> None:
    def celulas(linha: str) -> list[str]:
        return [c.strip() for c in linha.strip().strip("|").split("|")]

    corpo = [celulas(l) for l in linhas if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", l)]
    if not corpo:
        return
    n = max(len(r) for r in corpo)
    corpo = [r + [""] * (n - len(r)) for r in corpo]
    pdf.set_font("DejaVu", size=8)
    pdf.set_text_color(40, 51, 74)
    pdf.set_draw_color(*BORDA)
    cabec = FontFace(family="DejaVu", emphasis="B", color=TINTA, fill_color=(238, 242, 248), size_pt=8)
    # Largura de cada coluna proporcional ao texto mais longo (com mínimo e máximo)
    larguras = tuple(min(max(max(len(r[j]) for r in corpo), 12), 60) for j in range(n))
    with pdf.table(text_align="LEFT", line_height=4.4, padding=1.6, markdown=True, headings_style=cabec,
                   borders_layout="HORIZONTAL_LINES", width=pdf.epw, col_widths=larguras) as tabela:
        for r in corpo:
            linha = tabela.row()
            for c in r:
                linha.cell(_inline(c))
    pdf.ln(3)


def _relatorio_ia(pdf: FPDF, texto: str) -> None:
    if pdf.get_y() > pdf.h - 90:
        pdf.add_page()
    _secao(pdf, "Relatório analítico da IA")
    linhas = _limpar(texto).splitlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i].rstrip()
        bruto = linha.strip()

        if bruto.startswith("|"):  # tabela: junta as linhas consecutivas
            bloco = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                bloco.append(linhas[i])
                i += 1
            try:
                _tabela_md(pdf, bloco)
            except Exception:  # noqa: BLE001 - tabela malformada vira texto
                pdf.set_font("DejaVu", size=8.5)
                for b in bloco:
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(pdf.epw, 4.6, _inline(b.replace("|", "  ")), markdown=True, align="L")
            continue

        i += 1
        if not bruto or re.fullmatch(r"[-*_]{3,}", bruto):
            pdf.ln(1.5)
            continue

        titulo = re.match(r"^(#{1,6})\s+(.*)", bruto)
        if titulo:
            nivel = len(titulo.group(1))
            tam, cor = {1: (13.5, TINTA), 2: (11.5, AZUL), 3: (10, TINTA)}.get(nivel, (9.5, TINTA))
            if pdf.get_y() > pdf.h - 40:
                pdf.add_page()
            pdf.ln(2.5 if nivel <= 2 else 1.5)
            pdf.set_font("DejaVu", "B", tam)
            pdf.set_text_color(*cor)
            pdf.multi_cell(0, tam * 0.5, _inline(titulo.group(2)).replace("**", "").replace("__", ""),
                           align="L")
            pdf.ln(1.2)
            continue

        pdf.set_font("DejaVu", size=9)
        pdf.set_text_color(40, 51, 74)
        item = re.match(r"^(\s*)([-*+•]|\d+[.)])\s+(.*)", linha)
        if item:
            recuo = 4 + min(len(item.group(1)) // 2, 3) * 4
            marcador = item.group(2) if item.group(2)[0].isdigit() else "•"
            pdf.set_x(pdf.l_margin + recuo)
            pdf.cell(5, 5, marcador)
            pdf.multi_cell(pdf.epw - recuo - 5, 5, _inline(item.group(3)), markdown=True, align="L")
            pdf.ln(0.6)
            continue

        if bruto.startswith(">"):
            pdf.set_text_color(*TINTA_2)
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(pdf.epw - 4, 5, "__" + _inline(bruto.lstrip("> ")) + "__", markdown=True,
                           align="L")
            pdf.ln(1)
            continue

        pdf.multi_cell(0, 5, _inline(bruto), markdown=True, align="L")
        pdf.ln(1.2)


def gerar_pdf(df: pd.DataFrame, nome_arquivo: str, titulo: str, metrica: str | None,
              relatorio_ia: str | None = None) -> bytes:
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_font("DejaVu", "", _FONTES / "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "B", _FONTES / "DejaVuSans-Bold.ttf")
    pdf.add_font("DejaVu", "I", _FONTES / "DejaVuSans-Oblique.ttf")
    pdf.add_font("DejaVu", "BI", _FONTES / "DejaVuSans-BoldOblique.ttf")
    pdf.rodape = "Analisador de Dados com IA  ·  " + nome_arquivo[:70]
    pdf.set_title(f"Relatório de análise — {titulo}")
    pdf.add_page()

    tipos = an.classificar_colunas(df)
    datas, cat = tipos["data"], tipos["categorica"]

    _cabecalho(pdf, titulo, nome_arquivo, len(df), df.shape[1])
    _secao(pdf, "Indicadores-chave")
    _kpis(pdf, an.indicadores_chave(df, metrica))

    # Gráficos
    graficos: list[tuple[str, io.BytesIO]] = []
    if datas:
        img = _grafico_tempo(df, datas[0], metrica)
        if img:
            graficos.append((f"{metrica or 'Registros'} por mês", img))
    rankings = [(f"{metrica or 'Registros'} por {c}", _grafico_ranking(df, c, metrica)) for c in cat[:2]]

    if graficos or rankings:
        _secao(pdf, "Desempenho")
        for titulo_g, img in graficos:
            pdf.set_y(pdf.get_y() + _imagem_em_cartao(pdf, img, titulo_g, pdf.l_margin, pdf.get_y(), pdf.epw) + 3)
        if rankings:
            larg = (pdf.epw - 4) / 2 if len(rankings) > 1 else pdf.epw * 0.6
            y = pdf.get_y()
            if y > pdf.h - 80:
                pdf.add_page()
                y = pdf.get_y()
            altura = max(_altura_cartao(img, larg) for _, img in rankings)
            for i, (t, img) in enumerate(rankings):
                _imagem_em_cartao(pdf, img, t, pdf.l_margin + i * (larg + 4), y, larg, altura)
            pdf.set_y(y + altura + 3)

    if pdf.get_y() > pdf.h - 50:
        pdf.add_page()
    _secao(pdf, "Achados automáticos")
    _achados(pdf, an.insights_automaticos(df))

    if relatorio_ia:
        _relatorio_ia(pdf, relatorio_ia)

    return bytes(pdf.output())
