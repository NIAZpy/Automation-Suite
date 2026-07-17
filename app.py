import streamlit as st
import pandas as pd
import os
import pdfplumber
import re
from converter import convert_data
from io import BytesIO

# ==========================================
# 1. LOAD EXTERNAL CSS (style.css)
# ==========================================
def load_css(file_name="style.css"):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        # যদি ফাইল না পাওয়া যায়, তাহলে কিছু করবে না (শুধু সতর্কতা)
        st.warning("⚠️ style.css file not found. Using default Streamlit theme.")

# CSS লোড করুন
load_css()

# ==========================================
# Helper Functions
# ==========================================
def make_columns_unique(cols):
    seen = {}
    new_cols = []
    for col in cols:
        if pd.isna(col) or col == '' or col is None:
            base = "Unnamed"
        else:
            base = str(col).strip()
        if base in seen:
            seen[base] += 1
            new_cols.append(f"{base}_{seen[base]}")
        else:
            seen[base] = 0
            new_cols.append(base)
    return new_cols

def pdf_to_excel_converter(pdf_file):
    data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split("\n"):
                m = re.search(r'(\d{2}/\d{2}).*?(\d-\d{5}-[\w-]+).*?(\d+)\s+資材', line)
                if m:
                    data.append([m.group(1), m.group(2), int(m.group(3))])
    if not data:
        return None
    df = pd.DataFrame(data, columns=["指示日", "品番", "計画数"])
    date_order = sorted(df["指示日"].unique(), key=lambda x: tuple(map(int, x.split("/"))))
    pivot = df.pivot_table(index="品番", columns="指示日", values="計画数", aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(columns=date_order)
    pivot["総数"] = pivot.sum(axis=1)
    return pivot

# ==========================================
# Streamlit App Config
# ==========================================
st.set_page_config(page_title=" Automation Tool (自動化ツール)", layout="wide", page_icon="🤖")

# হেডার (সুন্দর টাইটেল)
st.markdown('<div class="custom-title"> Automation Suite🤖オートメーションスイート</div>', unsafe_allow_html=True)
st.markdown('<div class="custom-sub">自動化スイート ｜ +29 Data Processing & PDF → Excel Converter</div>', unsafe_allow_html=True)

# ==========================================
# Tabs Navigation
# ==========================================
tab1, tab2 = st.tabs(["🔧 Main Tool (メインツール)", "📄 PDF → Excel Converter (PDF変換)"])

# ==========================================
# TAB 1: MAIN TOOL
# ==========================================
with tab1:
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.markdown("**Upload Excel (.xlsx/.xls) or PDF (.pdf)** file. Duplicate headers are handled automatically. <br> **(Excel / PDF ファイルをアップロードしてください。重複ヘッダーは自動処理されます。)**", unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("📤 Upload '+29' data file (データファイルをアップロード)", type=['xlsx', 'xls', 'pdf'])
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_file is not None:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        df = None

        with st.spinner("⏳ Reading file... (ファイル読み込み中...)"):
            try:
                if file_extension == 'pdf':
                    st.info("📄 Extracting data from PDF... (PDFからデータを抽出中...)")
                    all_dfs = []
                    raw_rows = []
                    with pdfplumber.open(uploaded_file) as pdf:
                        for page in pdf.pages:
                            tables = page.extract_tables()
                            if tables and any(tables):
                                for table in tables:
                                    if table and len(table) > 1:
                                        temp_df = pd.DataFrame(table)
                                        raw_headers = temp_df.iloc[0].tolist()
                                        unique_headers = make_columns_unique(raw_headers)
                                        temp_df.columns = unique_headers
                                        temp_df = temp_df.drop(0).reset_index(drop=True)
                                        all_dfs.append(temp_df)
                            else:
                                text = page.extract_text()
                                if text:
                                    for line in text.split('\n'):
                                        line = line.strip()
                                        if not line: continue
                                        parts = re.split(r'\s{2,}', line)
                                        if len(parts) == 1: parts = line.split()
                                        if parts: raw_rows.append(parts)
                    if all_dfs:
                        df = pd.concat(all_dfs, ignore_index=True)
                        st.success(f"✅ Table extracted! Total rows: {len(df)} (テーブル抽出完了！ 合計行数: {len(df)})")
                    elif raw_rows:
                        max_cols = max(len(row) for row in raw_rows)
                        padded_rows = [row + [''] * (max_cols - len(row)) for row in raw_rows]
                        df = pd.DataFrame(padded_rows)
                        if len(df) > 0:
                            raw_headers = df.iloc[0].tolist()
                            df.columns = make_columns_unique(raw_headers)
                            df = df.drop(0).reset_index(drop=True)
                        st.warning("⚠️ No table borders found. Parsed from text. (テーブル境界なし。テキストから解析。)", unsafe_allow_html=True)
                        st.info(f"📝 Parsed {len(df)} rows from text. (テキストから {len(df)} 行を解析。)")
                    else:
                        st.error("❌ No data extracted. (データ抽出失敗。)")
                        st.stop()
                else:
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                    if len(df.columns) != len(set(df.columns)):
                        df.columns = make_columns_unique(df.columns.tolist())
                    st.success(f"✅ Excel loaded! Total rows: {len(df)} (Excel読み込み完了！ 合計行数: {len(df)})")
            except Exception as e:
                st.error(f"⚠️ Error: {e} (エラー: {e})")
                st.stop()

        if df is not None and len(df) > 0:
            st.markdown('<div class="main-card">', unsafe_allow_html=True)
            st.subheader("📊 Data Preview (データプレビュー)")
            max_rows = len(df)
            default_rows = min(5, max_rows)
            preview_count = st.slider("Rows to preview (プレビュー行数)", 1, max_rows, default_rows, 1)
            st.dataframe(df.head(preview_count), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="main-card">', unsafe_allow_html=True)
            if st.button("🚀 Generate 3 Lists (One-click) (3つのリストを生成)", type="primary"):
                with st.spinner("⏳ Processing... (処理中...)"):
                    try:
                        output_dfs = convert_data(df)
                        os.makedirs("output", exist_ok=True)
                        output_dfs[0].to_excel("output/01_材料別発注リスト.xlsx", index=False)
                        output_dfs[1].to_excel("output/02_協力企業納入予定表.xlsx", index=False)
                        output_dfs[2].to_excel("output/03_社内プレス入荷予定表.xlsx", index=False)

                        st.success("✅ 3 files created! Download below. (3つのファイル作成！ 以下からダウンロード。)")
                        
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            with open("output/01_材料別発注リスト.xlsx", "rb") as f:
                                st.download_button("📥 材料別発注リスト", f, file_name="01_材料別発注リスト.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        with c2:
                            with open("output/02_協力企業納入予定表.xlsx", "rb") as f:
                                st.download_button("📥 協力企業納入予定表", f, file_name="02_協力企業納入予定表.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        with c3:
                            with open("output/03_社内プレス入荷予定表.xlsx", "rb") as f:
                                st.download_button("📥 社内プレス入荷予定表", f, file_name="03_社内プレス入荷予定表.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    except Exception as e:
                        st.error(f"❌ Processing error: {e} (処理エラー: {e})")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning("⚠️ No data loaded. (データが読み込まれませんでした。)")

# ==========================================
# TAB 2: PDF TO EXCEL CONVERTER
# ==========================================
with tab2:
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.markdown("**Upload a PDF file** to extract order data (Date, Part No, Qty) and generate a pivot table Excel. <br> **(PDFをアップロードして、注文データ（日付、品番、数量）を抽出し、ピボットテーブルのExcelを生成します。)**", unsafe_allow_html=True)
    
    uploaded_pdf = st.file_uploader("📤 Upload PDF file (PDFファイルをアップロード)", type=['pdf'])
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_pdf is not None:
        with st.spinner("⏳ Processing PDF... (PDFを処理中...)"):
            try:
                pivot_df = pdf_to_excel_converter(uploaded_pdf)
                if pivot_df is None:
                    st.error("❌ No matching data found. Check format. (該当データなし。フォーマット確認。)")
                else:
                    st.success(f"✅ Conversion successful! {len(pivot_df)} rows extracted. (変換成功！ {len(pivot_df)} 行抽出。)")
                    
                    st.markdown('<div class="main-card">', unsafe_allow_html=True)
                    st.subheader("📊 Preview (プレビュー)")
                    st.dataframe(pivot_df.head(10), use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                    output_filename = "converted_" + uploaded_pdf.name.replace(".pdf", ".xlsx")
                    output = BytesIO()
                    pivot_df.to_excel(output, index=True, engine='openpyxl')
                    output.seek(0)
                    
                    st.markdown('<div class="main-card">', unsafe_allow_html=True)
                    st.download_button("📥 Download Excel (Excelをダウンロード)", data=output, file_name=output_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    st.markdown('</div>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"❌ Error: {e} (エラー: {e})")

# ==========================================
# Footer
# ==========================================
st.markdown('<div class="footer-note">Made with ❤️ for 米山工業株式会社　内　YONEYAMA BRAND</div>', unsafe_allow_html=True)