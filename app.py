import streamlit as st
import pandas as pd
import io
import os
from modulos.azure_client import ler_mestra_do_azure
from modulos.filtro import aprovar_campanha

# Configuração Visual
st.set_page_config(page_title="Higienizador HSM", page_icon="❄️", layout="centered")

# ==========================================
# CAMADA DE SEGURANÇA (WHITELIST + QUERY PARAMS)
# ==========================================
dicionario_usuarios = st.secrets["usuarios_autorizados"]

# O Recepcionista olha primeiro para a URL (Crachá)
if "user" in st.query_params:
    email_digitado = st.query_params["user"]
else:
    # Se não tiver na URL, pede para digitar
    email_digitado = st.sidebar.text_input("🔑 Identificação (E-mail corporativo):").strip().lower()

# Verifica se tem permissão
if email_digitado not in dicionario_usuarios:
    st.title("❄️ Geladeira Inteligente HSM")
    st.warning("Acesso restrito. Por favor, identifique-se no menu lateral para liberar a esteira de higienização.")
    st.stop()
else:
    # Se tem permissão, pendura o crachá na URL para sobreviver ao F5
    st.query_params["user"] = email_digitado

nome_usuario = dicionario_usuarios[email_digitado]

# ==========================================
# PAINEL DE CONTROLE (SIDEBAR)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Controles do Sistema")

# Botão de Reboot (Limpa o Cache e a Memória)
if st.sidebar.button("🔄 Reboot (Limpar Cache)"):
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

# Botão de Logoff (Arranca o Crachá da URL)
if st.sidebar.button("🚪 Logoff"):
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()

# ==========================================
# APLICAÇÃO PRINCIPAL
# ==========================================
st.title("❄️ Geladeira Inteligente HSM")
st.markdown(f"Bem-vindo(a), **{nome_usuario}**! Suba a sua campanha para cortar custos com disparos inválidos.")

st.header("Higienizar Lista")

# A Placa de Instruções (O Contrato de Dados UI)
st.info("""
**📋 Padrão de Arquivo Esperado:**
Para garantir a qualidade dos relatórios, envie a sua planilha Excel contendo obrigatoriamente as colunas:
1. **`WhatsAppdoContato`**: O número de telefone.
2. **`Carteira`**: O nome da operação ou carteira responsável.

*Nota: Você pode incluir outras colunas (Nome, CPF, etc.). A nossa Geladeira irá preservar todas elas e devolverá o seu arquivo intacto, adicionando apenas o `Status_Atual` e a `Data_Filtragem` no final.*
""")

# ... (o resto do seu código de upload continua aqui) ...

# 1. Função que limpa a prateleira se o utilizador subir um ficheiro diferente
def limpar_memoria():
    st.session_state.processamento_concluido = False

# Inicializa a prateleira na memória, se não existir
if 'processamento_concluido' not in st.session_state:
    st.session_state.processamento_concluido = False

arquivo_campanha = st.file_uploader("Arraste a Campanha Aqui (.xlsx)", type=["xlsx"], on_change=limpar_memoria)

if arquivo_campanha is not None:
    # Este bloco APENAS processa e guarda na prateleira (Session State)
    if st.button("Aplicar Filtro de Geladeira"):
        try:
            with st.spinner("O Carro-Forte está buscando as permissões no Azure..."):
                df_mestra = ler_mestra_do_azure() 
                df_campanha = pd.read_excel(arquivo_campanha)
                col_tel = 'WhatsAppdoContato' if 'WhatsAppdoContato' in df_campanha.columns else df_campanha.columns[0]
                
                df_aprovados, df_rejeitados = aprovar_campanha(df_campanha, df_mestra, col_tel)
                
                if 'Status_Atual' in df_rejeitados.columns:
                    df_leads = df_rejeitados[df_rejeitados['Status_Atual'] == 'GELADEIRA (Avaliar Comercial)']
                    df_puro_retidos = df_rejeitados[df_rejeitados['Status_Atual'] != 'GELADEIRA (Avaliar Comercial)']
                else:
                    df_leads = pd.DataFrame(columns=df_rejeitados.columns)
                    df_puro_retidos = df_rejeitados
                
                # GUARDANDO TUDO NA PRATELEIRA DA MEMÓRIA
                st.session_state.metricas = [len(df_campanha), len(df_aprovados), len(df_puro_retidos), len(df_leads)]
                
                # Gerando e guardando Buffer 1
                buf_aprov = io.BytesIO()
                with pd.ExcelWriter(buf_aprov, engine='xlsxwriter') as writer:
                    df_aprovados.to_excel(writer, index=False, sheet_name='Aprovados')
                st.session_state.buffer_aprovados = buf_aprov.getvalue()
                
                # Gerando e guardando Buffer 2
                buf_ret = io.BytesIO()
                with pd.ExcelWriter(buf_ret, engine='xlsxwriter') as writer:
                    if not df_leads.empty:
                        df_leads.to_excel(writer, index=False, sheet_name='1_Leads_Comerciais')
                    if not df_puro_retidos.empty:
                        df_puro_retidos.to_excel(writer, index=False, sheet_name='2_Retidos_Economia')
                    if df_leads.empty and df_puro_retidos.empty:
                        pd.DataFrame({'Aviso': ['100% aprovado.']}).to_excel(writer, index=False)
                st.session_state.buffer_retidos = buf_ret.getvalue()
                
                # Sinaliza que o trabalho está pronto!
                st.session_state.processamento_concluido = True
                
        except Exception as e:
            st.error(f"Erro de comunicação com o Cofre: {e}")

    # ==================================================
    # RENDERIZAÇÃO DA INTERFACE (Lê sempre da Prateleira)
    # ==================================================
    # Como esta parte está fora do 'if st.button', ela sobrevive ao clique de download!
    if st.session_state.processamento_concluido:
        st.success("Filtro Aplicado com Sucesso!")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Analisado", st.session_state.metricas[0])
        col2.metric("Aprovados (Verde)", st.session_state.metricas[1])
        col3.metric("Retidos (Economia)", st.session_state.metricas[2])
        col4.metric("Leads B2B (URAs)", st.session_state.metricas[3])
        
        st.markdown("### 📥 Arquivos de Saída")
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            st.download_button(
                label="🚀 Baixar Aprovados (Disparo HSM)",
                data=st.session_state.buffer_aprovados,
                file_name="01_Campanha_Aprovada_HSM.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        with col_btn2:
            st.download_button(
                label="⚠️ Baixar Leads e Retidos (Auditoria)",
                data=st.session_state.buffer_retidos,
                file_name="02_Leads_e_Retidos_Auditoria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
