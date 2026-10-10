"""
COVID-19 em Fortaleza (2020-2024): tratamento, gráficos e mapa por bairro.

Uso (uma linha):
    python covid_fortaleza_bi.py

Opções úteis:
    python covid_fortaleza_bi.py --csv meu_arquivo.csv --saida resultados
    python covid_fortaleza_bi.py --ano 2021                 # mapa de um ano só
    python covid_fortaleza_bi.py --geojson bairros.geojson  # limites locais
    python covid_fortaleza_bi.py --abrir                    # abre os mapas no navegador

Dependências:
    pip install pandas numpy matplotlib openpyxl geopandas folium

Saídas (pasta --saida, padrão "saida/"):
    covid_bairro_ano_tratado.csv        -> tabela fato
    covid_base_completa_powerbi.xlsx    -> abas fato / bairro / ano / regional
    graficos/*.png                      -> gráficos de casos, óbitos, letalidade...
    mapas/mapa_estatico.png             -> mapa de preenchimento (casos e óbitos)
    mapas/mapa_casos.html               -> mapa interativo de casos
    mapas/mapa_obitos.html              -> mapa interativo de óbitos
    mapas/mapa_pixel.png + mapa_pixel_*.html -> mapa em pixels (--pixels 60)
"""

from __future__ import annotations

import argparse
import difflib
import re
import unicodedata
import webbrowser
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import PowerNorm
from matplotlib.ticker import FuncFormatter

# Limites dos bairros de Fortaleza (GeoJSON público, propriedade com o nome: "NOME")
GEOJSON_URL = (
    "https://gist.githubusercontent.com/emanueles/f43681762385f250d533eabb35da6dac/"
    "raw/4d4541e92fb9ce69e692a7a3c291a4a538ae6b6a/FortalezaBairros.geojson"
)

# Nomes que diferem entre o CSV e o GeoJSON (chave normalizada -> chave normalizada)
ALIASES = {
    "joguei clube": "joquei clube",
    "pirambu": "pirambu",
}

# Fundo do mapa: Esri (sem chave de API; o OpenStreetMap bloqueia HTML aberto via arquivo local)
TILES_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
             "World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}")
TILES_ATTR = "Tiles &copy; Esri"

COR_CASOS = "#2a6f97"
COR_OBITOS = "#c1121f"


