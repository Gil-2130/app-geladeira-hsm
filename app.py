import streamlit as st
import pandas as pd
import io
import os
from modulos.azure_client import ler_mestra_do_azure
from modulos.filtro import aprovar_campanha

# Configuração Visual
st.set_page_config(page_title="Higienizador HSM", page_icon="❄️", layout="centered")

# ==========================================
# CAMADA DE SEGURANÇA (WHITELIST + UX)
# ==========================================
email_digitado = st.sidebar.text_input("🔑 Identificação (E-mail corporativo):").strip().lower()

# Carregamos a "prancheta" de usuários do cofre (Dicionário)
dicionario_usuarios = st.secrets["usuarios_autorizados"]

# O Segurança verifica se a Chave (e-mail) existe no Dicionário
if email_digitado not in dicionario_usuarios:
    st.title("❄️ Geladeira Inteligente HSM")
    st.warning("Acesso restrito. Por favor, identifique-se no menu lateral para liberar a esteira de higienização.")
    st.stop() # Interrompe a renderização do resto do código

# Se passou, pegamos o Valor (Nome) associado àquela Chave
nome_usuario = dicionario_usuarios[email_digitado]

# ==========================================
# APLICAÇÃO PRINCIPAL (Liberada após login)
# ==========================================
st.title("❄️ Geladeira Inteligente HSM")

# A Saudação Humanizada usando o nome extraído
st.markdown(f"Bem-vindo(a), **{nome_usuario}**! Suba a sua campanha para cortar custos com disparos inválidos.")

st.header("Higienizar Lista")
st.info("Faça o upload da planilha que você deseja disparar hoje.")

arquivo_campanha = st.file_uploader("Arraste a Campanha Aqui (.xlsx)", type=["xlsx"])

if arquivo_campanha is not None:
    if st.button("Aplicar Filtro de Geladeira"):
        try:
            with st.spinner("O Carro-Forte está buscando as permissões no Azure..."):
                df_mestra = ler_mestra_do_azure() 
                df_campanha = pd.read_excel(arquivo_campanha)
                
                col_tel = 'WhatsAppdoContato' if 'WhatsAppdoContato' in df_campanha.columns else df_campanha.columns[0]
                
                # A Esteira de Filtragem
                df_aprovados, df_rejeitados = aprovar_campanha(df_campanha, df_mestra, col_tel)
                
                # ==========================================
                # O ARQUIVISTA: Separação de Leads e Detratores
                # ==========================================
                if 'Status_Atual' in df_rejeitados.columns:
                    # Máscara Booleana Vetorizada
                    df_leads = df_rejeitados[df_rejeitados['Status_Atual'] == 'GELADEIRA (Avaliar Comercial)']
                    df_puro_retidos = df_rejeitados[df_rejeitados['Status_Atual'] != 'GELADEIRA (Avaliar Comercial)']
                else:
                    df_leads = pd.DataFrame(columns=df_rejeitados.columns)
                    df_puro_retidos = df_rejeitados
                
                st.success("Filtro Aplicado com Sucesso!")
                
                # PAINEL EXECUTIVO: 4 Colunas de Métricas
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Analisado", len(df_campanha))
                col2.metric("Aprovados (Verde)", len(df_aprovados))
                col3.metric("Retidos (Economia)", len(df_puro_retidos))
                col4.metric("Leads B2B (URAs)", len(df_leads))
                
                # ==========================================
                # GERAÇÃO DOS BUFFERS EM RAM
                # ==========================================
                
                # Buffer 1: Aprovados (Porta Verde - Direto pro HSM)
                buffer_aprovados = io.BytesIO()
                with pd.ExcelWriter(buffer_aprovados, engine='xlsxwriter') as writer:
                    df_aprovados.to_excel(writer, index=False, sheet_name='Aprovados')
                
                # Buffer 2: Retidos e Leads (Porta Amarela - Comercial/Auditoria)
                buffer_retidos = io.BytesIO()
                with pd.ExcelWriter(buffer_retidos, engine='xlsxwriter') as writer:
                    if not df_leads.empty:
                        df_leads.to_excel(writer, index=False, sheet_name='1_Leads_Comerciais')
                    if not df_puro_retidos.empty:
                        df_puro_retidos.to_excel(writer, index=False, sheet_name='2_Retidos_Economia')
                    
                    # Tratamento de exceção caso nenhum seja retido
                    if df_leads.empty and df_puro_retidos.empty:
                        pd.DataFrame({'Aviso': ['100% da base foi aprovada.']}).to_excel(writer, index=False, sheet_name='Vazio')

                # ==========================================
                # BOTÕES DE DOWNLOAD (Lado a Lado)
                # ==========================================
                st.markdown("### 📥 Arquivos de Saída")
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    st.download_button(
                        label="🚀 Baixar Aprovados (Para Disparo HSM)",
                        data=buffer_aprovados.getvalue(),
                        file_name="01_Campanha_Aprovada_HSM.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                with col_btn2:
                    st.download_button(
                        label="⚠️ Baixar Leads e Retidos (Auditoria)",
                        data=buffer_retidos.getvalue(),
                        file_name="02_Leads_e_Retidos_Auditoria.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
        except Exception as e:
            st.error(f"Erro de comunicação com o Cofre: {e}")
