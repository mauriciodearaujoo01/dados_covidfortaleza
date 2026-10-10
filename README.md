# Análise de Dados da COVID-19 por Bairros de Fortaleza

Este projeto em Python realiza a coleta, limpeza, análise exploratória e geração de tabelas sumarizadas sobre a incidência e evolução da COVID-19 nos diferentes bairros de Fortaleza. O objetivo é fornecer uma visão detalhada e organizada dos dados epidemiológicos locais para apoiar a compreensão do impacto da pandemia na cidade.

## 🚀 Funcionalidades

- **Pré-processamento de Dados:** Limpeza e tratamento de bases de dados oficiais da COVID-19, filtrando para o contexto municipal de Fortaleza.
- **Análise por Bairros:** Agrupamento e cruzamento de métricas como total de casos, óbitos e taxas por 100 mil habitantes em cada bairro.
- **Geração de Tabelas Automatizadas:** Exportação de tabelas estatísticas estruturadas (em formatos como CSV e Markdown) prontas para relatórios e apresentações.
- **Visualizações Básicas:** Scripts para gerar gráficos descritivos simples da distribuição espacial e temporal.

## 🛠️ Tecnologias Utilizadas

- **Python 3.x**
- **Pandas:** Para manipulação, limpeza e agregação de dados.
- **NumPy:** Para operações numéricas de suporte.
- **Matplotlib / Seaborn** *(Opcional)*: Para geração de gráficos de suporte.

## 📁 Estrutura do Projeto

```text
projeto-covid-fortaleza/
│
├── data/
│   ├── raw/           # Dados brutos obtidos de fontes oficiais
│   └── processed/     # Dados tratados após a execução dos scripts
│
├── outputs/
│   └── tables/        # Tabelas geradas em formato CSV/Markdown
│
├── src/
│   ├── cleaning.py    # Script de limpeza e padronização dos dados
│   ├── analysis.py    # Script de agregação e cálculos estatísticos
│   └── generator.py   # Script responsável por formatar e salvar as tabelas
│
├── requirements.txt   # Dependências do projeto
└── README.md          # Documentação do projeto
```

## ⚙️ Como Executar o Projeto

### Pré-requisitos
Certifique-es de ter o [Python](https://www.python.org/) instalado em sua máquina.

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/projeto-covid-fortaleza.git
   cd projeto-covid-fortaleza
   ```

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Execute os scripts de análise:**
   ```bash
   python src/cleaning.py
   python src/analysis.py
   python src/generator.py
   ```

As tabelas finais geradas estarão disponíveis na pasta `outputs/tables/`.

## 📊 Fontes de Dados

Os dados utilizados neste projeto são provenientes de bases públicas abertas disponibilizadas pela Prefeitura de Fortaleza / Secretaria da Saúde (SESA).

## 🤝 Contribuição

Contribuições são sempre bem-vindas! Sinta-se à vontade para abrir uma *issue* para relatar bugs ou sugerir melhorias.

## 📄 Licença

Este projeto está sob a licença [MIT](LICENSE).
