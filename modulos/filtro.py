# # Arquivo: modulos/filtro.py
# # Função: A Catraca Eletrônica (Filtro de Campanha)

# import pandas as pd
# import numpy as np # Adicionar no topo do arquivo
# from datetime import datetime

# def normalizar_telefone(serie):
#     """
#     Remove decimais, não-dígitos e o DDI (55) garantindo chaves universais.
#     """
#     s = serie.astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
    
#     # O Pulo do Gato (Regex Lookahead): 
#     # Se começar por '55' (^) e for seguido por exatamente 10 ou 11 números até o fim ($), remova o '55'.
#     s = s.str.replace(r'^55(?=\d{10,11}$)', '', regex=True)
#     return s

# def aprovar_campanha(df_campanha, df_mestra, col_tel_campanha):
#     """O Fiscal da Catraca: Com a Régua de Validação de Tamanho restituída."""
    
#     # 1. Normalização Blindada
#     df_campanha['Chave_Join'] = normalizar_telefone(df_campanha[col_tel_campanha])
#     df_mestra['Chave_Join'] = normalizar_telefone(df_mestra['WhatsAppdoContato'])
    
#     # =========================================================
#     # 2. A RÉGUA DO FISCAL (Validação Cruzada de Tamanho)
#     # Exige entre 10 e 15 dígitos (DDD + Número, com ou sem DDI 55)
#     # =========================================================
#     mascara_tamanho_valido = df_campanha['Chave_Join'].str.len().between(10, 15)
    
#     # Separa quem passou na régua e quem reprovou (Lixo)
#     df_campanha_valida = df_campanha[mascara_tamanho_valido].copy()
    
#     df_lixo_tamanho = df_campanha[~mascara_tamanho_valido].copy()
#     if not df_lixo_tamanho.empty:
#         df_lixo_tamanho['Status_Atual'] = 'INVÁLIDO (Erro de Digitação/Tamanho)'
#         df_lixo_tamanho['Data_Filtragem'] = datetime.today().strftime('%Y-%m-%d')
#         df_lixo_tamanho[col_tel_campanha] = df_lixo_tamanho[col_tel_campanha].astype(str)
#         df_lixo_tamanho = df_lixo_tamanho.drop(columns=['Chave_Join'])

#     # 3. O Cruzamento (Apenas com os números que passaram na régua)
#     df_resultado = pd.merge(
#         df_campanha_valida, 
#         df_mestra[['Chave_Join', 'Status_Atual']], 
#         on='Chave_Join', 
#         how='left'
#     )
    
#     df_resultado['Status_Atual'] = df_resultado['Status_Atual'].fillna('NOVO LEAD')
#     df_resultado['Data_Filtragem'] = datetime.today().strftime('%Y-%m-%d')
#     df_resultado = df_resultado.drop(columns=['Chave_Join'])
    
#     df_resultado[col_tel_campanha] = df_resultado[col_tel_campanha].astype(str)
    
#     # 4. Particionamento
#     condicao_aprovados = df_resultado['Status_Atual'].isin(['ATIVO', 'NOVO LEAD', 'ATIVO (Repescagem Liberta)'])
    
#     df_aprovados = df_resultado[condicao_aprovados]
#     df_rejeitados = df_resultado[~condicao_aprovados]
    
#     # 5. Reintegra os números inválidos ao montante de rejeitados (para a porta amarela)
#     if not df_lixo_tamanho.empty:
#         df_rejeitados = pd.concat([df_rejeitados, df_lixo_tamanho], ignore_index=True)
    
#     return df_aprovados, df_rejeitados
# Arquivo: modulos/filtro.py
# Função: A Catraca Eletrônica (Filtro de Campanha)

import pandas as pd
import numpy as np # Adicionar no topo do arquivo

def normalizar_telefone(serie_telefone):
    """
    UDF de Limpeza: Remove não-números e padroniza o tamanho da string
    baseado na regra de negócio (Tamanho 13 -> 11 dir, Tamanho 12 -> 10 dir).
    """
    # 1. Remove qualquer coisa que não seja número (espaços, +, -, parênteses)
    serie_limpa = serie_telefone.astype(str).str.replace(r'\D', '', regex=True)
    
    # 2. Aplica a sua regra de corte (RIGHT 11 ou RIGHT 10)
    condicoes = [
        serie_limpa.str.len() == 13,
        serie_limpa.str.len() == 12
    ]
    escolhas = [
        serie_limpa.str[-11:], # Pega os 11 da direita
        serie_limpa.str[-10:]  # Pega os 10 da direita
    ]
    
    # Retorna a série padronizada
    return np.select(condicoes, escolhas, default=serie_limpa)


def aprovar_campanha(df_campanha, df_mestra, coluna_telefone='WhatsAppdoContato'):
    """
    Cruza a lista da campanha com a base mestra (OUTER APPLY).
    Retorna dois DataFrames: Aprovados e Rejeitados.
    """
    # 1. Integridade: Padronização para o JOIN
    df_campanha[coluna_telefone] = normalizar_telefone(df_campanha[coluna_telefone])
    df_mestra['WhatsAppdoContato'] = normalizar_telefone(df_mestra['WhatsAppdoContato'])

    # 2. O Cruzamento (LEFT JOIN nativo)
    df_cruzamento = pd.merge(
        df_campanha, 
        df_mestra[['WhatsAppdoContato', 'Status_Atual']], 
        left_on=coluna_telefone, 
        right_on='WhatsAppdoContato', 
        how='left'
    )

    # 3. Tratamento de Novos Leads (NULL vira NOVO LEAD)
    df_cruzamento['Status_Atual'] = df_cruzamento['Status_Atual'].fillna('NOVO LEAD (Aprovado)')

    # 4. A Peneira Lógica (Aplicando as Zonas Térmicas)
    # Mantém quem tem 'ATIVO' ou 'NOVO LEAD' no status
    condicao_aprovado = df_cruzamento['Status_Atual'].str.contains('ATIVO|NOVO LEAD', na=False)

    df_aprovados = df_cruzamento[condicao_aprovado].copy()
    df_rejeitados = df_cruzamento[~condicao_aprovado].copy()

    # Limpeza para exportação
    df_aprovados = df_aprovados.drop(columns=['WhatsAppdoContato_y'], errors='ignore')
    df_rejeitados = df_rejeitados.drop(columns=['WhatsAppdoContato_y'], errors='ignore')

    return df_aprovados, df_rejeitados
