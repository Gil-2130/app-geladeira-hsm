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

def atualizar_historico_bi(df_novo_dia, nome_blob="Historico_BI_Geladeira.csv"):
    """
    O Livro-Razão: Adiciona o processamento do dia ao histórico do Azure, 
    garantindo a Idempotência (zero duplicados) via Chave Composta.
    """
    try:
        # 1. Recupera as credenciais (ajuste se o seu código for ligeiramente diferente)
        string_conexao = st.secrets["AZURE_CONNECTION_STRING"]
        nome_container = st.secrets["AZURE_CONTAINER_NAME"]
        
        blob_service_client = BlobServiceClient.from_connection_string(string_conexao)
        container_client = blob_service_client.get_container_client(nome_container)
        blob_client = container_client.get_blob_client(nome_blob)
        
        # 2. Fabricação do Carimbo de Cera (Chave Composta)
        df_novo_dia['ID_Evento'] = df_novo_dia['Data_Filtragem'].astype(str) + "_" + \
                                   df_novo_dia['Carteira'].astype(str) + "_" + \
                                   df_novo_dia['WhatsAppdoContato'].astype(str)
        
        # 3. Tentativa de Leitura do Livro Antigo
        try:
            stream_download = blob_client.download_blob()
            df_historico_antigo = pd.read_csv(io.BytesIO(stream_download.readall()), sep=';', dtype=str)
        except ResourceNotFoundError:
            # Se for o primeiro dia da operação, o livro ainda não existe.
            df_historico_antigo = pd.DataFrame()
        
        # 4. UPSERT: A Fusão e a Guilhotina
        if not df_historico_antigo.empty:
            df_consolidado = pd.concat([df_historico_antigo, df_novo_dia], ignore_index=True)
        else:
            df_consolidado = df_novo_dia.copy()
            
        # Esmaga quem tentou processar a mesma base duas vezes no mesmo dia
        df_consolidado = df_consolidado.drop_duplicates(subset=['ID_Evento'], keep='last')
        
        # 5. Salvar de volta no Cofre (Overwrite)
        buffer = io.BytesIO()
        df_consolidado.to_csv(buffer, sep=';', index=False, encoding='utf-8-sig')
        blob_client.upload_blob(buffer.getvalue(), overwrite=True)
        
        return True
        
    except Exception as e:
        print(f"Erro Crítico ao atualizar o Livro-Razão BI: {e}")
        return False
    
    # Sobrescreve o blob antigo pelo novo
    blob_client.upload_blob(output, overwrite=True)
