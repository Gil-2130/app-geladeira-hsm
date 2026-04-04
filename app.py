import streamlit as st
import pandas as pd
import io
import os
import plotly.express as px
from datetime import datetime
from modulos.azure_client import ler_mestra_do_azure, atualizar_historico_bi
from modulos.filtro import aprovar_campanha

# ==========================================
# CONFIGURAÇÃO VISUAL & BIBLIOTECAS
# ==========================================
st.set_page_config(page_title="Geladeira HSM | Dashboard", page_icon="❄️", layout="wide")

# INJEÇÃO DE CSS PARA ALINHAMENTO ISOMÉTRICO (Subjugação do Motor React)
st.markdown("""
    <style>
        /* 1. Alinha a linha mestra para esticar as colunas */
        div[data-testid="stHorizontalBlock"] {
            align-items: stretch !important;
        }
        
        /* 2. Transforma cada coluna num container puramente flexível */
        div[data-testid="column"] {
            display: flex !important;
            flex-direction: column !important;
        }
        
        /* 3. Força a div base da coluna a agir como um elástico */
        div[data-testid="column"] > div {
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
        }
        
        /* 4. Estica a caixa externa da Borda Mágica */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
        }
        
        /* 5. O TIRO FINAL: Estica a caixa interna que pinta o fundo cinza e tem a borda */
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important; /* Opcional: Centraliza os alertas no meio da caixa */
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# O COFRE DE SESSÃO (A "Misericórdia Matinal")
# ==========================================
hoje_str = datetime.now().strftime('%Y-%m-%d')

# Se mudou de dia ou se é o primeiro acesso, recriamos o cofre vazio
if 'data_sessao' not in st.session_state or st.session_state.data_sessao != hoje_str:
    st.session_state.data_sessao = hoje_str
    st.session_state.historico_diario = {} # Dicionário: Chave = Nome do Arquivo

# Variável de controle do processamento atual
if 'processamento_concluido' not in st.session_state:
    st.session_state.processamento_concluido = False

# ==========================================
# CAMADA DE SEGURANÇA (WHITELIST)
# ==========================================
dicionario_usuarios = st.secrets.get("usuarios_autorizados", {})

if "user" in st.query_params:
    email_digitado = st.query_params["user"]
else:
    email_digitado = st.sidebar.text_input("🔑 Identificação (E-mail corporativo):").strip().lower()

if email_digitado not in dicionario_usuarios:
    st.title("❄️ Geladeira Inteligente HSM")
    st.warning("Acesso restrito. Identifique-se no menu lateral.")
    st.stop()
else:
    st.query_params["user"] = email_digitado

nome_usuario = dicionario_usuarios[email_digitado]

# ==========================================
# PAINEL DE CONTROLE (SIDEBAR)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Painel do Executivo")

# O Botão de Reset Manual
if st.sidebar.button("🗑️ Resetar Dados de Hoje"):
    st.session_state.historico_diario = {}
    st.session_state.processamento_concluido = False
    st.rerun()

if st.sidebar.button("🔄 Recarregar Cérebro (Limpar Cache)"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# APLICAÇÃO PRINCIPAL & CABEÇALHO DIVIDIDO
# ==========================================
col_titulo, col_instrucoes = st.columns([1.5, 1])

with col_titulo:
    st.title("❄️ Geladeira Inteligente HSM")
    st.markdown(f"**Operador:** {nome_usuario} | **Data da Sessão:** {hoje_str}")

with col_instrucoes:
    st.markdown("<br>", unsafe_allow_html=True)
    st.info("📌 **Instrução:** Suba a sua base de contatos no formato Excel (.xlsx) ou CSV para higienizar a campanha e cortar custos com disparos inválidos.")

st.markdown("---")

CUSTO_HSM = 0.40 # O valor financeiro da economia

# Layout de duas  no topo
col_upload, col_resumo = st.columns([1, 1])

def limpar_tela_atual():
    st.session_state.processamento_concluido = False

# --- Coluna Upload ---
with col_upload:
    with st.container(height=225, border=True): 
        arquivo_campanha = st.file_uploader("Suba a Campanha (.xlsx ou .csv)", type=["xlsx", "csv"], on_change=limpar_tela_atual)
        
        # O botão agora nasce e vive DENTRO da caixa
        processar_btn = False
        if arquivo_campanha is not None:
            processar_btn = st.button("🚀 Processar e Filtrar", type="primary", width="stretch")

# --- Coluna Resumo ---
total_dia_economia = 0
total_dia_retidos = 0
total_dia_analisado = 0

if st.session_state.historico_diario:
    for arquivo, dados in st.session_state.historico_diario.items():
        total_dia_economia += dados['Economia']
        total_dia_retidos += dados['Retidos_Totais']
        total_dia_analisado += dados['Total']

# --- Coluna Resumo ---
with col_resumo:
    with st.container(height=225, border=True):
        st.markdown("### 💰 Acumulado do Dia")
        if total_dia_analisado > 0:
            st.success(f"**Economia Acumulada Hoje:** R$ {total_dia_economia:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
            st.info(f"**Bloqueios Hoje:** {total_dia_retidos} contatos em {len(st.session_state.historico_diario)} arquivos.")
        else:
            st.markdown("*Nenhuma campanha processada nesta sessão.*")

# ==========================================
# O MOTOR DE PROCESSAMENTO
# ==========================================
if arquivo_campanha is not None and processar_btn:
    try:
        with st.spinner("O Carro-Forte está conectando ao Azure..."):
            df_mestra = ler_mestra_do_azure() 
            
            nome_arquivo_completo = arquivo_campanha.name
            nome_base = nome_arquivo_completo.rsplit('.', 1)[0]
            extensao = nome_arquivo_completo.rsplit('.', 1)[1].lower()
            
            if extensao == 'csv':
                df_campanha = pd.read_csv(arquivo_campanha, sep=';', dtype=str)
                if len(df_campanha.columns) == 1:
                    arquivo_campanha.seek(0)
                    df_campanha = pd.read_csv(arquivo_campanha, sep=',', dtype=str)
            else:
                df_campanha = pd.read_excel(arquivo_campanha, dtype=str)
            
            colunas_alvo = ['VALOR_DO_REGISTRO', 'WhatsAppdoContato', 'Telefone', 'Celular']
            col_tel = next((col for col in colunas_alvo if col in df_campanha.columns), df_campanha.columns[0])
            
            # SNAPSHOT: Fotografa o esquema original para devolver exatamente igual
            colunas_originais = df_campanha.columns.tolist()
            
            # A Catraca Eletrônica
            df_aprovados, df_rejeitados = aprovar_campanha(df_campanha, df_mestra, col_tel)
            
            # O CARIMBO DE METADADOS (Blindagem para o BI)
            df_aprovados['Carteira'] = nome_base
            df_aprovados['Data_Filtragem'] = hoje_str
            if 'Status_Atual' not in df_aprovados.columns:
                df_aprovados['Status_Atual'] = 'APROVADO'
                
            df_rejeitados['Carteira'] = nome_base
            df_rejeitados['Data_Filtragem'] = hoje_str
            if 'Status_Atual' not in df_rejeitados.columns:
                df_rejeitados['Status_Atual'] = 'RETIDO'
            
            # Atualização Invisível do Azure
            _bi = [col_tel, 'Status_Atual', 'Data_Filtragem', 'Carteira']
            df_bi_hoje = pd.concat([
                df_aprovados[_bi].rename(columns={col_tel: 'WhatsAppdoContato'}),
                df_rejeitados[_bi].rename(columns={col_tel: 'WhatsAppdoContato'})
            ], ignore_index=True)
            atualizar_historico_bi(df_bi_hoje)
            
            # Divisão de Categorias
            df_leads = df_rejeitados[df_rejeitados['Status_Atual'] == 'GELADEIRA (Avaliar Comercial)'] if 'Status_Atual' in df_rejeitados.columns else pd.DataFrame()
            df_puro_retidos = df_rejeitados[df_rejeitados['Status_Atual'] != 'GELADEIRA (Avaliar Comercial)'] if 'Status_Atual' in df_rejeitados.columns else df_rejeitados
            
            vol_total = len(df_campanha)
            vol_aprovados = len(df_aprovados)
            vol_economia = len(df_puro_retidos)
            vol_uras = len(df_leads)
            
            # ==========================================
            # IDEMPOTÊNCIA DE SESSÃO (Proteção Contra Fragmentos)
            # ==========================================
            hora_processamento = datetime.now().strftime('%H:%M:%S')
            chave_sessao_unica = f"{nome_base} ({hora_processamento})"
            
            st.session_state.historico_diario[chave_sessao_unica] = {
                'Total': vol_total,
                'Aprovados': vol_aprovados,
                'Retidos': vol_economia,
                'URAs': vol_uras,
                'Retidos_Totais': vol_economia + vol_uras,
                'Economia': (vol_economia + vol_uras) * CUSTO_HSM
            }
            
            # Preparação de Buffers para Download...
            # O Filtro Absoluto: Devolve apenas as colunas que vieram no arquivo original
            colunas_para_devolver = [c for c in colunas_originais if c in df_aprovados.columns]
            df_aprovados_cliente = df_aprovados[colunas_para_devolver]
            
            buf_aprov = io.BytesIO()
            
            if extensao == 'csv':
                df_aprovados_cliente.to_csv(buf_aprov, sep=';', index=False, encoding='utf-8-sig')
                st.session_state.mime_aprov, st.session_state.nome_arq_aprov = "text/csv", f"{nome_base}_Aprovados.csv"
            else:
                with pd.ExcelWriter(buf_aprov, engine='xlsxwriter') as writer:
                    df_aprovados_cliente.to_excel(writer, index=False, sheet_name='Aprovados')
                st.session_state.mime_aprov, st.session_state.nome_arq_aprov = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{nome_base}_Aprovados.xlsx"
            st.session_state.buffer_aprovados = buf_aprov.getvalue()
            
            buf_ret = io.BytesIO()
            if extensao == 'csv':
                df_rejeitados.to_csv(buf_ret, sep=';', index=False, encoding='utf-8-sig')
                st.session_state.mime_ret, st.session_state.nome_arq_ret = "text/csv", f"{nome_base}_Retidos.csv"
            else:
                with pd.ExcelWriter(buf_ret, engine='xlsxwriter') as writer:
                    if not df_leads.empty: df_leads.to_excel(writer, index=False, sheet_name='1_Leads_Comerciais')
                    if not df_puro_retidos.empty: df_puro_retidos.to_excel(writer, index=False, sheet_name='2_Retidos_Economia')
                    if df_leads.empty and df_puro_retidos.empty: pd.DataFrame({'Aviso': ['100% aprovado.']}).to_excel(writer, index=False)
                st.session_state.mime_ret, st.session_state.nome_arq_ret = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{nome_base}_Retidos.xlsx"
            st.session_state.buffer_retidos = buf_ret.getvalue()
            
            # Salvamos a auditoria das top 50 recusas
            st.session_state.df_auditoria = df_rejeitados.head(50) if not df_rejeitados.empty else pd.DataFrame()
            st.session_state.nome_arquivo_atual = chave_sessao_unica # <--- PONTEIRO CORRIGIDO
            st.session_state.processamento_concluido = True
            
            st.balloons() # O toque Premium de UX!
            st.rerun() # Dá refresh para atualizar o quadro de resumo no topo
            
    except Exception as e:
        st.error(f"Erro na operação: {e}")

# # ==================================================
# # A VITRINE EXECUTIVA (Renderização Gráfica em Grid)
# # ==================================================
# if st.session_state.processamento_concluido:
#     nome_atual = st.session_state.nome_arquivo_atual
#     dados_atuais = st.session_state.historico_diario[nome_atual]
    
#     st.markdown("---") # Linha horizontal divisória
#     st.markdown(f"## 📊 Análise da Campanha: `{nome_atual}`")
    
#     # 1. Painel de ROI da Campanha Atual (Em Cartões)
#     c1, c2, c3, c4 = st.columns(4)
#     with c1:
#         with st.container(border=True):
#             st.metric("Analisados", dados_atuais['Total'])
#     with c2:
#         with st.container(border=True):
#             st.metric("Aprovados (Disparo)", dados_atuais['Aprovados'])
#     with c3:
#         with st.container(border=True):
#             st.metric("Bloqueios Táticos", dados_atuais['Retidos_Totais'])
#     with c4:
#         with st.container(border=True):
#             st.metric("Economia Gerada (R$)", f"R$ {dados_atuais['Economia']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    
#     # 2. A Matriz de 3 Colunas com Fronteiras Individuais
#     col_donut_atual, col_donut_acumulado, col_acoes = st.columns([1, 1, 1])
    
#     # --- COLUNA 1: Donut Atual ---
#     with col_donut_atual:
#         with st.container(border=True):
#             labels = ['Aprovados (Verdes)', 'Economia (Geladeira/Freezer)', 'URAs (Leads Comerciais)']
#             valores_atual = [dados_atuais['Aprovados'], dados_atuais['Retidos'], dados_atuais['URAs']]
#             cores = ['#2ECC71', '#E74C3C', '#F1C40F']
            
#             fig_atual = px.pie(values=valores_atual, names=labels, hole=0.5, color=labels, color_discrete_map={l: c for l, c in zip(labels, cores)})
#             fig_atual.update_layout(title_text="Saúde da Campanha (Lote Atual)", margin=dict(t=40, b=0, l=0, r=0), height=280)
#             st.plotly_chart(fig_atual, width="stretch")

#     # --- COLUNA 2: Donut Acumulado do Dia ---
#     with col_donut_acumulado:
#         with st.container(border=True):
#             tot_aprov = sum(d['Aprovados'] for d in st.session_state.historico_diario.values())
#             tot_retid = sum(d['Retidos'] for d in st.session_state.historico_diario.values())
#             tot_uras  = sum(d['URAs'] for d in st.session_state.historico_diario.values())
            
#             valores_acumulados = [tot_aprov, tot_retid, tot_uras]
            
#             fig_acumulado = px.pie(values=valores_acumulados, names=labels, hole=0.5, color=labels, color_discrete_map={l: c for l, c in zip(labels, cores)})
#             fig_acumulado.update_layout(title_text="Saúde Diária (Acumulado Geral)", margin=dict(t=40, b=0, l=0, r=0), height=280)
#             st.plotly_chart(fig_acumulado, width="stretch")

#     # --- COLUNA 3: Centro de Comando (Botões + Auditoria) ---
#     with col_acoes:
#         with st.container(border=True):
#             st.markdown("<br>", unsafe_allow_html=True)
#             st.success("✅ **Esteira Concluída. Arquivos Prontos.**")
#             st.download_button("🚀 Baixar Aprovados (Disparo HSM)", data=st.session_state.buffer_aprovados, file_name=st.session_state.nome_arq_aprov, mime=st.session_state.mime_aprov, width="stretch")
#             st.download_button("⚠️ Baixar Base Rejeitada (Auditoria)", data=st.session_state.buffer_retidos, file_name=st.session_state.nome_arq_ret, mime=st.session_state.mime_ret, width="stretch")
            
#             st.markdown("<br>", unsafe_allow_html=True)
#             if not st.session_state.df_auditoria.empty:
#                 with st.expander("🔍 Auditoria Dinâmica (Top 50 Bloqueios)"):
#                     colunas_ver = ['WhatsAppdoContato', 'Status_Atual'] if 'Status_Atual' in st.session_state.df_auditoria.columns else st.session_state.df_auditoria.columns
#                     st.dataframe(st.session_state.df_auditoria[colunas_ver], width='stretch')

# # ==================================================
# # A TABELA DO LIVRO-RAZÃO DIÁRIO COM LINHA DE TOTAL
# # ==================================================
# if st.session_state.historico_diario:
#     st.markdown("---")
#     st.markdown("### 📋 Histórico de Processamento da Sessão")
#     df_historico = pd.DataFrame.from_dict(st.session_state.historico_diario, orient='index')
#     df_historico.index.name = 'Campanha_Processada'
#     df_historico = df_historico.reset_index()
    
#     # 1. Cálculos da Linha de Totais
#     total_linha = pd.DataFrame({
#         'Campanha_Processada': ['TOTAL ACUMULADO'],
#         'Total': [df_historico['Total'].sum()],
#         'Aprovados': [df_historico['Aprovados'].sum()],
#         'Retidos': [df_historico['Retidos'].sum()],
#         'URAs': [df_historico['URAs'].sum()],
#         'Retidos_Totais': [df_historico['Retidos_Totais'].sum()],
#         'Economia': [df_historico['Economia'].sum()]
#     })
    
#     # 2. Concatena a linha de totais ao fundo da tabela
#     df_historico_com_total = pd.concat([df_historico, total_linha], ignore_index=True)
    
#     # 3. Formatação visual da moeda na tabela
#     df_historico_com_total['Economia'] = df_historico_com_total['Economia'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    
#     # 4. Renderização
#     st.dataframe(df_historico_com_total, width='stretch')
# ==================================================
# A VITRINE EXECUTIVA (Renderização Gráfica em Grid)
# ==================================================
if st.session_state.processamento_concluido:
    nome_atual = st.session_state.nome_arquivo_atual
    dados_atuais = st.session_state.historico_diario[nome_atual]
    
    st.markdown("---") 
    st.markdown(f"## 📊 Análise da Campanha: `{nome_atual}`")
    
    # ==================================================
    # NOVA BARRA DE AÇÕES (Downloads colados no Upload)
    # ==================================================
    st.success("✅ **Esteira Concluída. Arquivos higienizados prontos para uso:**")
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        st.download_button("🚀 Baixar Aprovados (Disparo HSM)", data=st.session_state.buffer_aprovados, file_name=st.session_state.nome_arq_aprov, mime=st.session_state.mime_aprov, width="stretch")
    with col_btn2:
        st.download_button("⚠️ Baixar Base Rejeitada (Auditoria)", data=st.session_state.buffer_retidos, file_name=st.session_state.nome_arq_ret, mime=st.session_state.mime_ret, width="stretch")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ==================================================
    # 1. Painel de ROI da Campanha Atual (Em Cartões)
    # ==================================================
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        with st.container(border=True):
            st.metric("Analisados", dados_atuais['Total'])
    with c2:
        with st.container(border=True):
            st.metric("Aprovados (Disparo)", dados_atuais['Aprovados'])
    with c3:
        with st.container(border=True):
            st.metric("Bloqueios Táticos", dados_atuais['Retidos_Totais'])
    with c4:
        with st.container(border=True):
            st.metric("Economia Gerada (R$)", f"R$ {dados_atuais['Economia']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    
    # ==================================================
    # 2. A Matriz Gráfica (Agora com 2 colunas largas)
    # ==================================================
    col_donut_atual, col_donut_acumulado = st.columns([1, 1])
    
    labels = ['Aprovados (Verdes)', 'Economia (Geladeira/Freezer)', 'URAs (Leads Comerciais)']
    cores = ['#2ECC71', '#E74C3C', '#F1C40F']
    
    # --- COLUNA 1: Donut Atual ---
    with col_donut_atual:
        with st.container(border=True):
            valores_atual = [dados_atuais['Aprovados'], dados_atuais['Retidos'], dados_atuais['URAs']]
            
            fig_atual = px.pie(values=valores_atual, names=labels, hole=0.5, color=labels, color_discrete_map={l: c for l, c in zip(labels, cores)})
            fig_atual.update_layout(title_text="Saúde da Campanha (Lote Atual)", margin=dict(t=40, b=0, l=0, r=0), height=300)
            st.plotly_chart(fig_atual, width="stretch")

    # --- COLUNA 2: Donut Acumulado do Dia ---
    with col_donut_acumulado:
        with st.container(border=True):
            tot_aprov = sum(d['Aprovados'] for d in st.session_state.historico_diario.values())
            tot_retid = sum(d['Retidos'] for d in st.session_state.historico_diario.values())
            tot_uras  = sum(d['URAs'] for d in st.session_state.historico_diario.values())
            valores_acumulados = [tot_aprov, tot_retid, tot_uras]
            
            fig_acumulado = px.pie(values=valores_acumulados, names=labels, hole=0.5, color=labels, color_discrete_map={l: c for l, c in zip(labels, cores)})
            fig_acumulado.update_layout(title_text="Saúde Diária (Acumulado Geral)", margin=dict(t=40, b=0, l=0, r=0), height=300)
            st.plotly_chart(fig_acumulado, width="stretch")

    # ==================================================
    # 3. Auditoria Dinâmica (Full Width abaixo dos gráficos)
    # ==================================================
    if not st.session_state.df_auditoria.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔍 Auditoria Dinâmica (Amostra de 50 Bloqueios)"):
            colunas_ver = ['WhatsAppdoContato', 'Status_Atual'] if 'Status_Atual' in st.session_state.df_auditoria.columns else st.session_state.df_auditoria.columns
            st.dataframe(st.session_state.df_auditoria[colunas_ver], width="stretch")

# ==================================================
# A TABELA DO LIVRO-RAZÃO DIÁRIO COM LINHA DE TOTAL
# ==================================================
if st.session_state.historico_diario:
    st.markdown("---")
    st.markdown("### 📋 Histórico de Processamento da Sessão")
    df_historico = pd.DataFrame.from_dict(st.session_state.historico_diario, orient='index')
    df_historico.index.name = 'Campanha_Processada'
    df_historico = df_historico.reset_index()
    
    total_linha = pd.DataFrame({
        'Campanha_Processada': ['TOTAL ACUMULADO'],
        'Total': [df_historico['Total'].sum()],
        'Aprovados': [df_historico['Aprovados'].sum()],
        'Retidos': [df_historico['Retidos'].sum()],
        'URAs': [df_historico['URAs'].sum()],
        'Retidos_Totais': [df_historico['Retidos_Totais'].sum()],
        'Economia': [df_historico['Economia'].sum()]
    })
    
    df_historico_com_total = pd.concat([df_historico, total_linha], ignore_index=True)
    df_historico_com_total['Economia'] = df_historico_com_total['Economia'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    
    st.dataframe(df_historico_com_total, width="stretch")
