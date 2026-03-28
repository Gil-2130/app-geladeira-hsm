# Arquivo: modulos/regras.py
# Função: O Fiscal Alfandegário (Motor de Regras)

import pandas as pd
import numpy as np

def processar_carga_inicial(df):
    """
    Recebe o DataFrame bruto, aplica as regras de higienização
    e retorna o DataFrame Mestre consolidado.
    """
    # 1. Integridade: Limpeza de espaços e padronização (De-Para)
    df['WhatsAppdoContato'] = df['WhatsAppdoContato'].astype(str).str.strip()
    df['Envio'] = pd.to_datetime(df['Envio'])
    df['TeveRetorno'] = df['TeveRetorno'].str.upper().str.strip()

    # 2. Ordenação Cronológica (Para a lógica fluir corretamente)
    df = df.sort_values(by=['WhatsAppdoContato', 'Envio'])

    # 3. CTEs em Memória (Isolando a última interação e contando falhas)
    df_recente = df.drop_duplicates(subset=['WhatsAppdoContato'], keep='last').copy()
    
    # Pega apenas as duas últimas interações para performance de contagem
    df_ultimos_dois = df.groupby('WhatsAppdoContato').tail(2)
    falhas = df_ultimos_dois[df_ultimos_dois['TeveRetorno'] == 'N'].groupby('WhatsAppdoContato').size().reset_index(name='Qtd_Falhas_Consecutivas')

    # 4. Cruzamento (Equivalente ao OUTER APPLY)
    df_mestra = pd.merge(df_recente, falhas, on='WhatsAppdoContato', how='left')
    
    # 5. Regra de Negócio: Se a última interação foi 'S', zera as falhas
    df_mestra.loc[df_mestra['TeveRetorno'] == 'S', 'Qtd_Falhas_Consecutivas'] = 0
    df_mestra['Qtd_Falhas_Consecutivas'] = df_mestra['Qtd_Falhas_Consecutivas'].fillna(0).astype(int)

    # 6. Zonas Térmicas (Geladeira, Freezer, Ativo)
    hoje = pd.to_datetime('today')
    df_mestra['Dias_Desde_Envio'] = (hoje - df_mestra['Envio']).dt.days

    condicoes = [
        df_mestra['Qtd_Falhas_Consecutivas'] >= 2,
        (df_mestra['Qtd_Falhas_Consecutivas'] == 1) & (df_mestra['Dias_Desde_Envio'] <= 7),
        (df_mestra['Qtd_Falhas_Consecutivas'] == 1) & (df_mestra['Dias_Desde_Envio'] > 7)
    ]
    escolhas = ['FREEZER (Definitivo)', 'GELADEIRA (Temp 7 Dias)', 'ATIVO (Repescagem Liberta)']
    df_mestra['Status_Atual'] = np.select(condicoes, escolhas, default='ATIVO')

    # 7. Formatação de Saída
    df_mestra = df_mestra.rename(columns={'Envio': 'Data_Ultimo_Disparo'})
    return df_mestra[['WhatsAppdoContato', 'Data_Ultimo_Disparo', 'Qtd_Falhas_Consecutivas', 'Status_Atual']]
