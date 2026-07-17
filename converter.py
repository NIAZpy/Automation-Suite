import pandas as pd
import streamlit as st

def convert_data(input_df):
    df = input_df.copy()

    # ---------- Detect format ----------
    has_partner = '納入先' in df.columns
    has_dates = any('/' in str(col) or '-' in str(col) or str(col).isdigit() for col in df.columns)

    # ---------- Case 1: PDF (has 納入先) ----------
    if has_partner:
        col_material = next((c for c in df.columns if '材料' in c or '品番' in c), None)
        col_partner = next((c for c in df.columns if '納入先' in c), None)
        col_date = next((c for c in df.columns if '完成日' in c or '日' in c), None)
        col_qty = next((c for c in df.columns if '計画数' in c or '数量' in c or '数' in c), None)

        if not all([col_material, col_partner, col_date, col_qty]):
            st.error("❌ PDF format not recognized.")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df_clean = df[[col_material, col_partner, col_date, col_qty]].copy()
        df_clean.columns = ['材料コード', '納入先', '完成日', '数量']

        df_clean['完成日'] = pd.to_datetime(df_clean['完成日'], errors='coerce')
        df_clean['数量'] = pd.to_numeric(df_clean['数量'], errors='coerce')

        df_clean = df_clean.dropna(subset=['数量'])
        df_clean = df_clean[df_clean['数量'] > 0]

        # Output 1
        df1 = df_clean.groupby(['材料コード', '完成日']).agg({
            '数量': 'sum',
            '納入先': 'first'
        }).reset_index()
        df1.columns = ['品番', '完成日', '数量', '納入先(参考)']

        # Output 2
        df2 = df_clean.groupby(['納入先', '完成日']).agg({
            '材料コード': lambda x: ', '.join(x.unique()),
            '数量': 'sum'
        }).reset_index()
        df2.columns = ['協力企業', '完成日', '品番(複数)', '数量合計']

        # Output 3
        df3 = df_clean.groupby(['完成日']).agg({
            '材料コード': lambda x: ', '.join(x.unique()),
            '数量': 'sum'
        }).reset_index()
        df3.columns = ['完成日', '品番(複数)', '数量合計']
        df3.insert(0, 'プレス/シフト', '全プレス(PDF)')

    # ---------- Case 2: Excel (+29 or any date columns) ----------
    elif has_dates:

        # Identify 品番 column
        id_col = None
        for c in df.columns:
            if '品番' in c:
                id_col = c
                break
        if id_col is None:
            id_col = df.columns[0]  # fallback

        # All other columns treated as dates
        value_cols = [c for c in df.columns if c != id_col]

        # Melt
        df_melted = df.melt(id_vars=[id_col], value_vars=value_cols,
                            var_name='完成日', value_name='数量')

        df_melted = df_melted[df_melted['数量'] > 0].dropna()

        # SAFE date parser (Cloud + Local)
        def safe_date(x):
            try:
                return pd.to_datetime(x, errors='coerce')
            except:
                try:
                    return pd.to_datetime(float(x), unit='d', origin='1899-12-30')
                except:
                    return pd.NaT

        df_melted['完成日'] = df_melted['完成日'].apply(safe_date)
        df_melted = df_melted.dropna(subset=['完成日'])

        # Output 1
        df1 = df_melted.groupby([id_col, '完成日']).agg({'数量': 'sum'}).reset_index()
        df1.columns = ['品番', '完成日', '数量']

        # Output 2
        df2 = df_melted.groupby([id_col, '完成日']).agg({'数量': 'sum'}).reset_index()
        df2.columns = ['協力企業(品番)', '完成日', '数量']

        # Output 3
        df3 = df_melted.groupby(['完成日']).agg({
            id_col: lambda x: ', '.join(x.unique()),
            '数量': 'sum'
        }).reset_index()
        df3.columns = ['完成日', '品番(複数)', '数量合計']
        df3.insert(0, 'プレス/シフト', '全プレス(Excel)')

    # ---------- No format matched ----------
    else:
        st.error("❌ Excel format not recognized.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # ---------- Format dates ----------
    for df_out in [df1, df2, df3]:
        if '完成日' in df_out.columns:
            df_out['完成日'] = df_out['完成日'].dt.strftime('%Y-%m-%d')

    return df1, df2, df3
