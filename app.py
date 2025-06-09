# 📊 Controle de Carteira com Streamlit - v6 (proteção por senha)

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime
import os

st.set_page_config(page_title="Controle de Carteira Manual", layout="wide")

# Autenticação simples com opção de manter sessão
CORRECT_PASSWORD = "minhasenha123"
if 'auth_ok' not in st.session_state:
    st.session_state['auth_ok'] = False

if not st.session_state['auth_ok']:
    st.title("🔐 Acesso à Carteira")
    senha = st.text_input("Digite a senha:", type="password")
    lembrar = st.checkbox("Manter conectado")
    if st.button("Entrar"):
        if senha == CORRECT_PASSWORD:
            st.session_state['auth_ok'] = True
            if lembrar:
                st.session_state['lembrar'] = True
            st.rerun()
        else:
            st.error("Senha incorreta. Tente novamente.")
    st.stop()

st.title("📈 Controle Manual de Carteira de Investimentos")

# Caminho do arquivo de persistência
ARQUIVO_MOV = 'movimentacoes.csv'

# Cotação do dólar automática
try:
    usdbrl = yf.Ticker('USDBRL=X')
    dolar = usdbrl.history(period='1d')['Close'].iloc[-1]
    st.sidebar.success(f"Cotação atual do dólar: R$ {dolar:.2f}")
except:
    dolar = None
    st.sidebar.error("Erro ao buscar a cotação do dólar.")

# Carregar movimentações do arquivo ou iniciar vazio
if 'movimentacoes' not in st.session_state:
    if os.path.exists(ARQUIVO_MOV):
        st.session_state['movimentacoes'] = pd.read_csv(ARQUIVO_MOV, parse_dates=['Data'])
    else:
        st.session_state['movimentacoes'] = pd.DataFrame(columns=[
            'Data', 'Operação', 'Ativo', 'Tipo', 'Carteira', 'Qtde.', 'Preço Unit.', 'Total R$'
        ])

# Mapeamento de tipo de ativo para moeda
def detectar_moeda(tipo):
    tipo = tipo.upper()
    if tipo in ['ETF', 'STOCK', 'BOND', 'REITS']:
        return 'USD'
    return 'BRL'

st.sidebar.header("➕ Registrar Movimentação")

with st.sidebar.form("formulario_mov"):
    data = st.date_input("Data da operação", value=datetime.today())
    operacao = st.selectbox("Tipo de operação", ['Compra', 'Venda'])
    ativo = st.text_input("Código do Ativo (ex: VOO, PETR4)", max_chars=10)
    tipo = st.selectbox("Tipo", ['Ação', 'FII', 'ETF', 'STOCK', 'BDR', 'REITS', 'Renda Fixa', 'Cripto'])
    carteira = st.selectbox("Carteira", ['Lucas', 'Pais', 'Outros'])
    qtde = st.number_input("Quantidade", min_value=0.01, step=0.01)
    preco = st.number_input("Preço unitário", min_value=0.0, step=0.01)
    submitted = st.form_submit_button("Adicionar")

    if submitted and ativo:
        total = qtde * preco * (-1 if operacao == 'Venda' else 1)
        nova = pd.DataFrame([{
            'Data': pd.to_datetime(data), 'Operação': operacao, 'Ativo': ativo.upper(), 'Tipo': tipo,
            'Carteira': carteira, 'Qtde.': qtde * (1 if operacao == 'Compra' else -1),
            'Preço Unit.': preco, 'Total R$': total
        }])
        st.session_state['movimentacoes'] = pd.concat([st.session_state['movimentacoes'], nova], ignore_index=True)
        st.session_state['movimentacoes'].to_csv(ARQUIVO_MOV, index=False)
        st.success(f"{operacao} de {qtde} {ativo.upper()} registrada!")

