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
