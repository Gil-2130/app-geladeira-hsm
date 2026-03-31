# Arquivo: modulos/retroalimentacao.py
# Função: O Fiscal de UPSERT integrado com Análise de Sentimento

import pandas as pd
import numpy as np
from modulos.filtro import normalizar_telefone
from modulos.sentimento import classificar_mensagens # Importamos o novo Fiscal Lexicógrafo

def processar_retornos(df_mestra, df_retornos, col_tel_retorno='WhatsAppdoContato', col_msg='primeiramensagem'):
    """
    Realiza o UPSERT cruzando o Cérebro com os retornos recentes, aplicando Análise de Sentimento.
    """
    # 1. Integridade: Normalização de Chaves Primárias
    df_mestra['WhatsAppdoContato'] = normalizar_telefone(df_mestra['WhatsAppdoContato'])
    df_retornos[col_tel_retorno] = normalizar_telefone(df_retornos[col_tel_retorno])
    
    # Limpeza básica do Retorno 'S/N'
    df_retornos['TeveRetorno'] = df_retornos['TeveRetorno'].str.upper().str.strip()
    df_retornos['DataEnvio'] = pd.to_datetime(df_retornos['DataEnvio'])

    # =========================================================
    # NOVO: BLINDAGEM CRONOLÓGICA (O TRITURADOR DE HISTÓRICO)
    # Garante que, se o mesmo número vier 5 vezes na planilha,
    # o sistema só olhará para o dia mais recente.
    # =========================================================
    df_retornos = df_retornos.sort_values(by=[col_tel_retorno, 'DataEnvio'])
    df_retornos = df_retornos.drop_duplicates(subset=[col_tel_retorno], keep='last')

    # =========================================================
    # 2. O FISCAL LEXICÓGRAFO ENTRA EM AÇÃO AQUI (Antes do Merge)
    # Avalia se quem respondeu 'S' disse algo improdutivo
    # =========================================================
    if col_msg in df_retornos.columns:
        df_retornos = classificar_mensagens(df_retornos, col_msg)
    else:
        # Se a origem de dados vier sem a coluna de mensagem, assume-se Produtivo por segurança
        df_retornos['Sentimento_Calculado'] = 'PRODUTIVO'

    # 3. O Cruzamento de Lote (FULL OUTER JOIN - UPSERT)
    colunas_para_merge = [col_tel_retorno, 'DataEnvio', 'TeveRetorno', 'Sentimento_Calculado']
    df_atualizado = pd.merge(
        df_mestra, 
        df_retornos[colunas_para_merge], 
        left_on='WhatsAppdoContato', 
        right_on=col_tel_retorno, 
        how='outer'
    )
    
    # Preenchimento de Chaves para Novos Leads
    df_atualizado['WhatsAppdoContato'] = df_atualizado['WhatsAppdoContato'].fillna(df_atualizado[col_tel_retorno])

    # 4. Regras de Negócio: Atualização de Data
    df_atualizado['Data_Ultimo_Disparo'] = np.where(
        df_atualizado['DataEnvio'].notna(), 
        df_atualizado['DataEnvio'], 
        df_atualizado['Data_Ultimo_Disparo']
    )

    # 5. Regras de Negócio: A Guilhotina de Falhas e Sentimento
    # Aqui unimos as falhas comuns de 'N' com a Blacklist de palavrões/URA
    condicoes_falhas = [
        df_atualizado['Sentimento_Calculado'] == 'IMPRODUTIVO (DETRATOR)', # Detrator: Falhas vão para 99
        df_atualizado['Sentimento_Calculado'] == 'URA (LEAD B2B)',       # URA: Congelado comercialmente (99 falhas tbm)
        (df_atualizado['TeveRetorno'] == 'S') & (df_atualizado['Sentimento_Calculado'] == 'PRODUTIVO'), # Sucesso real: Zera falhas
        df_atualizado['TeveRetorno'] == 'N'                              # Ignorou: Soma +1 falha normal
    ]
    
    escolhas_falhas = [
        99, 
        99, 
        0, 
        df_atualizado['Qtd_Falhas_Consecutivas'].fillna(0) + 1
    ]
    
    df_atualizado['Qtd_Falhas_Consecutivas'] = np.select(
        condicoes_falhas, 
        escolhas_falhas, 
        default=df_atualizado['Qtd_Falhas_Consecutivas']
    )

    # 6. Zonas Térmicas (O Carimbo Final)
    hoje = pd.to_datetime('today')
    df_atualizado['Dias_Desde_Envio'] = (hoje - pd.to_datetime(df_atualizado['Data_Ultimo_Disparo'])).dt.days

    condicoes_status = [
        (df_atualizado['Qtd_Falhas_Consecutivas'] == 99) & (df_atualizado['Sentimento_Calculado'] == 'URA (LEAD B2B)'),
        (df_atualizado['Qtd_Falhas_Consecutivas'] == 99),
        df_atualizado['Qtd_Falhas_Consecutivas'] >= 2,
        (df_atualizado['Qtd_Falhas_Consecutivas'] == 1) & (df_atualizado['Dias_Desde_Envio'] <= 7),
        (df_atualizado['Qtd_Falhas_Consecutivas'] == 1) & (df_atualizado['Dias_Desde_Envio'] > 7)
    ]
    
    escolhas_status = [
        'GELADEIRA (Avaliar Comercial)',
        'FREEZER (Blacklist)',
        'FREEZER (Definitivo)', 
        'GELADEIRA (Temp 7 Dias)', 
        'ATIVO (Repescagem Liberta)'
    ]
    
    df_atualizado['Status_Atual'] = np.select(condicoes_status, escolhas_status, default='ATIVO')

    # 7. Formatação de Saída para o Azure
    return df_atualizado[['WhatsAppdoContato', 'Data_Ultimo_Disparo', 'Qtd_Falhas_Consecutivas', 'Status_Atual']].copy()