# Mostrar movimentações
movs = st.session_state['movimentacoes']
if not movs.empty:
    st.subheader("📋 Histórico de Movimentações")
    st.dataframe(movs.sort_values(by='Data', ascending=False), use_container_width=True)

    # Cálculo de posição atual
    posicao = movs.groupby(['Ativo', 'Tipo', 'Carteira']).agg({
        'Qtde.': 'sum',
        'Total R$': 'sum'
    }).reset_index()
    posicao = posicao[posicao['Qtde.'] > 0]
    posicao['Preço Médio'] = posicao['Total R$'] / posicao['Qtde.']
    posicao['Moeda'] = posicao['Tipo'].apply(detectar_moeda)

    # Buscar cotações atuais
    cotacoes = {}
    for ativo in posicao['Ativo'].unique():
        try:
            ticker = yf.Ticker(ativo)
            preco_mercado = ticker.history(period='1d')['Close'].iloc[-1]
            cotacoes[ativo] = preco_mercado
        except:
            cotacoes[ativo] = None

    posicao['Cotação Atual'] = posicao['Ativo'].map(cotacoes)

    # Valor atual em moeda original e BRL
    posicao['Val. Atual (moeda)'] = posicao['Cotação Atual'] * posicao['Qtde.']
    posicao['Val. Atual (BRL)'] = posicao.apply(
        lambda row: row['Val. Atual (moeda)'] * dolar if row['Moeda'] == 'USD' else row['Val. Atual (moeda)'], axis=1)
    posicao['Investido (BRL)'] = posicao.apply(
        lambda row: row['Preço Médio'] * row['Qtde.'] * dolar if row['Moeda'] == 'USD' else row['Preço Médio'] * row['Qtde.'], axis=1)
    posicao['Lucro (BRL)'] = posicao['Val. Atual (BRL)'] - posicao['Investido (BRL)']
    posicao['Rentabilidade (%)'] = (posicao['Lucro (BRL)'] / posicao['Investido (BRL)']) * 100

    # Formatação de colunas
    def format_moeda(valor, moeda):
        if pd.isna(valor): return '-'
        simbolo = 'US$' if moeda == 'USD' else 'R$'
        return f"{simbolo} {valor:,.2f}"

    posicao['ValFormat'] = posicao['Val. Atual (BRL)']  # manter valor bruto para gráficos
    posicao['Val. Atual (BRL)'] = posicao['Val. Atual (BRL)'].map(lambda v: f"R$ {v:,.2f}")
    posicao['Lucro (BRL)'] = posicao['Lucro (BRL)'].map(lambda v: f"R$ {v:,.2f}")
    posicao['Preço Médio'] = posicao.apply(lambda row: format_moeda(row['Preço Médio'], row['Moeda']), axis=1)
    posicao['Cotação Atual'] = posicao.apply(lambda row: format_moeda(row['Cotação Atual'], row['Moeda']), axis=1)

    # Aplicar estilo à rentabilidade
    def cor_rentabilidade(val):
        try:
            return f"color: {'green' if val > 0 else 'red'}"
        except:
            return ""

    styled = posicao[['Ativo', 'Tipo', 'Carteira', 'Moeda', 'Qtde.', 'Preço Médio', 'Cotação Atual',
                      'Val. Atual (BRL)', 'Lucro (BRL)', 'Rentabilidade (%)']].style \
        .format({
            'Rentabilidade (%)': '{:.2f}%'
        }).applymap(cor_rentabilidade, subset=['Rentabilidade (%)'])

    st.subheader("📊 Posição Atual por Ativo")
    st.dataframe(styled, use_container_width=True)

    st.subheader("📌 Distribuição por Tipo de Ativo")
    tipo_group = posicao.groupby('Tipo')['ValFormat'].sum()
    fig1, ax1 = plt.subplots()
    tipo_group.plot.pie(autopct='%1.1f%%', ax=ax1)
    ax1.set_ylabel('')
    st.pyplot(fig1)

# Botão para limpar tudo
if st.sidebar.button("🗑️ Limpar movimentações"):
    st.session_state['movimentacoes'] = pd.DataFrame(columns=st.session_state['movimentacoes'].columns)
    if os.path.exists(ARQUIVO_MOV): os.remove(ARQUIVO_MOV)
    st.sidebar.success("Todas as movimentações foram apagadas.")
