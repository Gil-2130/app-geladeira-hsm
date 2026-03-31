# Arquivo: modulos/filtro.py
# Função: A Catraca Eletrônica (Filtro de Campanha)

import pandas as pd
import numpy as np # Adicionar no topo do arquivo
from datetime import datetime

def normalizar_telefone(serie):
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
    
    """Remove decimais '.0' e extrai apenas números limpos."""
    return serie.astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)


def aprovar_campanha(df_campanha, df_mestra, col_tel_campanha):
    """O Fiscal da Catraca: Cruza as bases blindando contra notação científica."""
    # 1. Normalização Blindada
    df_campanha['Chave_Join'] = normalizar_telefone(df_campanha[col_tel_campanha])
    df_mestra['Chave_Join'] = normalizar_telefone(df_mestra['WhatsAppdoContato'])
    
    # 2. O Cruzamento (LEFT JOIN)
    df_resultado = pd.merge(
        df_campanha, 
        df_mestra[['Chave_Join', 'Status_Atual']], 
        on='Chave_Join', 
        how='left'
    )
    
    df_resultado['Status_Atual'] = df_resultado['Status_Atual'].fillna('NOVO LEAD')
    df_resultado['Data_Filtragem'] = datetime.today().strftime('%Y-%m-%d')
    df_resultado = df_resultado.drop(columns=['Chave_Join'])
    
    # 3. ANTI-NOTAÇÃO CIENTÍFICA NO EXCEL DE SAÍDA:
    # Força a coluna original a ser texto puro antes de exportar
    df_resultado[col_tel_campanha] = df_resultado[col_tel_campanha].astype(str)
    
    # 4. Particionamento
    condicao_aprovados = df_resultado['Status_Atual'].isin(['ATIVO', 'NOVO LEAD', 'ATIVO (Repescagem Liberta)'])
    
    return df_resultado[condicao_aprovados], df_resultado[~condicao_aprovados]
