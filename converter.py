import pandas as pd
import streamlit as st

def convert_data(input_df):
    """
    Converts input DataFrame (from PDF or '+29' Excel) into 3 Japanese-labeled outputs:
    1. 材料別発注リスト (Material-wise order list)
    2. 協力企業納入予定表 (Partner delivery schedule)
    3. 社内プレス入荷予定表 (Internal press inbound schedule)
    """
    df = input_df.copy()

    # ---------- Detect format ----------
    has_partner = '納入先' in df.columns
    has_dates = any(col in df.columns for col in ['07/13', '07/14', '07/15', '07/16', '07/17'])

    # ---------- Normalize data ----------
    if has_partner:
        # --- Case 1: PDF (has 納入先) ---
        col_material = next((c for c in df.columns if '材料' in c or '品番' in c), None)
        col_partner = next((c for c in df.columns if '納入先' in c), None)
        col_date = next((c for c in df.columns if '完成日' in c or '日' in c), None)
        col_qty = next((c for c in df.columns if '計画数' in c or '数量' in c or '数' in c), None)

        if not all([col_material, col_partner, col_date, col_qty]):
            if len(df.columns) >= 7:
                df.columns = ['品番', '計画番号', '計画数', '品名', '次工程', '材料コード', '納入先', '完成日'][:len(df.columns)]
                col_material = '材料コード'
                col_partner = '納入先'
                col_date = '完成日'
                col_qty = '計画数'
            else:
                st.error("❌ PDF format not recognized. Please ensure columns include '材料コード', '納入先', '完成日', '計画数'.")
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df_clean = df[[col_material, col_partner, col_date, col_qty]].copy()
        df_clean.columns = ['材料コード', '納入先', '完成日', '数量']
        df_clean['完成日'] = pd.to_datetime(df_clean['完成日'], errors='coerce')
        df_clean['数量'] = pd.to_numeric(df_clean['数量'], errors='coerce')
        df_clean = df_clean.dropna(subset=['数量'])
        df_clean = df_clean[df_clean['数量'] > 0]

        # --- Output 1: 材料別発注リスト ---
        df1 = df_clean.groupby(['材料コード', '完成日']).agg({
            '数量': 'sum',
            '納入先': 'first'
        }).reset_index()
        df1.columns = ['品番', '完成日', '数量', '納入先(参考)']

        # --- Output 2: 協力企業納入予定表 ---
        df2 = df_clean.groupby(['納入先', '完成日']).agg({
            '材料コード': lambda x: ', '.join(x.unique()),
            '数量': 'sum'
        }).reset_index()
        df2.columns = ['協力企業', '完成日', '品番(複数)', '数量合計']

        # --- Output 3: 社内プレス入荷予定表 ---
        df3 = df_clean.groupby(['完成日']).agg({
            '材料コード': lambda x: ', '.join(x.unique()),
            '数量': 'sum'
        }).reset_index()
        df3.columns = ['完成日', '品番(複数)', '数量合計']
        df3.insert(0, 'プレス/シフト', '全プレス(仮)')

        st.success(f"✅ PDF parsed: {len(df_clean)} orders, {df2['協力企業'].nunique()} unique partners detected.")

    elif has_dates:
        # --- Case 2: Excel '+29' format ---
        if '総数' in df.columns:
            df = df.drop(columns=['総数'])
        df_melted = df.melt(id_vars=['品番'], var_name='完成日', value_name='数量')
        df_melted = df_melted[df_melted['数量'] > 0].dropna()
        df_melted['完成日'] = pd.to_datetime(df_melted['完成日'], format='%m/%d')
        df_melted.columns = ['品番', '完成日', '数量']

        df1 = df_melted.groupby(['品番', '完成日']).agg({
            '数量': 'sum'
        }).reset_index()
        df1.columns = ['品番', '完成日', '数量']

        df2 = df_melted.groupby(['品番', '完成日']).agg({
            '数量': 'sum'
        }).reset_index()
        df2.columns = ['協力企業(品番)', '完成日', '数量']
        st.warning("⚠️ No '納入先' column in Excel. Using Material Code as Partner placeholder. Please edit manually or upload PDF for full partner list.")

        df3 = df_melted.groupby(['完成日']).agg({
            '品番': lambda x: ', '.join(x.unique()),
            '数量': 'sum'
        }).reset_index()
        df3.columns = ['完成日', '品番(複数)', '数量合計']
        df3.insert(0, 'プレス/シフト', '全プレス(Excel)')

    else:
        st.error("❌ Unrecognized data format. Please upload a PDF with '納入先' or an Excel '+29' sheet.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # ---------- Format dates ----------
    for df_out in [df1, df2, df3]:
        if '完成日' in df_out.columns:
            df_out['完成日'] = df_out['完成日'].dt.strftime('%Y-%m-%d')

    return df1, df2, df3
