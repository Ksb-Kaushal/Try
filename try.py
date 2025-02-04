import streamlit as st
import pandas as pd
import pdfplumber
import camelot
import re
from pathlib import Path
from fuzzywuzzy import fuzz

# --------------------- Configuration ---------------------
DATA_DIR = Path("invoices")
DATA_DIR.mkdir(exist_ok=True)

# --------------------- Backend Functions ---------------------
def extract_invoice_details(pdf_path):
    """Extract text and structured data from PDF"""
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join([page.extract_text() for page in pdf.pages])
        
        details = {
            'invoice_number': re.search(r'Invoice No[.:\s]*(\S+)', full_text, re.I),
            'date': re.search(r'Date[.:\s]*(\d{2}/\d{2}/\d{4})', full_text, re.I),
            'total_amount': re.search(r'Total[\s\$]*([\d,]+\.\d{2})', full_text, re.I),
            'due_date': re.search(r'Due Date[.:\s]*(\d{2}/\d{2}/\d{4})', full_text, re.I),
            'vendor': re.search(r'From:\s*(.+)\n', full_text, re.I),
            'client': re.search(r'To:\s*(.+)\n', full_text, re.I),
            'raw_text': full_text
        }
        
        for key in details:
            if details[key] and not isinstance(details[key], str):
                details[key] = details[key].group(1) if details[key] else "Not Found"
        
        tables = camelot.read_pdf(str(pdf_path), flavor='stream')
        table_dfs = [table.df for table in tables]
        
    return details, table_dfs

def match_invoices(df1, df2):
    """Fuzzy match invoices between datasets"""
    matches = []
    for idx1, row1 in df1.iterrows():
        for idx2, row2 in df2.iterrows():
            score = fuzz.ratio(str(row1['invoice']).lower(), str(row2['invoice']).lower())
            matches.append({
                'Dataset1_Invoice': row1['invoice'],
                'Dataset2_Invoice': row2['invoice'],
                'Confidence_Score': score,
                'Match_Status': 'Potential Match' if score > 70 else 'No Match'
            })
    return pd.DataFrame(matches)

# --------------------- Frontend Interface ---------------------
st.set_page_config(page_title="Firmway Finance Suite", layout="wide")
st.markdown("""
<style>
    .main {padding: 2rem;}
    .stButton>button {width: 100%;}
    .highlight {background-color: #e6f3ff; border-radius: 5px; padding: 1rem;}
    .metric-box {border: 1px solid #e1e4e8; padding: 1rem; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Firmway Smart Finance Suite")
operation = st.radio("Select Operation:", 
                    ["📄 Smart Statement Reader", "🔍 Intelligent Invoice Matching"],
                    horizontal=True)

# --------------------- Smart Statement Reader ---------------------
if operation == "📄 Smart Statement Reader":
    st.subheader("AI-Powered Document Analysis")
    uploaded_file = st.file_uploader("Upload Financial PDF", type=["pdf"])
    
    if uploaded_file:
        save_path = DATA_DIR / uploaded_file.name
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("Analyzing document structure..."):
            details, tables = extract_invoice_details(save_path)
        
        st.success("✅ Analysis complete!")
        
        # Key Details Display
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Basic Information**")
            st.write(f"Invoice Number: {details['invoice_number']}")
            st.write(f"Date: {details['date']}")
            st.write(f"Due Date: {details['due_date']}")
        
        with col2:
            st.markdown("**Financial Details**")
            st.write(f"Total Amount: {details['total_amount']}")
            st.write(f"Vendor: {details['vendor']}")
            st.write(f"Client: {details['client']}")
        
        with col3:
            st.markdown("**Document Insights**")
            st.write(f"Pages Analyzed: {len(tables)}")
            st.write(f"Tables Found: {len(tables)}")
            st.write(f"Text Length: {len(details['raw_text'])} chars")
        
        st.markdown("---")
        
        # Table Display Section
        if len(tables) > 0:
            st.subheader("📊 Extracted Tables")
            tab1, tab2 = st.tabs(["Individual Tables", "Combined View"])
            
            with tab1:
                table_idx = st.selectbox("Select Table", range(1, len(tables)+1))
                st.dataframe(tables[table_idx-1], height=300)
            
            with tab2:
                combined_df = pd.concat(tables)
                st.dataframe(combined_df, height=500)
            
            # Download Options
            csv = combined_df.to_csv(index=False).encode()
            st.download_button(
                "Download All Tables as CSV",
                data=csv,
                file_name=f"{Path(uploaded_file.name).stem}_tables.csv",
                mime="text/csv"
            )
        else:
            st.warning("No tables found in document")

# --------------------- Invoice Matching ---------------------
else:
    st.subheader("Intelligent Invoice Reconciliation")
    col1, col2 = st.columns(2)
    with col1:
        file1 = st.file_uploader("Upload Primary Dataset", type=["csv", "xlsx"])
    with col2:
        file2 = st.file_uploader("Upload Comparison Dataset", type=["csv", "xlsx"])
    
    if file1 and file2:
        df1 = pd.read_csv(file1) if file1.name.endswith('.csv') else pd.read_excel(file1)
        df2 = pd.read_csv(file2) if file2.name.endswith('.csv') else pd.read_excel(file2)
        
        if st.button("Run Invoice Matching"):
            with st.spinner("Matching invoices..."):
                matches_df = match_invoices(df1, df2)
            
            st.success(f"Found {len(matches_df)} potential matches!")
            
            # Results Display
            st.subheader("Matching Results")
            st.dataframe(
                matches_df.style.apply(
                    lambda row: ['background: #e6ffe6' if row['Match_Status'] == 'Potential Match' else '' 
                               for _ in row], axis=1),
                height=500
            )
            
            # Metrics
            col1, col2 = st.columns(2)
            with col1:
                avg_score = matches_df['Confidence_Score'].mean()
                st.metric("Average Confidence Score", f"{avg_score:.1f}%")
            
            with col2:
                potential_matches = matches_df[matches_df['Match_Status'] == 'Potential Match']
                st.metric("Auto-Matched Invoices", len(potential_matches))
            
            # Download Report
            report = matches_df.to_csv(index=False).encode()
            st.download_button(
                "Download Full Report",
                data=report,
                file_name="invoice_matches.csv",
                mime="text/csv"
            )

# --------------------- Sidebar Instructions ---------------------
with st.sidebar:
    st.markdown("## 🧠 How to Use")
    st.markdown("""
    **Smart Statement Reader**
    1. Upload financial PDF
    2. View auto-extracted details
    3. Download structured data
    
    **Invoice Matching**
    1. Upload two CSV/Excel files
    2. Run matching algorithm
    3. Review & export results
    """)
    st.markdown("---")
    st.markdown("**Key Features**")
    st.markdown("- 📄 PDF text & table extraction")
    st.markdown("- 🔍 Fuzzy matching algorithm")
    st.markdown("- 📊 Interactive data previews")
    st.markdown("- 📥 Multi-format exports")

