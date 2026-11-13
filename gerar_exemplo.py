"""Gera uma base de vendas fictícia (exemplo_vendas.xlsx) para testar o sistema."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
n = 600
produtos = {"Notebook": 3500, "Mouse": 80, "Teclado": 150, "Monitor": 1200, "Headset": 300, "Webcam": 250}
nomes = rng.choice(list(produtos), n, p=[0.1, 0.25, 0.2, 0.12, 0.18, 0.15])
qtd = rng.integers(1, 6, n)
preco = np.array([produtos[p] for p in nomes]) * rng.normal(1, 0.08, n)
df = pd.DataFrame({
    "Data": pd.to_datetime("2025-01-01") + pd.to_timedelta(rng.integers(0, 365, n), unit="D"),
    "Região": rng.choice(["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte"], n, p=[0.45, 0.2, 0.18, 0.1, 0.07]),
    "Vendedor": rng.choice(["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio"], n),
    "Produto": nomes,
    "Quantidade": qtd,
    "Preço Unitário": preco.round(2),
})
df["Faturamento"] = (df["Quantidade"] * df["Preço Unitário"]).round(2)
df["Desconto (%)"] = rng.choice([0, 5, 10, 15], n, p=[0.5, 0.25, 0.15, 0.1])
df.loc[rng.choice(n, 25, replace=False), "Vendedor"] = np.nan  # alguns vazios para o teste
df = df.sort_values("Data").reset_index(drop=True)
df.to_excel("exemplo_vendas.xlsx", index=False)
print("exemplo_vendas.xlsx criado com", len(df), "linhas")
