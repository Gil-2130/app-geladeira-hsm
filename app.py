# Arquivo: app.py (Trecho Atualizado)

import streamlit as st
import pandas as pd
import io
# Trocamos a biblioteca 'os' pelos nossos Fiscais do Azure
from modulos.azure_client import ler_mestra_do_azure, salvar_mestra_no_azure
from modulos.filtro import aprovar_campanha
from modulos.retroalimentacao import processar_retornos

# Teste temporário de integridade do Cofre
if "container_name" in st.secrets:
    st.toast("Cofre conectado com sucesso!", icon="✅")

st.set_page_config(page_title="Higienizador HSM", page_icon="❄️", layout="centered")

st.title("❄️ Geladeira Inteligente HSM")
st.markdown("Suba as suas campanhas para cortar custos com disparos inválidos.")

aba1, aba2 = st.tabs(["🚀 1. Filtrar Nova Campanha", "📥 2. Atualizar Retornos (Fechamento)"])

# ABA 1: FILTRO
with aba1:
    st.header("Passo 1: Higienizar Lista")
    st.info("Faça o upload da planilha que você deseja disparar hoje.")
    arquivo_campanha = st.file_uploader("Arraste a Campanha Aqui (.xlsx)", type=["xlsx"], key="upload_camp")
    
    if arquivo_campanha is not None:
        if st.button("Aplicar Filtro de Geladeira"):
            try:
                with st.spinner("O Carro-Forte está buscando os dados no Azure..."):
                    df_mestra = ler_mestra_do_azure() # Substituiu o pd.read_excel local!
                    df_campanha = pd.read_excel(arquivo_campanha)
                    
                    col_tel = 'WhatsAppdoContato' if 'WhatsAppdoContato' in df_campanha.columns else df_campanha.columns[0]
                    df_aprovados, df_rejeitados = aprovar_campanha(df_campanha, df_mestra, col_tel)
                    
                    st.success("Filtro Aplicado com Sucesso!")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Analisado", len(df_campanha))
                    col2.metric("Aprovados (Verde)", len(df_aprovados))
                    col3.metric("Retidos (Economia)", len(df_rejeitados))
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_aprovados.to_excel(writer, index=False, sheet_name='Aprovados')
                    
                    st.download_button(
                        label="⬇️ Baixar Lista Aprovada",
                        data=buffer.getvalue(),
                        file_name="01_Campanha_Aprovada.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"Erro ao conectar ao Azure ou processar: {e}")

# ABA 2: FECHAMENTO
with aba2:
    st.header("Passo 2: Retroalimentar o Cérebro")
    st.warning("Suba o relatório de entregas da Meta para atualizar a Geladeira.")
    arquivo_retorno = st.file_uploader("Arraste os Retornos Aqui (.xlsx)", type=["xlsx"], key="upload_ret")
    
    if arquivo_retorno is not None:
        if st.button("Atualizar Base Mestra no Azure"):
            try:
                with st.spinner("Trazendo dados do Cofre e processando UPSERT..."):
                    df_mestra = ler_mestra_do_azure()
                    df_retornos = pd.read_excel(arquivo_retorno)
                    
                    col_tel_ret = 'WhatsApp do contato' if 'WhatsApp do contato' in df_retornos.columns else df_retornos.columns[0]
                    
                    df_atualizado = processar_retornos(df_mestra, df_retornos, col_tel_ret)
                    
                    salvar_mestra_no_azure(df_atualizado) # Substituiu o to_excel local!
                    
                    st.success("O Cérebro no Azure foi atualizado com sucesso!")
                    st.balloons()
            except Exception as e:
                st.error(f"Erro ao salvar no Azure: {e}")