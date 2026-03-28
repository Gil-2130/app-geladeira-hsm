# Arquivo: modulos/azure_client.py
# Função: O Carro-Forte (Conexão Segura com o Azure em Memória RAM)

from azure.storage.blob import BlobServiceClient
import pandas as pd
import io
import streamlit as st

def obter_cliente_blob():
    """Conecta ao Azure usando os Segredos do Streamlit."""
    conn_str = st.secrets["connection_string"]
    return BlobServiceClient.from_connection_string(conn_str)

def ler_mestra_do_azure():
    """Vai ao Cofre, pega o Excel e joga direto na RAM (DataFrame)."""
    container = st.secrets["container_name"]
    blob_name = 'Base_Controle_Mestra.xlsx'
    
    blob_service_client = obter_cliente_blob()
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
    
    # Faz o download como stream de bytes, sem tocar no disco
    download_stream = blob_client.download_blob()
    bytes_io = io.BytesIO(download_stream.readall())
    
    return pd.read_excel(bytes_io)

def salvar_mestra_no_azure(df):
    """Pega o DataFrame da RAM, converte para Excel e joga no Cofre."""
    container = st.secrets["container_name"]
    blob_name = 'Base_Controle_Mestra.xlsx'
    
    blob_service_client = obter_cliente_blob()
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
    
    # Prepara o Excel na memória RAM
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    
    # Sobrescreve o blob antigo pelo novo
    blob_client.upload_blob(output, overwrite=True)
