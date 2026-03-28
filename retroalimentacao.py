# Arquivo: modulos/retroalimentacao.py
# Função: O Fiscal do Fechamento (Motor de UPSERT)

import pandas as pd
import numpy as np
# Importamos o seu normalizador blindado que você já usa no filtro
from modulos.filtro import normalizar_telefone 

def processar_retornos(df_mestra, df_retornos, col_tel_retorno='WhatsAppdoContato'):
    """
    Realiza o UPSERT cruzando a base mestra com a planilha de retornos do dia.
    """
    # 1. Integridade: Normalização de Chaves Primárias (A sua blindagem)
    df_mestra['WhatsAppdoContato'] = normalizar_telefone(df_mestra['WhatsAppdoContato'])
    df_retornos[col_tel_retorno] = normalizar_telefone(df_retornos[col_tel_retorno])
    
    # Limpeza da coluna de retorno (S/N) e conversão de Data
    df_retornos['TeveRetorno'] = df_retornos['TeveRetorno'].str.upper().str.strip()
    df_retornos['DataEnvio'] = pd.to_datetime(df_retornos['DataEnvio'])

    # 2. O Cruzamento de Lote (FULL OUTER JOIN)
    # Isso garante que mantemos quem já estava na Mestra e adicionamos novos Leads
    df_atualizado = pd.merge(
        df_mestra, 
        df_retornos[[col_tel_retorno, 'DataEnvio', 'TeveRetorno']], 
        left_on='WhatsAppdoContato', 
        right_on=col_tel_retorno, 
        how='outer'
    )
    
    # Se a PK veio vazia da Mestra (Novo Lead), preenchemos com a PK do Retorno
    df_atualizado['WhatsAppdoContato'] = df_atualizado['WhatsAppdoContato'].fillna(df_atualizado[col_tel_retorno])

    # 3. Regra de Negócio: Atualização de Data
    # Se participou da campanha (DataEnvio não é nulo), atualiza. Senão, mantém a antiga.
    df_atualizado['Data_Ultimo_Disparo'] = np.where(
        df_atualizado['DataEnvio'].notna(), 
        df_atualizado['DataEnvio'], 
        df_atualizado['Data_Ultimo_Disparo']
    )

    # 4. Regra de Negócio: Contagem de Falhas (O Coração da Geladeira)
    condicoes_falhas = [
        df_atualizado['TeveRetorno'] == 'S', # Respondeu? Zera tudo.
        df_atualizado['TeveRetorno'] == 'N'  # Não respondeu? Soma 1 ao histórico.
    ]
    escolhas_falhas = [
        0, 
        df_atualizado['Qtd_Falhas_Consecutivas'].fillna(0) + 1
    ]
    # Se não participou da campanha hoje (TeveRetorno é nulo), mantém a quantidade de falhas que já tinha
    df_atualizado['Qtd_Falhas_Consecutivas'] = np.select(
        condicoes_falhas, 
        escolhas_falhas, 
        default=df_atualizado['Qtd_Falhas_Consecutivas']
    )

    # 5. Aplicação das Zonas Térmicas com o novo Status
    hoje = pd.to_datetime('today')
    df_atualizado['Dias_Desde_Envio'] = (hoje - pd.to_datetime(df_atualizado['Data_Ultimo_Disparo'])).dt.days

    condicoes_status = [
        df_atualizado['Qtd_Falhas_Consecutivas'] >= 2,
        (df_atualizado['Qtd_Falhas_Consecutivas'] == 1) & (df_atualizado['Dias_Desde_Envio'] <= 7),
        (df_atualizado['Qtd_Falhas_Consecutivas'] == 1) & (df_atualizado['Dias_Desde_Envio'] > 7)
    ]
    escolhas_status = ['FREEZER (Definitivo)', 'GELADEIRA (Temp 7 Dias)', 'ATIVO (Repescagem Liberta)']
    df_atualizado['Status_Atual'] = np.select(condicoes_status, escolhas_status, default='ATIVO')

    # 6. Formatação e Limpeza de Saída
    return df_atualizado[['WhatsAppdoContato', 'Data_Ultimo_Disparo', 'Qtd_Falhas_Consecutivas', 'Status_Atual']].copy()