import streamlit as st
import pandas as pd
import io
import os
from modulos.azure_client import ler_mestra_do_azure
from modulos.filtro import aprovar_campanha
# Atualize a linha de importação do azure_client para incluir a nova função
from modulos.azure_client import ler_mestra_do_azure, atualizar_historico_bi

# Configuração Visual
st.set_page_config(page_title="Higienizador HSM", page_icon="❄️", layout="wide")

# ==========================================
# CAMADA DE SEGURANÇA (WHITELIST + QUERY PARAMS)
# ==========================================
dicionario_usuarios = st.secrets["usuarios_autorizados"]

if "user" in st.query_params:
    email_digitado = st.query_params["user"]
else:
    email_digitado = st.sidebar.text_input("🔑 Identificação (E-mail corporativo):").strip().lower()

if email_digitado not in dicionario_usuarios:
    st.title("❄️ Geladeira Inteligente HSM")
    st.warning("Acesso restrito. Por favor, identifique-se no menu lateral para liberar a esteira de higienização.")
    st.stop()
else:
    st.query_params["user"] = email_digitado

nome_usuario = dicionario_usuarios[email_digitado]

# ==========================================
# PAINEL DE CONTROLE (SIDEBAR)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Controles do Sistema")

if st.sidebar.button("🔄 Reboot (Limpar Cache)"):
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

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

st.info("""
**📋 Padrão de Arquivo Esperado:**
Aceitamos planilhas no formato **Excel (.xlsx)** ou **Texto (.csv)**. O arquivo deve conter:
1. **`WhatsAppdoContato`** (ou `VALOR_DO_REGISTRO` / `Telefone`): A coluna com os números.
2. **`Carteira`**: O nome da operação (Opcional, mas recomendado).

*Nota: Você pode incluir dezenas de outras colunas (Nome, CPF, etc.). A Geladeira preservará absolutamente todas elas, devolvendo o seu arquivo limpo no mesmo formato em que foi enviado.*
""")

def limpar_memoria():
    st.session_state.processamento_concluido = False

if 'processamento_concluido' not in st.session_state:
    st.session_state.processamento_concluido = False

arquivo_campanha = st.file_uploader("Arraste a Campanha (.xlsx ou .csv)", type=["xlsx", "csv"], on_change=limpar_memoria)

