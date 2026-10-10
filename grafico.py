import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# 1. Carregar os dados
caminho_arquivo = "covid_bairro_ano_tratado.csv"
df = pd.read_csv(caminho_arquivo)

# Configuração do estilo visual
plt.style.use("seaborn-v0_8-whitegrid")
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# -----------------------------------------------------------------------------
# Gráfico 1: Evolução da Taxa Geral de Letalidade (%) por Ano
# -----------------------------------------------------------------------------
df_ano = (
    df.groupby("Ano")
    .agg(Casos=("Casos", "sum"), Obitos=("Obitos", "sum"))
    .reset_index()
)
df_ano["Letalidade_%"] = (df_ano["Obitos"] / df_ano["Casos"]) * 100

sns.barplot(
    data=df_ano, x="Ano", y="Letalidade_%", ax=axes[0, 0], palette="Blues_d"
)
axes[0, 0].set_title(
    "1. Taxa Geral de Letalidade (%) por Ano em Fortaleza",
    fontsize=12,
    fontweight="bold",
)
axes[0, 0].set_ylabel("Letalidade (%)")
axes[0, 0].set_xlabel("Ano")

# Adicionar rótulos de porcentagem nas barras
for p in axes[0, 0].patches:
    axes[0, 0].annotate(
        f"{p.get_height():.2f}%",
        (p.get_x() + p.get_width() / 2.0, p.get_height()),
        ha="center",
        va="center",
        xytext=(0, 6),
        textcoords="offset points",
        fontweight="bold",
    )

# -----------------------------------------------------------------------------
# Gráfico 2: Top 10 Bairros com Maior Taxa de Letalidade Acumulada (%)
# -----------------------------------------------------------------------------
df_bairro = (
    df.groupby("Bairro")
    .agg(Total_Casos=("Casos", "sum"), Total_Obitos=("Obitos", "sum"))
    .reset_index()
)
df_bairro["Letalidade_%"] = (
    df_bairro["Total_Obitos"] / df_bairro["Total_Casos"]
) * 100
top10_letalidade = df_bairro.sort_values(
    "Letalidade_%", ascending=False
).head(10)

sns.barplot(
    data=top10_letalidade,
    y="Bairro",
    x="Letalidade_%",
    ax=axes[0, 1],
    palette="Reds_r",
)
axes[0, 1].set_title(
    "2. Top 10 Bairros com Maior Taxa de Letalidade Acumulada (%)",
    fontsize=12,
    fontweight="bold",
)
axes[0, 1].set_xlabel("Letalidade Acumulada (%)")
axes[0, 1].set_ylabel("Bairro")

for p in axes[0, 1].patches:
    axes[0, 1].annotate(
        f"{p.get_width():.2f}%",
        (p.get_width(), p.get_y() + p.get_height() / 2.0),
        ha="left",
        va="center",
        xytext=(5, 0),
        textcoords="offset points",
        fontweight="bold",
    )

# -----------------------------------------------------------------------------
# Gráfico 3: Variação Percentual Média Ano a Ano (YoY) dos Casos (%)
# -----------------------------------------------------------------------------
df_var = (
    df.dropna(subset=["Var_%_Casos_YoY"])
    .groupby("Ano")["Var_%_Casos_YoY"]
    .mean()
    .reset_index()
)

sns.barplot(
    data=df_var, x="Ano", y="Var_%_Casos_YoY", ax=axes[1, 0], palette="PuOr"
)
axes[1, 0].set_title(
    "3. Variação Percentual Média Ano a Ano (YoY) dos Casos (%)",
    fontsize=12,
    fontweight="bold",
)
axes[1, 0].set_ylabel("Variação Média (%)")
axes[1, 0].set_xlabel("Ano")
axes[1, 0].axhline(0, color="black", linewidth=0.8, linestyle="--")

for p in axes[1, 0].patches:
    val = p.get_height()
    axes[1, 0].annotate(
        f"{val:.1f}%",
        (p.get_x() + p.get_width() / 2.0, val),
        ha="center",
        va="center",
        xytext=(0, 6 if val >= 0 else -12),
        textcoords="offset points",
        fontweight="bold",
    )

# -----------------------------------------------------------------------------
# Gráfico 4: Concentração de Óbitos (%) - Top 10 Bairros
# -----------------------------------------------------------------------------
df_bairro["Concentracao_Obitos_%"] = (
    df_bairro["Total_Obitos"] / df_bairro["Total_Obitos"].sum()
) * 100
top10_obitos = df_bairro.sort_values(
    "Concentracao_Obitos_%", ascending=False
).head(10)

sns.barplot(
    data=top10_obitos,
    y="Bairro",
    x="Concentracao_Obitos_%",
    ax=axes[1, 1],
    palette="YlOrRd_r",
)
axes[1, 1].set_title(
    "4. Concentração do Total de Óbitos (%) - Top 10 Bairros",
    fontsize=12,
    fontweight="bold",
)
axes[1, 1].set_xlabel("% em Relação ao Total de Óbitos da Cidade")
axes[1, 1].set_ylabel("Bairro")

for p in axes[1, 1].patches:
    axes[1, 1].annotate(
        f"{p.get_width():.2f}%",
        (p.get_width(), p.get_y() + p.get_height() / 2.0),
        ha="left",
        va="center",
        xytext=(5, 0),
        textcoords="offset points",
        fontweight="bold",
    )

# Ajuste de layout e salvamento
plt.tight_layout()
plt.savefig("graficos_porcentagem_covid.png", dpi=300)
plt.show()