# Arquivo: modulos/filtro.py
# Função: A Catraca Eletrônica (Filtro de Campanha)

import pandas as pd
import numpy as np # Adicionar no topo do arquivo
from datetime import datetime

def normalizar_telefone(serie):
    """
    Remove decimais, não-dígitos e o DDI (55) garantindo chaves universais.
    """
    s = serie.astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
    
    # O Pulo do Gato (Regex Lookahead): 
    # Se começar por '55' (^) e for seguido por exatamente 10 ou 11 números até o fim ($), remova o '55'.
    s = s.str.replace(r'^55(?=\d{10,11}$)', '', regex=True)
    return s

def aprovar_campanha(df_campanha, df_mestra, col_tel_campanha):
    """O Fiscal da Catraca: Com a Régua de Validação de Tamanho restituída."""
    
    # 1. Normalização Blindada
    df_campanha['Chave_Join'] = normalizar_telefone(df_campanha[col_tel_campanha])
    df_mestra['Chave_Join'] = normalizar_telefone(df_mestra['WhatsAppdoContato'])
    
    # =========================================================
    # 2. A RÉGUA DO FISCAL (Validação Cruzada de Tamanho)
    # Exige entre 10 e 15 dígitos (DDD + Número, com ou sem DDI 55)
    # =========================================================
    mascara_tamanho_valido = df_campanha['Chave_Join'].str.len().between(10, 15)
    
    # Separa quem passou na régua e quem reprovou (Lixo)
    df_campanha_valida = df_campanha[mascara_tamanho_valido].copy()
    
    df_lixo_tamanho = df_campanha[~mascara_tamanho_valido].copy()
    if not df_lixo_tamanho.empty:
        df_lixo_tamanho['Status_Atual'] = 'INVÁLIDO (Erro de Digitação/Tamanho)'
        df_lixo_tamanho['Data_Filtragem'] = datetime.today().strftime('%Y-%m-%d')
        df_lixo_tamanho[col_tel_campanha] = df_lixo_tamanho[col_tel_campanha].astype(str)
        df_lixo_tamanho = df_lixo_tamanho.drop(columns=['Chave_Join'])

    # 3. O Cruzamento (Apenas com os números que passaram na régua)
    df_resultado = pd.merge(
        df_campanha_valida, 
        df_mestra[['Chave_Join', 'Status_Atual']], 
        on='Chave_Join', 
        how='left'
    )
    
    df_resultado['Status_Atual'] = df_resultado['Status_Atual'].fillna('NOVO LEAD')
    df_resultado['Data_Filtragem'] = datetime.today().strftime('%Y-%m-%d')
    df_resultado = df_resultado.drop(columns=['Chave_Join'])
    
    df_resultado[col_tel_campanha] = df_resultado[col_tel_campanha].astype(str)
    
    # 4. Particionamento
    condicao_aprovados = df_resultado['Status_Atual'].isin(['ATIVO', 'NOVO LEAD', 'ATIVO (Repescagem Liberta)'])
    
    df_aprovados = df_resultado[condicao_aprovados]
    df_rejeitados = df_resultado[~condicao_aprovados]
    
    # 5. Reintegra os números inválidos ao montante de rejeitados (para a porta amarela)
    if not df_lixo_tamanho.empty:
        df_rejeitados = pd.concat([df_rejeitados, df_lixo_tamanho], ignore_index=True)
    
    return df_aprovados, df_rejeitados