if arquivo_campanha is not None:
    if st.button("Aplicar Filtro de Geladeira"):
        try:
            with st.spinner("O Carro-Forte está buscando as permissões no Azure e processando..."):
                df_mestra = ler_mestra_do_azure() 
                
                # ---------------------------------------------------------
                # EXTRAÇÃO PASSIVA DE METADADOS (Carteira baseada no nome)
                # ---------------------------------------------------------
                nome_arquivo_completo = arquivo_campanha.name
                nome_base = nome_arquivo_completo.rsplit('.', 1)[0]
                extensao = nome_arquivo_completo.rsplit('.', 1)[1].lower()
                
                # ---------------------------------------------------------
                # O TRADUTOR POLIGLOTA
                # ---------------------------------------------------------
                if extensao == 'csv':
                    df_campanha = pd.read_csv(arquivo_campanha, sep=';', dtype=str)
                    if len(df_campanha.columns) == 1:
                        arquivo_campanha.seek(0)
                        df_campanha = pd.read_csv(arquivo_campanha, sep=',', dtype=str)
                else:
                    df_campanha = pd.read_excel(arquivo_campanha, dtype=str)
                
                colunas_alvo = ['VALOR_DO_REGISTRO', 'WhatsAppdoContato', 'Telefone', 'Celular']
                col_tel = next((col for col in colunas_alvo if col in df_campanha.columns), df_campanha.columns[0])
                
                # ---------------------------------------------------------
                # A ESTEIRA E O MORDOMO (Enriquecimento Silencioso)
                # ---------------------------------------------------------
                df_aprovados, df_rejeitados = aprovar_campanha(df_campanha, df_mestra, col_tel)
                
                # Enriquecimento
                df_aprovados['Carteira'] = nome_base
                df_rejeitados['Carteira'] = nome_base
                
                # =========================================================
                # O LIVRO-RAZÃO: Alimentando o Power BI silenciosamente
                # =========================================================
                colunas_bi = [col_tel, 'Status_Atual', 'Data_Filtragem', 'Carteira']
                
                # Criamos um DataFrame exclusivo para o BI (juntando os bons e os maus)
                df_bi_hoje = pd.concat([
                    df_aprovados[colunas_bi].rename(columns={col_tel: 'WhatsAppdoContato'}),
                    df_rejeitados[colunas_bi].rename(columns={col_tel: 'WhatsAppdoContato'})
                ], ignore_index=True)
                
                # Chamada para o Azure (grava em background)
                atualizar_historico_bi(df_bi_hoje)
                # =========================================================
                
                if 'Status_Atual' in df_rejeitados.columns:
                    df_leads = df_rejeitados[df_rejeitados['Status_Atual'] == 'GELADEIRA (Avaliar Comercial)']
                    df_puro_retidos = df_rejeitados[df_rejeitados['Status_Atual'] != 'GELADEIRA (Avaliar Comercial)']
                else:
                    df_leads = pd.DataFrame(columns=df_rejeitados.columns)
                    df_puro_retidos = df_rejeitados
                
                # ---------------------------------------------------------
                # BIFURCAÇÃO: PREPARANDO A CAIXA PARA O CLIENTE
                # Removemos os rastros do sistema para não quebrar a discadora
                # ---------------------------------------------------------
                colunas_sistema = ['Status_Atual', 'Data_Filtragem', 'Carteira']
                df_aprovados_cliente = df_aprovados.drop(columns=[c for c in colunas_sistema if c in df_aprovados.columns])
                
                st.session_state.metricas = [len(df_campanha), len(df_aprovados), len(df_puro_retidos), len(df_leads)]
                
                # =========================================================
                # EXPORTAÇÃO DINÂMICA (CSV vs XLSX)
                # =========================================================
                
                # Buffer 1: Aprovados Limpos
                buf_aprov = io.BytesIO()
                if extensao == 'csv':
                    df_aprovados_cliente.to_csv(buf_aprov, sep=';', index=False, encoding='utf-8-sig')
                    st.session_state.mime_aprov = "text/csv"
                    st.session_state.nome_arq_aprov = f"{nome_base}_Aprovados.csv"
                else:
                    with pd.ExcelWriter(buf_aprov, engine='xlsxwriter') as writer:
                        df_aprovados_cliente.to_excel(writer, index=False, sheet_name='Aprovados')
                    st.session_state.mime_aprov = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    st.session_state.nome_arq_aprov = f"{nome_base}_Aprovados.xlsx"
                st.session_state.buffer_aprovados = buf_aprov.getvalue()
                
                # Buffer 2: Retidos (Com colunas de sistema mantidas para auditoria)
                buf_ret = io.BytesIO()
                if extensao == 'csv':
                    # CSV não tem abas, exporta tudo junto
                    df_rejeitados.to_csv(buf_ret, sep=';', index=False, encoding='utf-8-sig')
                    st.session_state.mime_ret = "text/csv"
                    st.session_state.nome_arq_ret = f"{nome_base}_Leads_e_Retidos.csv"
                else:
                    with pd.ExcelWriter(buf_ret, engine='xlsxwriter') as writer:
                        if not df_leads.empty:
                            df_leads.to_excel(writer, index=False, sheet_name='1_Leads_Comerciais')
                        if not df_puro_retidos.empty:
                            df_puro_retidos.to_excel(writer, index=False, sheet_name='2_Retidos_Economia')
                        if df_leads.empty and df_puro_retidos.empty:
                            pd.DataFrame({'Aviso': ['100% aprovado.']}).to_excel(writer, index=False)
                    st.session_state.mime_ret = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    st.session_state.nome_arq_ret = f"{nome_base}_Leads_e_Retidos.xlsx"
                st.session_state.buffer_retidos = buf_ret.getvalue()
                
                st.session_state.processamento_concluido = True
                
        except Exception as e:
            st.error(f"Erro na operação: {e}")

    # ==================================================
    # RENDERIZAÇÃO DA INTERFACE DINÂMICA
    # ==================================================
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
                file_name=st.session_state.nome_arq_aprov,
                mime=st.session_state.mime_aprov
            )
            
        with col_btn2:
            st.download_button(
                label="⚠️ Baixar Leads e Retidos (Auditoria)",
                data=st.session_state.buffer_retidos,
                file_name=st.session_state.nome_arq_ret,
                mime=st.session_state.mime_ret
            )
