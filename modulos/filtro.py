# Arquivo: modulos/filtro.py
# Função: A Catraca Eletrônica (Filtro de Campanha)

import pandas as pd
import numpy as np # Adicionar no topo do arquivo
from datetime import datetime

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


def aprovar_campanha(df_campanha, df_mestra, col_tel_campanha):
    """
    O Fiscal da Catraca: Cruza as bases, PRESERVA as colunas originais e CARIMBA a data.
    """
    # 1. Normalizamos os telefones para o cruzamento sem alterar a coluna original
    df_campanha['Chave_Join'] = df_campanha[col_tel_campanha].astype(str).str.replace(r'\D', '', regex=True)
    df_mestra['Chave_Join'] = df_mestra['WhatsAppdoContato'].astype(str).str.replace(r'\D', '', regex=True)
    
    # 2. O Cruzamento (LEFT JOIN). Mantém TUDO que o cliente enviou e traz apenas o Status do Cérebro
    df_resultado = pd.merge(
        df_campanha, 
        df_mestra[['Chave_Join', 'Status_Atual']], 
        on='Chave_Join', 
        how='left'
    )
    
    # Se o cliente não estava no Cérebro, ele é novo
    df_resultado['Status_Atual'] = df_resultado['Status_Atual'].fillna('NOVO LEAD')
    
    # 3. O Carimbo de Data (A sua ideia brilhante para o BI)
    # Extrai exatamente a data de hoje (ex: 2026-03-31)
    df_resultado['Data_Filtragem'] = datetime.today().strftime('%Y-%m-%d')
    
    # Limpamos a chave temporária
    df_resultado = df_resultado.drop(columns=['Chave_Join'])
    
    # 4. A Separação das Portas (Verde vs Amarela)
    condicao_aprovados = df_resultado['Status_Atual'].isin(['ATIVO', 'NOVO LEAD', 'ATIVO (Repescagem Liberta)'])
    
    df_aprovados = df_resultado[condicao_aprovados]
    df_rejeitados = df_resultado[~condicao_aprovados]
    
    return df_aprovados, df_rejeitados
