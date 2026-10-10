import numpy as np
import pandas as pd


def processar_dados_covid(
    caminho_entrada: str,
    caminho_saida_csv: str = "covid_bairro_ano_tratado.csv",
    caminho_saida_excel: str = "covid_base_completa_powerbi.xlsx",
):
    """Processa a base de dados de COVID-19 por bairro e ano, gerando todas as
    métricas de evolução, letalidade, variação e ranking.
    """
    # -------------------------------------------------------------------------
    # 1. LEITURA E PADRONIZAÇÃO DOS DADOS
    # -------------------------------------------------------------------------
    if caminho_entrada.endswith(".csv"):
        df = pd.read_csv(caminho_entrada)
    else:
        df = pd.read_excel(caminho_entrada)

    # Padroniza nomes das colunas (remove espaços e ajusta maiúsculas)
    df.columns = df.columns.str.strip().str.title()

    # Mapeamento para garantir nomes padrão
    col_map = {
        "Bairro": "Bairro",
        "Ano": "Ano",
        "Casos": "Casos",
        "Obitos": "Obitos",
        "Óbitos": "Obitos",
    }
    df.rename(columns=col_map, inplace=True)

    # Tratamento de tipos e valores nulos
    df["Bairro"] = df["Bairro"].astype(str).str.strip().str.title()
    df["Ano"] = df["Ano"].astype(int)
    df["Casos"] = (
        pd.to_numeric(df["Casos"], errors="coerce").fillna(0).astype(int)
    )
    df["Obitos"] = (
        pd.to_numeric(df["Obitos"], errors="coerce").fillna(0).astype(int)
    )

    # Consolidação por Bairro e Ano (caso existam registros duplicados)
    df_fato = (
        df.groupby(["Bairro", "Ano"], as_index=False)[["Casos", "Obitos"]]
        .sum()
        .sort_values(["Bairro", "Ano"])
    )

    # -------------------------------------------------------------------------
    # 2. CÁLCULOS POR BAIRRO E ANO (TABELA FATO DETALHADA)
    # -------------------------------------------------------------------------
    # Percentual de Letalidade por Bairro em cada Ano
    df_fato["Letalidade_%"] = np.where(
        df_fato["Casos"] > 0,
        np.round((df_fato["Obitos"] / df_fato["Casos"]) * 100, 2),
        0.0,
    )

    # Casos e Óbitos do Ano Anterior (para cálculo de variação YoY)
    df_fato["Casos_Ano_Anterior"] = df_fato.groupby("Bairro")["Casos"].shift(1)
    df_fato["Obitos_Ano_Anterior"] = df_fato.groupby("Bairro")["Obitos"].shift(
        1
    )

    # Variação Absoluta de um Ano para o Outro
    df_fato["Var_Abs_Casos_YoY"] = (
        df_fato["Casos"] - df_fato["Casos_Ano_Anterior"]
    )
    df_fato["Var_Abs_Obitos_YoY"] = (
        df_fato["Obitos"] - df_fato["Obitos_Ano_Anterior"]
    )

    # Variação Percentual (%) de um Ano para o Outro
    df_fato["Var_%_Casos_YoY"] = np.where(
        df_fato["Casos_Ano_Anterior"] > 0,
        np.round(
            (df_fato["Var_Abs_Casos_YoY"] / df_fato["Casos_Ano_Anterior"])
            * 100,
            2,
        ),
        np.nan,
    )

    df_fato["Var_%_Obitos_YoY"] = np.where(
        df_fato["Obitos_Ano_Anterior"] > 0,
        np.round(
            (df_fato["Var_Abs_Obitos_YoY"] / df_fato["Obitos_Ano_Anterior"])
            * 100,
            2,
        ),
        np.nan,
    )

    # -------------------------------------------------------------------------
    # 3. CONSOLIDADO POR BAIRRO (DIMENSÃO BAIRRO)
    # -------------------------------------------------------------------------
    df_bairro = (
        df_fato.groupby("Bairro")
        .agg(
            Total_Casos=("Casos", "sum"),
            Total_Obitos=("Obitos", "sum"),
            Media_Casos_Ano=("Casos", "mean"),
            Media_Obitos_Ano=("Obitos", "mean"),
            Anos_Monitorados=("Ano", "nunique"),
        )
        .reset_index()
    )

    # Letalidade acumulada por Bairro
    df_bairro["Letalidade_Geral_%"] = np.where(
        df_bairro["Total_Casos"] > 0,
        np.round(
            (df_bairro["Total_Obitos"] / df_bairro["Total_Casos"]) * 100, 2
        ),
        0.0,
    )

    # Arredondamento das médias
    df_bairro["Media_Casos_Ano"] = df_bairro["Media_Casos_Ano"].round(2)
    df_bairro["Media_Obitos_Ano"] = df_bairro["Media_Obitos_Ano"].round(2)

    # Concentração (% em relação ao município/total geral)
    total_geral_casos = df_bairro["Total_Casos"].sum()
    total_geral_obitos = df_bairro["Total_Obitos"].sum()

    df_bairro["%_Concentracao_Casos"] = np.round(
        (df_bairro["Total_Casos"] / total_geral_casos) * 100, 2
    )
    df_bairro["%_Concentracao_Obitos"] = np.round(
        (df_bairro["Total_Obitos"] / total_geral_obitos) * 100, 2
    )

    # Rankings
    df_bairro["Rank_Casos"] = (
        df_bairro["Total_Casos"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    df_bairro["Rank_Obitos"] = (
        df_bairro["Total_Obitos"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    df_bairro["Rank_Letalidade"] = (
        df_bairro["Letalidade_Geral_%"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    # -------------------------------------------------------------------------
    # 4. EVOLUÇÃO GERAL POR ANO (DIMENSÃO ANO)
    # -------------------------------------------------------------------------
    df_ano = (
        df_fato.groupby("Ano")
        .agg(
            Total_Casos=("Casos", "sum"),
            Total_Obitos=("Obitos", "sum"),
            Bairros_Com_Registros=("Bairro", "nunique"),
        )
        .reset_index()
        .sort_values("Ano")
    )

    df_ano["Letalidade_Geral_%"] = np.where(
        df_ano["Total_Casos"] > 0,
        np.round((df_ano["Total_Obitos"] / df_ano["Total_Casos"]) * 100, 2),
        0.0,
    )

    # Variação temporal global
    df_ano["Var_Abs_Casos"] = df_ano["Total_Casos"].diff()
    df_ano["Var_%_Casos"] = (df_ano["Total_Casos"].pct_change() * 100).round(2)

    df_ano["Var_Abs_Obitos"] = df_ano["Total_Obitos"].diff()
    df_ano["Var_%_Obitos"] = (
        df_ano["Total_Obitos"].pct_change() * 100
    ).round(2)

    # -------------------------------------------------------------------------
    # 5. EXPORTAÇÃO DOS DADOS
    # -------------------------------------------------------------------------
    df_fato.to_csv(caminho_saida_csv, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(caminho_saida_excel, engine="openpyxl") as writer:
        df_fato.to_excel(
            writer, sheet_name="Base_Bairro_Ano_Fato", index=False
        )
        df_bairro.to_excel(
            writer, sheet_name="Resumo_Por_Bairro", index=False
        )
        df_ano.to_excel(writer, sheet_name="Resumo_Por_Ano", index=False)

    print("Processamento concluído com sucesso!")
    print(f"-> CSV gerado: {caminho_saida_csv}")
    print(f"-> Excel gerado com 3 abas: {caminho_saida_excel}")

    return df_fato, df_bairro, df_ano


# =============================================================================
# EXEMPLO DE EXECUÇÃO
# =============================================================================
if __name__ == "__main__":
    # COLOQUE AQUI O NOME EXATO DO SEU FICHEIRO CSV OU EXCEL
    arquivo_original = "covid_fortaleza_bairros_2020_2024.csv"
    # Executa a função
    df_fato, df_bairro, df_ano = processar_dados_covid(arquivo_original)