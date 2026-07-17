import pandas as pd
import streamlit as st
import re

def convert_data(input_df):
    """
    এখন যেকোনো তারিখের কলাম (যেমন 07/06, 07/13, 08/01) চিনবে।
    শিটের নাম যাই হোক, প্রথম শিট প্রসেস করবে।
    """
    df = input_df.copy()

    # ---------- 1. ফরম্যাট ডিটেক্ট করুন ----------
    # PDF ফরম্যাট চেক: '納入先' কলাম আছে কিনা
    has_partner = '納入先' in df.columns
    
    # Excel ফরম্যাট চেক: কলামের নামে 'MM/DD' প্যাটার্ন খুঁজুন (যেমন 07/13)
    date_pattern = re.compile(r'^\d{2}/\d{2}$')  # যেমন 07/13, 07/06
    date_cols = [col for col in df.columns if date_pattern.match(str(col).strip())]
    
    has_dates = len(date_cols) > 0

    # ---------- 2. ডেটা প্রসেস ----------
    if has_partner:
        # --- কেস ১: PDF (納入先 আছে) ---
        # আপনার PDF লজিক এখানে...
        # (এখনো ঠিক আছে, পরিবর্তন নেই)
        col_material = next((c for c in df.columns if '材料' in c or '品番' in c), None)
        col_partner = next((c for c in df.columns if '納入先' in c), None)
        col_date = next((c for c in df.columns if '完成日' in c), None)
        col_qty = next((c for c in df.columns if '計画数' in c), None)

        if not all([col_material, col_partner, col_date, col_qty]):
            if len(df.columns) >= 7:
                df.columns = ['品番', '計画番号', '計画数', '品名', '次工程', '材料コード', '納入先', '完成日'][:len(df.columns)]
                col_material = '材料コード'
                col_partner = '納入先'
                col_date = '完成日'
                col_qty = '計画数'
            else:
                st.error("❌ PDF format not recognized...")
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df_clean = df[[col_material, col_partner, col_date, col_qty]].copy()
        df_clean.columns = ['材料コード', '納入先', '完成日', '数量']
        df_clean['完成日'] = pd.to_datetime(df_clean['完成日'], errors='coerce')
        df_clean['数量'] = pd.to_numeric(df_clean['数量'], errors='coerce')
        df_clean = df_clean.dropna(subset=['数量'])
        df_clean = df_clean[df_clean['数量'] > 0]

        df1 = df_clean.groupby(['材料コード', '完成日']).agg({'数量': 'sum', '納入先': 'first'}).reset_index()
        df1.columns = ['品番', '完成日', '数量', '納入先(参考)']
        df2 = df_clean.groupby(['納入先', '完成日']).agg({'材料コード': lambda x: ', '.join(x.unique()), '数量': 'sum'}).reset_index()
        df2.columns = ['協力企業', '完成日', '品番(複数)', '数量合計']
        df3 = df_clean.groupby(['完成日']).agg({'材料コード': lambda x: ', '.join(x.unique()), '数量': 'sum'}).reset_index()
        df3.columns = ['完成日', '品番(複数)', '数量合計']
        df3.insert(0, 'プレス/シフト', '全プレス(仮)')

        st.success(f"✅ PDF parsed: {len(df_clean)} orders, {df2['協力企業'].nunique()} unique partners.")

        elif has_dates:
        # --- কেস ২: Excel '+29' ফরম্যাট ---
        if '総数' in df.columns:
            df = df.drop(columns=['総数'])
            
        if '品番' not in df.columns:
            st.error("❌ Excel-এ '品番' কলাম পাওয়া যায়নি।")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Wide → Long ফরম্যাটে রূপান্তর
        df_melted = df.melt(
            id_vars=['品番'], 
            value_vars=date_cols,
            var_name='完成日', 
            value_name='数量'
        )
        df_melted = df_melted[df_melted['数量'] > 0].dropna()
        
        # 📌 সমস্যা: এখানে বছর ১৯০০ হয়ে যায়
        df_melted['完成日'] = pd.to_datetime(df_melted['完成日'], format='%m/%d')
        
        # ✅ সমাধান: ১৯০০ সালকে ২০২৬ সালে পরিবর্তন করুন
        # FIX: যেহেতু Excel-এ বছর নেই, তাই সব তারিখকে 2026 সালের করে দিচ্ছি
        df_melted['完成日'] = df_melted['完成日'].apply(lambda x: x.replace(year=2026))
        
        df_melted.columns = ['品番', '完成日', '数量']

        # --- আউটপুট ১ ---
        df1 = df_melted.groupby(['品番', '完成日']).agg({'数量': 'sum'}).reset_index()
        df1.columns = ['品番', '完成日', '数量']

        # --- আউটপুট ২ ---
        df2 = df_melted.groupby(['品番', '完成日']).agg({'数量': 'sum'}).reset_index()
        df2.columns = ['協力企業(品番)', '完成日', '数量']
        st.warning("⚠️ Excel-এ '納入先' কলাম নেই। '品番' কে সহযোগী প্রতিষ্ঠানের জায়গায় দেখানো হচ্ছে।")

        # --- আউটপুট ৩ ---
        df3 = df_melted.groupby(['完成日']).agg({
            '品番': lambda x: ', '.join(x.unique()),
            '数量': 'sum'
        }).reset_index()
        df3.columns = ['完成日', '品番(複数)', '数量合計']
        df3.insert(0, 'プレス/シフト', '全プレス(Excel)')

        st.success(f"✅ Excel processed! Total rows: {len(df_melted)}")
    else:
        st.error("❌ Unrecognized data format. Please upload a PDF with '納入先' or an Excel sheet with '品番' and date columns (like 07/13).")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # ---------- 3. তারিখ ফরম্যাট করুন ----------
    for df_out in [df1, df2, df3]:
        if '完成日' in df_out.columns:
            df_out['完成日'] = df_out['完成日'].dt.strftime('%Y-%m-%d')

    return df1, df2, df3
