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
                # O Cérebro agora é mantido invisivelmente pelo robô local (nosso próximo passo)
                df_mestra = ler_mestra_do_azure() 
                df_campanha = pd.read_excel(arquivo_campanha)
                
                col_tel = 'WhatsAppdoContato' if 'WhatsAppdoContato' in df_campanha.columns else df_campanha.columns[0]
                
                # O Filtro cruza a campanha com o Cérebro Mestre
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
            st.error(f"Erro de comunicação com o Cofre: {e}")