# =============================================================================
# UTILITÁRIOS
# =============================================================================
def normalizar(texto: str) -> str:
    """minúsculas, sem acento, sem pontuação: 'São Gerardo/Alagadiço' -> 'sao gerardo alagadico'."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", " ", texto.lower())
    return texto.strip()


def milhar(x, _pos=None) -> str:
    return f"{x:,.0f}".replace(",", ".")


# =============================================================================
# 1. TRATAMENTO
# =============================================================================
def processar_dados_covid(
    caminho_entrada: str,
    pasta_saida: Path,
    manter_anos_parciais: bool = False,
):
    """Lê o CSV, valida, calcula métricas e exporta CSV + Excel para o Power BI."""
    df = pd.read_csv(caminho_entrada)

    # Padroniza nomes de colunas (sem alterar o conteúdo dos nomes de bairro)
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={"cores": "regional", "óbitos": "obitos"})

    faltando = {"bairro", "ano", "casos", "obitos"} - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas obrigatórias ausentes no CSV: {sorted(faltando)}")
    if "regional" not in df.columns:
        df["regional"] = "N/D"

    df["bairro"] = df["bairro"].astype(str).str.strip()  # NÃO usar .str.title()
    df["regional"] = df["regional"].astype(str).str.strip()
    df["ano"] = df["ano"].astype(int)
    for col in ("casos", "obitos"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Valida em vez de preencher com 0 silenciosamente
    nulos = int(df[["casos", "obitos"]].isna().sum().sum())
    if nulos:
        print(f"[aviso] {nulos} valores nulos em casos/óbitos (mantidos como nulos).")
    inconsistentes = df[df["obitos"] > df["casos"]]
    if len(inconsistentes):
        print(f"[aviso] {len(inconsistentes)} linhas com óbitos > casos.")

    # Consolida duplicatas de bairro/ano (se existirem)
    fato = (
        df.groupby(["regional", "bairro", "ano"], as_index=False)[["casos", "obitos"]]
        .sum(min_count=1)
        .sort_values(["bairro", "ano"])
        .reset_index(drop=True)
    )
    fato = fato.rename(
        columns={"regional": "Regional", "bairro": "Bairro", "ano": "Ano",
                 "casos": "Casos", "obitos": "Obitos"}
    )

    # Letalidade: nula (e não 0%) quando não há casos
    fato["Letalidade_Pct"] = np.where(
        fato["Casos"] > 0, (fato["Obitos"] / fato["Casos"] * 100).round(2), np.nan
    )

    # Variação ano a ano por bairro
    for col in ("Casos", "Obitos"):
        ant = fato.groupby("Bairro")[col].shift(1)
        fato[f"{col}_Ano_Anterior"] = ant
        fato[f"Var_Abs_{col}_YoY"] = fato[col] - ant
        fato[f"Var_Pct_{col}_YoY"] = np.where(
            ant > 0, ((fato[col] - ant) / ant * 100).round(2), np.nan
        )

    # ---- Dimensão Ano -------------------------------------------------------
    df_ano = (
        fato.groupby("Ano")
        .agg(Total_Casos=("Casos", "sum"), Total_Obitos=("Obitos", "sum"),
             Bairros_Com_Casos=("Casos", lambda s: int((s > 0).sum())))
        .reset_index()
        .sort_values("Ano")
    )
    df_ano["Letalidade_Geral_Pct"] = np.where(
        df_ano["Total_Casos"] > 0,
        (df_ano["Total_Obitos"] / df_ano["Total_Casos"] * 100).round(2), np.nan,
    )
    for col in ("Casos", "Obitos"):
        df_ano[f"Var_Abs_{col}"] = df_ano[f"Total_{col}"].diff()
        df_ano[f"Var_Pct_{col}"] = (df_ano[f"Total_{col}"].pct_change() * 100).round(2)

    # Anos praticamente vazios (ex.: 2024 com 4 casos) distorcem médias
    limiar = 0.01 * df_ano["Total_Casos"].max()
    anos_parciais = df_ano.loc[df_ano["Total_Casos"] < limiar, "Ano"].tolist()
    df_ano["Ano_Parcial"] = df_ano["Ano"].isin(anos_parciais)
    anos_media = (
        df_ano["Ano"].tolist() if manter_anos_parciais
        else df_ano.loc[~df_ano["Ano_Parcial"], "Ano"].tolist()
    )
    if anos_parciais:
        acao = "mantidos" if manter_anos_parciais else "excluídos das médias"
        print(f"[aviso] Ano(s) com dados quase inexistentes: {anos_parciais} ({acao}). "
              "Verifique se é ausência de notificação, não ausência de casos.")

    # ---- Dimensão Bairro ----------------------------------------------------
    base_media = fato[fato["Ano"].isin(anos_media)]
    df_bairro = (
        fato.groupby(["Regional", "Bairro"])
        .agg(Total_Casos=("Casos", "sum"), Total_Obitos=("Obitos", "sum"))
        .reset_index()
    )
    medias = (
        base_media.groupby("Bairro")
        .agg(Media_Casos_Ano=("Casos", "mean"), Media_Obitos_Ano=("Obitos", "mean"))
        .round(2).reset_index()
    )
    pico = fato.loc[fato.groupby("Bairro")["Casos"].idxmax(), ["Bairro", "Ano"]]
    pico = pico.rename(columns={"Ano": "Ano_Pico_Casos"})
    df_bairro = df_bairro.merge(medias, on="Bairro").merge(pico, on="Bairro")

    df_bairro["Letalidade_Geral_Pct"] = np.where(
        df_bairro["Total_Casos"] > 0,
        (df_bairro["Total_Obitos"] / df_bairro["Total_Casos"] * 100).round(2), np.nan,
    )
    for col in ("Casos", "Obitos"):
        total = df_bairro[f"Total_{col}"].sum()
        df_bairro[f"Concentracao_{col}_Pct"] = (df_bairro[f"Total_{col}"] / total * 100).round(2)
        df_bairro[f"Rank_{col}"] = df_bairro[f"Total_{col}"].rank(ascending=False, method="min").astype(int)
    df_bairro["Rank_Letalidade"] = (
        df_bairro["Letalidade_Geral_Pct"].rank(ascending=False, method="min")
    )

    # ---- Dimensão Regional --------------------------------------------------
    df_regional = (
        fato.groupby("Regional")
        .agg(Bairros=("Bairro", "nunique"), Total_Casos=("Casos", "sum"),
             Total_Obitos=("Obitos", "sum"))
        .reset_index()
    )
    df_regional["Letalidade_Geral_Pct"] = (
        df_regional["Total_Obitos"] / df_regional["Total_Casos"] * 100
    ).round(2)

    # ---- Exportação ---------------------------------------------------------
    pasta_saida.mkdir(parents=True, exist_ok=True)
    csv_saida = pasta_saida / "covid_bairro_ano_tratado.csv"
    xlsx_saida = pasta_saida / "covid_base_completa_powerbi.xlsx"
    fato.to_csv(csv_saida, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_saida, engine="openpyxl") as writer:
        fato.to_excel(writer, sheet_name="Base_Bairro_Ano_Fato", index=False)
        df_bairro.to_excel(writer, sheet_name="Resumo_Por_Bairro", index=False)
        df_ano.to_excel(writer, sheet_name="Resumo_Por_Ano", index=False)
        df_regional.to_excel(writer, sheet_name="Resumo_Por_Regional", index=False)
    print(f"[ok] Tratamento concluído -> {csv_saida.name}, {xlsx_saida.name}")
    return fato, df_bairro, df_ano, df_regional


# =============================================================================
# 2. GRÁFICOS
# =============================================================================
def _barras_rotuladas(ax, x, y, cor, titulo, parciais=()):
    barras = ax.bar(x.astype(str), y, color=cor)
    ax.set_title(titulo, fontweight="bold")
    ax.yaxis.set_major_formatter(FuncFormatter(milhar))
    ax.spines[["top", "right"]].set_visible(False)
    for b, ano, v in zip(barras, x, y):
        ax.annotate(milhar(v) + ("*" if ano in parciais else ""),
                    (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=9, xytext=(0, 2),
                    textcoords="offset points")


def gerar_graficos(fato, df_bairro, df_ano, df_regional, pasta_saida: Path):
    pasta = pasta_saida / "graficos"
    pasta.mkdir(parents=True, exist_ok=True)
    parciais = df_ano.loc[df_ano["Ano_Parcial"], "Ano"].tolist()
    nota = "* ano com dados praticamente vazios" if parciais else ""

    # 1) Casos e óbitos por ano
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
    _barras_rotuladas(axs[0], df_ano["Ano"], df_ano["Total_Casos"], COR_CASOS,
                      "Casos confirmados por ano", parciais)
    _barras_rotuladas(axs[1], df_ano["Ano"], df_ano["Total_Obitos"], COR_OBITOS,
                      "Óbitos por ano", parciais)
    if nota:
        fig.text(0.01, 0.01, nota, fontsize=8, color="gray")
    fig.suptitle("COVID-19 em Fortaleza - evolução anual", fontsize=13)
    fig.tight_layout()
    fig.savefig(pasta / "01_casos_obitos_por_ano.png", dpi=150)
    plt.close(fig)

    # 2) Letalidade por ano
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(df_ano["Ano"], df_ano["Letalidade_Geral_Pct"], marker="o", color=COR_OBITOS)
    for a, v in zip(df_ano["Ano"], df_ano["Letalidade_Geral_Pct"]):
        if pd.notna(v):
            ax.annotate(f"{v:.2f}%".replace(".", ","), (a, v), ha="center",
                        xytext=(0, 7), textcoords="offset points", fontsize=9)
    ax.set_xticks(df_ano["Ano"])
    ax.set_title("Letalidade geral por ano (óbitos / casos)", fontweight="bold")
    ax.set_ylabel("%")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(pasta / "02_letalidade_por_ano.png", dpi=150)
    plt.close(fig)

    # 3) Top 10 bairros: casos e óbitos
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, col, cor, tit in (
        (axs[0], "Total_Casos", COR_CASOS, "Top 10 bairros - casos"),
        (axs[1], "Total_Obitos", COR_OBITOS, "Top 10 bairros - óbitos"),
    ):
        top = df_bairro.nlargest(10, col).sort_values(col)
        ax.barh(top["Bairro"], top[col], color=cor)
        ax.xaxis.set_major_formatter(FuncFormatter(milhar))
        ax.set_title(tit, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
        for i, v in enumerate(top[col]):
            ax.text(v, i, " " + milhar(v), va="center", fontsize=9)
        ax.margins(x=0.12)
    fig.tight_layout()
    fig.savefig(pasta / "03_top10_bairros.png", dpi=150)
    plt.close(fig)

    # 4) Casos e óbitos por regional (CORES)
    if df_regional["Regional"].nunique() > 1:
        reg = df_regional.sort_values("Regional")
        fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
        _barras_rotuladas(axs[0], reg["Regional"], reg["Total_Casos"], COR_CASOS,
                          "Casos por regional (CORES)")
        _barras_rotuladas(axs[1], reg["Regional"], reg["Total_Obitos"], COR_OBITOS,
                          "Óbitos por regional (CORES)")
        fig.tight_layout()
        fig.savefig(pasta / "04_por_regional.png", dpi=150)
        plt.close(fig)

    # 5) Dispersão casos x óbitos por bairro
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df_bairro["Total_Casos"], df_bairro["Total_Obitos"],
               color=COR_OBITOS, alpha=0.6, edgecolor="white")
    for _, r in df_bairro.nlargest(8, "Total_Obitos").iterrows():
        ax.annotate(r["Bairro"], (r["Total_Casos"], r["Total_Obitos"]),
                    fontsize=8, xytext=(4, 3), textcoords="offset points")
    ax.xaxis.set_major_formatter(FuncFormatter(milhar))
    ax.set_xlabel("Total de casos")
    ax.set_ylabel("Total de óbitos")
    ax.set_title("Casos x óbitos por bairro (2020-2024)", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(pasta / "05_dispersao_casos_obitos.png", dpi=150)
    plt.close(fig)

    print(f"[ok] Gráficos salvos em {pasta}/")


# =============================================================================
# 3. MAPA DE PREENCHIMENTO (COROPLÉTICO)
# =============================================================================
def carregar_limites(origem: str, pasta_saida: Path, col_nome: str | None):
    import geopandas as gpd

    caminho = Path(origem)
    if origem.startswith("http"):
        caminho = pasta_saida / "fortaleza_bairros.geojson"
        if not caminho.exists():
            print("[info] Baixando limites dos bairros...")
            req = urllib.request.Request(origem, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                caminho.write_bytes(r.read())
    gdf = gpd.read_file(caminho)
    gdf = gdf.set_crs(4326) if gdf.crs is None else gdf.to_crs(4326)

    if col_nome is None:
        candidatas = ["NOME", "nome", "Nome", "NAME", "name", "BAIRRO", "bairro", "NM_BAIRRO"]
        col_nome = next((c for c in candidatas if c in gdf.columns), None)
        if col_nome is None:  # primeira coluna de texto
            col_nome = next(c for c in gdf.columns if c != "geometry" and gdf[c].dtype == object)
    print(f"[info] {len(gdf)} polígonos; coluna de nome = '{col_nome}'")
    gdf = gdf.rename(columns={col_nome: "Nome_Mapa"})
    gdf["chave"] = gdf["Nome_Mapa"].map(normalizar)
    return gdf[["Nome_Mapa", "chave", "geometry"]]


def casar_nomes(chaves_csv, chaves_geo) -> dict:
    """Associa cada bairro do CSV a um polígono (exato > alias > sem numeral romano > fuzzy)."""
    geo = set(chaves_geo)
    mapa = {}
    for k in chaves_csv:
        alvo = None
        if k in geo:
            alvo = k
        elif ALIASES.get(k) in geo:
            alvo = ALIASES[k]
        else:
            sem_romano = re.sub(r" (i|ii|iii|iv|v)$", "", k)  # Praia do Futuro I/II
            if sem_romano in geo:
                alvo = sem_romano
            else:
                m = difflib.get_close_matches(k, list(geo), n=1, cutoff=0.85)
                alvo = m[0] if m else None
        mapa[k] = alvo
    return mapa


def gerar_mapas(fato, gdf, pasta_saida: Path, ano: int | None, pixels: int = 60):
    import branca.colormap as cm
    import folium

    pasta = pasta_saida / "mapas"
    pasta.mkdir(parents=True, exist_ok=True)
    rotulo = f"{ano}" if ano else "2020-2024"

    base = fato if ano is None else fato[fato["Ano"] == ano]
    por_bairro = base.groupby("Bairro", as_index=False)[["Casos", "Obitos"]].sum()
    por_bairro["chave"] = por_bairro["Bairro"].map(normalizar)

    mapa = casar_nomes(por_bairro["chave"], gdf["chave"])
    por_bairro["chave_geo"] = por_bairro["chave"].map(mapa)

    sem_poligono = por_bairro.loc[por_bairro["chave_geo"].isna(), "Bairro"].tolist()
    usados = set(por_bairro["chave_geo"].dropna())
    sem_dado = gdf.loc[~gdf["chave"].isin(usados), "Nome_Mapa"].tolist()
    print(f"[mapa] {por_bairro['chave_geo'].notna().sum()}/{len(por_bairro)} bairros do CSV casaram com polígonos.")
    if sem_poligono:
        print(f"[mapa] CSV sem polígono ({len(sem_poligono)}): {sem_poligono}")
        print("       -> ajuste o dicionário ALIASES no topo do script se necessário.")
    if sem_dado:
        print(f"[mapa] Polígonos sem dado no CSV ({len(sem_dado)}): {sem_dado}")

    # Se vários bairros do CSV caem no mesmo polígono, somar
    agg = (por_bairro.dropna(subset=["chave_geo"])
           .groupby("chave_geo", as_index=False)[["Casos", "Obitos"]].sum())
    agg["Letalidade_Pct"] = np.where(agg["Casos"] > 0, agg["Obitos"] / agg["Casos"] * 100, np.nan)
    g = gdf.merge(agg, left_on="chave", right_on="chave_geo", how="left")

    # --- Mapa estático (casos + óbitos) --------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(15, 7.5))
    for ax, col, cmap, tit in (
        (axs[0], "Casos", "YlGnBu", f"Casos confirmados ({rotulo})"),
        (axs[1], "Obitos", "YlOrRd", f"Óbitos ({rotulo})"),
    ):
        vmax = max(g[col].max(), 1)
        g.plot(column=col, cmap=cmap, norm=PowerNorm(0.6, vmin=0, vmax=vmax), ax=ax,
               edgecolor="white", linewidth=0.4, legend=True,
               legend_kwds={"shrink": 0.6, "format": FuncFormatter(milhar)},
               missing_kwds={"color": "lightgray", "label": "sem dado"})
        for _, r in g.nlargest(5, col).iterrows():
            p = r.geometry.representative_point()
            ax.annotate(r["Nome_Mapa"], (p.x, p.y), fontsize=8, ha="center",
                        fontweight="bold", color="black",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", alpha=0.7, lw=0))
        ax.set_title(tit, fontweight="bold")
        ax.set_axis_off()
    fig.suptitle("Fortaleza - bairros mais afetados pela COVID-19 (top 5 rotulados)", fontsize=13)
    fig.tight_layout()
    fig.savefig(pasta / "mapa_estatico.png", dpi=150)
    plt.close(fig)

    # --- Mapas interativos (HTML) ---------------------------------------------
    g["Casos_txt"] = g["Casos"].map(lambda v: "sem dado" if pd.isna(v) else milhar(v))
    g["Obitos_txt"] = g["Obitos"].map(lambda v: "sem dado" if pd.isna(v) else milhar(v))
    g["Letal_txt"] = g["Letalidade_Pct"].map(
        lambda v: "-" if pd.isna(v) else f"{v:.2f}%".replace(".", ","))

    minx, miny, maxx, maxy = g.total_bounds
    centro = [(miny + maxy) / 2, (minx + maxx) / 2]
    for col, cores, nome in (
        ("Casos", ["#ffffcc", "#41b6c4", "#0c2c84"], "casos"),
        ("Obitos", ["#ffffb2", "#fd8d3c", "#800026"], "obitos"),
    ):
        vmax = float(g[col].quantile(0.95)) or 1.0  # evita que 1-2 outliers apaguem o resto
        escala = cm.LinearColormap(cores, vmin=0, vmax=vmax,
                                   caption=f"{col.replace('Obitos', 'Óbitos')} ({rotulo}) - escala até o percentil 95")
        m = folium.Map(location=centro, zoom_start=11, tiles=TILES_URL, attr=TILES_ATTR)
        folium.GeoJson(
            g[["Nome_Mapa", "Casos_txt", "Obitos_txt", "Letal_txt", col, "geometry"]],
            style_function=lambda f, c=col, e=escala: {
                "fillColor": "#d9d9d9" if pd.isna(f["properties"][c]) else e(min(f["properties"][c], e.vmax)),
                "color": "white", "weight": 0.6, "fillOpacity": 0.85,
            },
            highlight_function=lambda f: {"weight": 2, "color": "black"},
            tooltip=folium.GeoJsonTooltip(
                fields=["Nome_Mapa", "Casos_txt", "Obitos_txt", "Letal_txt"],
                aliases=["Bairro", "Casos", "Óbitos", "Letalidade"]),
        ).add_to(m)
        escala.add_to(m)
        m.save(pasta / f"mapa_{nome}.html")
    print(f"[ok] Mapas salvos em {pasta}/")
    gerar_mapa_pixel(g, pasta, rotulo, pixels)


def gerar_mapa_pixel(g, pasta: Path, rotulo: str, n_colunas: int = 60):
    """Mapa em 'pixels': grade regular; cada célula recebe o valor do bairro em que cai."""
    import branca.colormap as cm
    import folium
    import geopandas as gpd
    from shapely.geometry import Point

    minx, miny, maxx, maxy = g.total_bounds
    d = (maxx - minx) / n_colunas  # célula quadrada (em Fortaleza, ~3,8°S, grau lat ≈ grau lon)
    xs = np.arange(minx + d / 2, maxx, d)
    ys = np.arange(maxy - d / 2, miny, -d)  # de cima para baixo
    pontos = gpd.GeoDataFrame(
        geometry=[Point(x, y) for y in ys for x in xs], crs=g.crs)
    j = gpd.sjoin(pontos, g[["Casos", "Obitos", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()].sort_index()
    forma = (len(ys), len(xs))
    dentro = j["index_right"].notna().to_numpy().reshape(forma)

    fig, axs = plt.subplots(1, 2, figsize=(15, 7.5))
    for ax, col, nome, cmap_nome, cores in (
        (axs[0], "Casos", "casos", "YlGnBu", ["#ffffcc", "#41b6c4", "#0c2c84"]),
        (axs[1], "Obitos", "obitos", "YlOrRd", ["#ffffb2", "#fd8d3c", "#800026"]),
    ):
        arr = j[col].to_numpy(dtype=float).reshape(forma)
        vmax = max(np.nanmax(arr), 1)
        cmap = plt.get_cmap(cmap_nome).copy()
        cmap.set_bad("#d9d9d9")  # dentro de um bairro, mas sem dado
        # fora de Fortaleza = transparente; dentro sem dado = cinza
        rgba = cmap(PowerNorm(0.6, vmin=0, vmax=vmax)(np.nan_to_num(arr)))
        rgba[~dentro] = (1, 1, 1, 0)
        rgba[dentro & np.isnan(arr)] = (0.85, 0.85, 0.85, 1)
        ax.imshow(rgba, extent=(minx, maxx, miny, maxy), interpolation="nearest")
        sm = plt.cm.ScalarMappable(norm=PowerNorm(0.6, vmin=0, vmax=vmax), cmap=cmap_nome)
        fig.colorbar(sm, ax=ax, shrink=0.6, format=FuncFormatter(milhar))
        ax.set_title(f"{col.replace('Obitos', 'Óbitos')} - mapa em pixels ({rotulo})", fontweight="bold")
        ax.set_axis_off()

        # versão interativa sobre mapa-base
        escala = cm.LinearColormap(cores, vmin=0, vmax=vmax,
                                   caption=f"{col.replace('Obitos', 'Óbitos')} ({rotulo})")
        m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2],
                       zoom_start=11, tiles=TILES_URL, attr=TILES_ATTR)
        folium.raster_layers.ImageOverlay(
            image=rgba, bounds=[[miny, minx], [maxy, maxx]], opacity=0.75,
            mercator_project=True, class_name="pixelado").add_to(m)
        m.get_root().html.add_child(folium.Element(
            "<style>.pixelado{image-rendering:pixelated;image-rendering:crisp-edges;}</style>"))
        escala.add_to(m)
        m.save(pasta / f"mapa_pixel_{nome}.html")
    fig.suptitle(f"Fortaleza - intensidade por pixel ({n_colunas} colunas)", fontsize=13)
    fig.tight_layout()
    fig.savefig(pasta / "mapa_pixel.png", dpi=150)
    plt.close(fig)
    print(f"[ok] Mapa em pixels salvo em {pasta}/ (mapa_pixel.png, mapa_pixel_*.html)")


# =============================================================================
# EXECUÇÃO
# =============================================================================
def main():
    ap = argparse.ArgumentParser(description="COVID-19 Fortaleza: tratamento, gráficos e mapa.")
    ap.add_argument("--csv", default="covid_fortaleza_bairros_2020_2024.csv")
    ap.add_argument("--saida", default="saida")
    ap.add_argument("--geojson", default=GEOJSON_URL, help="caminho local ou URL do GeoJSON dos bairros")
    ap.add_argument("--col-nome", default=None, help="coluna do GeoJSON com o nome do bairro")
    ap.add_argument("--ano", type=int, default=None, help="filtra o mapa por um ano (padrão: todos)")
    ap.add_argument("--abrir", action="store_true",
                    help="abre os mapas no navegador ao terminar")
    ap.add_argument("--pixels", type=int, default=60,
                    help="colunas da grade do mapa em pixels (menor = mais pixelado)")
    ap.add_argument("--manter-anos-parciais", action="store_true",
                    help="inclui anos quase vazios (ex.: 2024) nas médias")
    args = ap.parse_args()

    saida = Path(args.saida)
    fato, df_bairro, df_ano, df_regional = processar_dados_covid(
        args.csv, saida, args.manter_anos_parciais)
    gerar_graficos(fato, df_bairro, df_ano, df_regional, saida)

    try:
        gdf = carregar_limites(args.geojson, saida, args.col_nome)
        gerar_mapas(fato, gdf, saida, args.ano, args.pixels)
        if args.abrir:
            for nome in ("mapa_pixel_casos.html", "mapa_pixel_obitos.html",
                         "mapa_casos.html", "mapa_obitos.html"):
                webbrowser.open((saida / "mapas" / nome).resolve().as_uri())
    except Exception as exc:  # o resto do pipeline já foi entregue
        print(f"[erro] Não foi possível gerar o mapa: {exc}")
        print("       Baixe o GeoJSON manualmente e rode com --geojson caminho/arquivo.geojson")


if __name__ == "__main__":
    main()
