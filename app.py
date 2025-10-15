# ============================================================
# 🎯 STREAMLIT WEB APP V2.2 - UPLOAD STOCK LIST
# ============================================================
# Tính năng mới: Upload Excel/CSV danh sách mã CK
# ============================================================

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import re
from urllib.parse import urljoin
import io

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Cào Tin Chứng Khoán V2.2",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS CUSTOM
# ============================================================

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .upload-box {
        background-color: #e8f4f8;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 2px dashed #1f77b4;
        margin: 1rem 0;
    }
    .severe-card {
        background-color: #ffe6e6;
        border-left: 5px solid #ff4444;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
    }
    .warning-card {
        background-color: #fff8e6;
        border-left: 5px solid #ffaa00;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
    }
    .positive-card {
        background-color: #e6ffe6;
        border-left: 5px solid #44ff44;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_default_stock_list():
    """Danh sách mã mặc định (backup)"""
    default_data = {
        'Mã CK': ['SHS', 'PVS', 'NVB', 'VCS', 'BVS', 'APS', 'MBS', 'CEO', 'VGC', 'PVC',
                  'LPB', 'EIB', 'BAB', 'OCB', 'BMI', 'HDG', 'PAN', 'NTL'],
        'Sàn': ['HNX']*10 + ['UPCoM']*8,
        'Tên công ty': ['Chứng khoán SHS', 'Chứng khoán PVS', 'Ngân hàng NVB', 'Chứng khoán VCS',
                        'Chứng khoán BVS', 'Chứng khoán APS', 'Chứng khoán MBS', 'Tập đoàn CEO',
                        'Viglacera', 'PVC', 'Ngân hàng LPB', 'Ngân hàng EIB', 'Ngân hàng BAB',
                        'Ngân hàng OCB', 'Bảo hiểm BMI', 'Tập đoàn HDG', 'PAN Group', 'NTL Logistics']
    }
    return pd.DataFrame(default_data)

def parse_stock_file(uploaded_file):
    """Parse Excel/CSV file"""
    try:
        # Đọc file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # Chuẩn hóa tên cột
        df.columns = df.columns.str.strip().str.lower()
        
        # Map các tên cột có thể có
        column_mapping = {
            'mã ck': 'Mã CK',
            'ma ck': 'Mã CK',
            'mã': 'Mã CK',
            'ma': 'Mã CK',
            'code': 'Mã CK',
            'stock_code': 'Mã CK',
            'ticker': 'Mã CK',
            
            'sàn': 'Sàn',
            'san': 'Sàn',
            'exchange': 'Sàn',
            'mã sàn': 'Sàn',
            'ma san': 'Sàn',
            
            'tên công ty': 'Tên công ty',
            'ten cong ty': 'Tên công ty',
            'tên': 'Tên công ty',
            'ten': 'Tên công ty',
            'name': 'Tên công ty',
            'company': 'Tên công ty',
            'company_name': 'Tên công ty',
        }
        
        # Rename columns
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)
        
        # Kiểm tra các cột bắt buộc
        required_cols = ['Mã CK', 'Sàn']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            return None, f"Thiếu các cột: {', '.join(missing_cols)}"
        
        # Thêm cột Tên công ty nếu không có
        if 'Tên công ty' not in df.columns:
            df['Tên công ty'] = ''
        
        # Làm sạch dữ liệu
        df['Mã CK'] = df['Mã CK'].astype(str).str.strip().str.upper()
        df['Sàn'] = df['Sàn'].astype(str).str.strip().str.upper()
        df['Tên công ty'] = df['Tên công ty'].astype(str).str.strip()
        
        # Lọc chỉ HNX và UPCoM
        df = df[df['Sàn'].isin(['HNX', 'UPCOM'])]
        
        # Chuẩn hóa UPCoM
        df['Sàn'] = df['Sàn'].replace('UPCOM', 'UPCoM')
        
        # Bỏ trùng
        df = df.drop_duplicates(subset=['Mã CK'])
        
        return df, None
        
    except Exception as e:
        return None, f"Lỗi đọc file: {str(e)}"

def create_sample_excel():
    """Tạo file Excel mẫu"""
    sample_data = {
        'Mã CK': ['SHS', 'PVS', 'NVB', 'LPB', 'EIB', 'CEO'],
        'Sàn': ['HNX', 'HNX', 'HNX', 'UPCoM', 'UPCoM', 'HNX'],
        'Tên công ty': ['Chứng khoán Sài Gòn - Hà Nội', 'Chứng khoán Dầu khí', 
                        'Ngân hàng Quốc dân', 'Ngân hàng Lộc Phát', 
                        'Ngân hàng Xuất nhập khẩu', 'Tập đoàn CEO']
    }
    df = pd.DataFrame(sample_data)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Danh sách mã')
    
    return buffer.getvalue()

# ============================================================
# SCRAPER CLASSES
# ============================================================

class KeywordRiskDetector:
    """Phát hiện keywords rủi ro"""
    
    def __init__(self):
        self.keywords_db = {
            "lãnh đạo bị bắt": {"category": "A. Nội bộ", "severity": "severe", "score": -95, "violation": "I.2, II.A"},
            "lãnh đạo bỏ trốn": {"category": "A. Nội bộ", "severity": "severe", "score": -95, "violation": "I.2, II.A"},
            "cổ đông lớn bán chui": {"category": "A. Nội bộ", "severity": "severe", "score": -85, "violation": "I.1, II.A"},
            "chủ tịch bất ngờ thoái hết vốn": {"category": "A. Nội bộ", "severity": "severe", "score": -85, "violation": "I.1, II.A"},
            "bất ngờ báo lỗ": {"category": "B. Tài chính", "severity": "severe", "score": -80, "violation": "I.4, II.B"},
            "âm vốn chủ": {"category": "B. Tài chính", "severity": "severe", "score": -90, "violation": "II.B"},
            "đội lái làm giá": {"category": "C. Thao túng", "severity": "severe", "score": -95, "violation": "I.3, II.C"},
            "tăng trần liên tiếp": {"category": "C. Thao túng", "severity": "warning", "score": -60, "violation": "I.2, II.C"},
            "công an điều tra": {"category": "E. Pháp lý", "severity": "severe", "score": -90, "violation": "II.E"},
            "lợi nhuận tăng": {"category": "Tích cực", "severity": "positive", "score": 70, "violation": ""},
            "tăng trưởng mạnh": {"category": "Tích cực", "severity": "positive", "score": 65, "violation": ""},
        }
    
    def analyze(self, text):
        text_lower = text.lower()
        found_keywords = []
        total_score = 0
        categories = set()
        violations = set()
        max_severity = "normal"
        
        for keyword, info in self.keywords_db.items():
            if keyword in text_lower:
                found_keywords.append({
                    "keyword": keyword,
                    "category": info["category"],
                    "severity": info["severity"],
                    "score": info["score"],
                    "violation": info["violation"]
                })
                total_score += info["score"]
                categories.add(info["category"])
                if info["violation"]:
                    violations.add(info["violation"])
                
                if info["severity"] == "severe":
                    max_severity = "severe"
                elif info["severity"] == "warning" and max_severity != "severe":
                    max_severity = "warning"
                elif info["severity"] == "positive" and max_severity == "normal":
                    max_severity = "positive"
        
        return {
            "keywords": found_keywords,
            "total_score": total_score,
            "severity": max_severity,
            "categories": list(categories),
            "violations": ", ".join(sorted(violations))
        }

class SimpleSentimentAnalyzer:
    """Phân tích sentiment"""
    
    def __init__(self):
        self.keyword_detector = KeywordRiskDetector()
        self.positive_words = ['tăng', 'tăng trưởng', 'lợi nhuận', 'thành công', 'tốt', 'cao', 'mạnh', 'vượt']
        self.negative_words = ['giảm', 'sụt giảm', 'lỗ', 'thua lỗ', 'khó khăn', 'tiêu cực', 'suy giảm']
    
    def analyze_sentiment(self, title, content):
        text = (title + " " + content).lower()
        keyword_analysis = self.keyword_detector.analyze(title + " " + content)
        
        pos_count = sum(1 for word in self.positive_words if word in text)
        neg_count = sum(1 for word in self.negative_words if word in text)
        
        base_score = 50 + (pos_count * 5) - (neg_count * 5)
        
        if keyword_analysis["severity"] == "severe":
            final_score = min(20, base_score + keyword_analysis["total_score"])
        elif keyword_analysis["severity"] == "warning":
            final_score = min(40, base_score + keyword_analysis["total_score"] * 0.7)
        elif keyword_analysis["severity"] == "positive":
            final_score = max(60, base_score + keyword_analysis["total_score"])
        else:
            final_score = base_score
        
        final_score = max(0, min(100, final_score))
        
        if final_score >= 60:
            label = "Tích cực"
        elif final_score >= 40:
            label = "Trung lập"
        else:
            label = "Tiêu cực"
        
        if keyword_analysis["severity"] == "severe":
            risk_level = "Nghiêm trọng"
        elif keyword_analysis["severity"] == "warning":
            risk_level = "Cảnh báo"
        elif keyword_analysis["severity"] == "positive":
            risk_level = "Tích cực"
        else:
            risk_level = "Bình thường"
        
        return {
            "sentiment_score": round(final_score, 1),
            "sentiment_label": label,
            "risk_level": risk_level,
            "keywords": keyword_analysis["keywords"],
            "categories": ", ".join(keyword_analysis["categories"]) if keyword_analysis["categories"] else "",
            "violations": keyword_analysis["violations"]
        }

class StockScraperWeb:
    """Scraper với stock list từ file"""
    
    def __init__(self, stock_df, time_filter_hours=24):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        }
        self.all_articles = []
        self.session = requests.Session()
        self.time_filter_hours = time_filter_hours
        
        self.vietnam_tz = timezone(timedelta(hours=7))
        self.cutoff_time = datetime.now(self.vietnam_tz) - timedelta(hours=time_filter_hours)
        
        self.sentiment_analyzer = SimpleSentimentAnalyzer()
        
        # Load stock list từ DataFrame
        self.stock_df = stock_df
        self.hnx_stocks = set(stock_df[stock_df['Sàn'] == 'HNX']['Mã CK'].tolist())
        self.upcom_stocks = set(stock_df[stock_df['Sàn'] == 'UPCoM']['Mã CK'].tolist())
        
        # Tạo dict: mã → tên công ty (cho tìm kiếm theo tên)
        self.code_to_name = dict(zip(stock_df['Mã CK'], stock_df['Tên công ty']))
        
        # Tạo dict: tên → mã (lowercase để search)
        self.name_to_code = {}
        for code, name in self.code_to_name.items():
            if name:
                # Tách từ trong tên công ty
                words = name.lower().split()
                for word in words:
                    if len(word) > 3:  # Bỏ qua từ quá ngắn
                        if word not in self.name_to_code:
                            self.name_to_code[word] = []
                        self.name_to_code[word].append(code)
        
        self.stock_to_exchange = {}
        for code in self.hnx_stocks:
            self.stock_to_exchange[code] = 'HNX'
        for code in self.upcom_stocks:
            self.stock_to_exchange[code] = 'UPCoM'
        
        self.stats = {
            'total_crawled': 0,
            'hnx_found': 0,
            'upcom_found': 0,
            'severe_risk': 0,
            'warning_risk': 0,
            'found_by_code': 0,
            'found_by_name': 0
        }
    
    def clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'[^\w\s.,;:!?()%\-\+\/\"\'àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract_stock(self, text):
        """
        Trích xuất mã CK - TÌM THEO MÃ VÀ TÊN
        Priority:
        1. Tìm theo mã CK
        2. Nếu không có, tìm theo tên công ty
        """
        text_upper = text.upper()
        text_lower = text.lower()
        
        # Blacklist
        blacklist_patterns = [
            r'CHỨNG KHOÁN\s+\w+\s+CÓ\s+NHẬN ĐỊNH',
            r'CHỨNG KHOÁN\s+\w+\s+DỰ BÁO',
            r'CHỨNG KHOÁN\s+\w+\s+PHÂN TÍCH',
            r'CÔNG TY\s+CHỨNG KHOÁN',
            r'CTCK\s+\w+',
            r'VN-INDEX',
            r'HNX-INDEX',
            r'UPCOM-INDEX',
        ]
        
        for pattern in blacklist_patterns:
            if re.search(pattern, text_upper):
                return None, None, None
        
        # METHOD 1: Tìm theo MÃ CK
        for code in self.hnx_stocks:
            match = re.search(r'\b' + code + r'\b', text_upper)
            if match:
                context = text_upper[max(0, match.start()-10):match.end()+10]
                
                if re.search(r'CHỨNG KHOÁN\s+' + code, context):
                    continue
                if re.search(r'CTCK\s+' + code, context):
                    continue
                
                return code, 'HNX', 'code'
        
        for code in self.upcom_stocks:
            match = re.search(r'\b' + code + r'\b', text_upper)
            if match:
                context = text_upper[max(0, match.start()-10):match.end()+10]
                
                if re.search(r'CHỨNG KHOÁN\s+' + code, context):
                    continue
                if re.search(r'CTCK\s+' + code, context):
                    continue
                
                return code, 'UPCoM', 'code'
        
        # METHOD 2: Tìm theo TÊN CÔNG TY
        # Tách từ trong text
        words = text_lower.split()
        matched_codes = []
        
        for word in words:
            if len(word) > 3 and word in self.name_to_code:
                matched_codes.extend(self.name_to_code[word])
        
        if matched_codes:
            # Lấy mã xuất hiện nhiều nhất
            from collections import Counter
            most_common = Counter(matched_codes).most_common(1)[0][0]
            exchange = self.stock_to_exchange.get(most_common)
            return most_common, exchange, 'name'
        
        return None, None, None
    
    def fetch_url(self, url, max_retries=2):
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
                return response
            except:
                if attempt < max_retries - 1:
                    time.sleep(1)
                return None
    
    def scrape_source(self, url, source_name, pattern, max_articles=20, progress_callback=None):
        """Cào từ một nguồn"""
        try:
            response = self.fetch_url(url)
            if not response:
                return 0
            
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            count = 0
            seen = set()
            
            links = soup.find_all('a', href=True)
            total_links = len(links)
            
            for idx, link_tag in enumerate(links):
                if progress_callback:
                    progress = (idx + 1) / total_links
                    progress_callback(f"{source_name}: {idx+1}/{total_links}", progress)
                
                href = link_tag.get('href', '')
                
                if pattern(href) and href not in seen:
                    title = link_tag.get_text(strip=True)
                    
                    if title and len(title) > 30:
                        self.stats['total_crawled'] += 1
                        seen.add(href)
                        
                        stock_code, exchange, match_method = self.extract_stock(title)
                        
                        if stock_code and exchange in ['HNX', 'UPCoM']:
                            full_link = urljoin(url, href)
                            
                            # Track method
                            if match_method == 'code':
                                self.stats['found_by_code'] += 1
                            else:
                                self.stats['found_by_name'] += 1
                            
                            # Lấy tên công ty
                            company_name = self.code_to_name.get(stock_code, '')
                            
                            # Sentiment analysis
                            sentiment_result = self.sentiment_analyzer.analyze_sentiment(title, "")
                            
                            if exchange == 'HNX':
                                self.stats['hnx_found'] += 1
                            else:
                                self.stats['upcom_found'] += 1
                            
                            if sentiment_result['risk_level'] == 'Nghiêm trọng':
                                self.stats['severe_risk'] += 1
                            elif sentiment_result['risk_level'] == 'Cảnh báo':
                                self.stats['warning_risk'] += 1
                            
                            self.all_articles.append({
                                'Tiêu đề': title,
                                'Link': full_link,
                                'Ngày': datetime.now(self.vietnam_tz).strftime('%d/%m/%Y'),
                                'Mã CK': stock_code,
                                'Tên công ty': company_name,
                                'Sàn': exchange,
                                'Sentiment': sentiment_result['sentiment_label'],
                                'Điểm': sentiment_result['sentiment_score'],
                                'Risk': sentiment_result['risk_level'],
                                'Vi phạm': sentiment_result['violations'],
                                'Keywords': "; ".join([k['keyword'] for k in sentiment_result['keywords'][:3]]),
                                'Tìm theo': 'Mã CK' if match_method == 'code' else 'Tên công ty'
                            })
                            
                            count += 1
                            
                            if count >= max_articles:
                                break
            
            return count
        
        except Exception as e:
            st.error(f"Lỗi {source_name}: {str(e)}")
            return 0
    
    def run(self, max_articles_per_source=20, progress_callback=None):
        """Chạy scraper"""
        sources = [
            ("https://cafef.vn/thi-truong-chung-khoan.chn", "CafeF", lambda h: '.chn' in h),
            ("https://vietstock.vn/chung-khoan.htm", "VietStock", lambda h: re.search(r'/\d{4}/\d{2}/.+\.htm', h)),
        ]
        
        for url, name, pattern in sources:
            self.scrape_source(url, name, pattern, max_articles_per_source, progress_callback)
            time.sleep(1)
        
        if len(self.all_articles) == 0:
            return None
        
        df = pd.DataFrame(self.all_articles)
        df = df.drop_duplicates(subset=['Tiêu đề'], keep='first')
        df.insert(0, 'STT', range(1, len(df) + 1))
        
        return df

# ============================================================
# STREAMLIT APP
# ============================================================

def main():
    # Header
    st.markdown('<div class="main-header">📈 TOOL CÀO TIN V2.2</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">HNX & UPCoM - Upload Danh Sách Mã CK</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ CÀI ĐẶT")
        
        # UPLOAD STOCK LIST
        st.subheader("📂 DANH SÁCH MÃ CK")
        
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        st.write("**Upload file Excel/CSV**")
        st.caption("Gồm 3 cột: Mã CK | Sàn | Tên công ty")
        
        uploaded_file = st.file_uploader(
            "Chọn file",
            type=['xlsx', 'xls', 'csv'],
            help="File phải có các cột: Mã CK, Sàn (HNX/UPCoM), Tên công ty"
        )
        
        # Download sample
        sample_excel = create_sample_excel()
        st.download_button(
            label="📥 Tải file mẫu",
            data=sample_excel,
            file_name="mau_danh_sach_ma_ck.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Parse uploaded file
        if uploaded_file is not None:
            stock_df, error = parse_stock_file(uploaded_file)
            
            if error:
                st.error(f"❌ {error}")
                st.session_state['stock_df'] = load_default_stock_list()
            else:
                st.success(f"✅ Đã load {len(stock_df)} mã CK")
                st.session_state['stock_df'] = stock_df
                
                # Hiển thị thống kê
                hnx_count = len(stock_df[stock_df['Sàn'] == 'HNX'])
                upcom_count = len(stock_df[stock_df['Sàn'] == 'UPCoM'])
                st.info(f"HNX: {hnx_count} | UPCoM: {upcom_count}")
        else:
            if 'stock_df' not in st.session_state:
                st.session_state['stock_df'] = load_default_stock_list()
                st.warning("⚠️ Đang dùng danh sách mặc định")
        
        st.markdown("---")
        
        # Cài đặt cào tin
        st.subheader("🔧 TÙY CHỈNH")
        
        time_filter = st.selectbox(
            "⏰ Khoảng thời gian",
            options=[6, 12, 24, 48, 72, 168],
            format_func=lambda x: f"{x} giờ" if x < 168 else "1 tuần",
            index=2
        )
        
        max_articles = st.slider(
            "📊 Số bài tối đa/nguồn",
            min_value=5,
            max_value=50,
            value=20,
            step=5
        )
        
        st.markdown("---")
        st.info("💡 **Hướng dẫn:**\n1. Upload danh sách mã\n2. Chọn thời gian\n3. Bấm 'Bắt đầu'\n4. Download Excel")
    
    # Main content
    if st.button("🚀 BẮT ĐẦU CÀO TIN", type="primary"):
        stock_df = st.session_state.get('stock_df')
        
        if stock_df is None or len(stock_df) == 0:
            st.error("❌ Chưa có danh sách mã CK! Vui lòng upload file.")
            return
        
        with st.spinner("Đang cào tin..."):
            # Progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(progress)
            
            # Run scraper
            scraper = StockScraperWeb(stock_df, time_filter_hours=time_filter)
            df = scraper.run(max_articles_per_source=max_articles, progress_callback=update_progress)
            
            progress_bar.empty()
            status_text.empty()
            
            if df is not None:
                st.success(f"✅ Hoàn tất! Tìm thấy {len(df)} bài viết")
                
                # Hiển thị thống kê matching method
                st.info(f"🔍 Tìm theo mã CK: {scraper.stats['found_by_code']} | Tìm theo tên: {scraper.stats['found_by_name']}")
                
                # Store in session
                st.session_state['df'] = df
                st.session_state['stats'] = scraper.stats
            else:
                st.error("Không tìm thấy bài viết nào!")
    
    # Display results
    if 'df' in st.session_state:
        df = st.session_state['df']
        stats = st.session_state['stats']
        
        # Metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📊 Tổng bài", len(df))
        with col2:
            st.metric("⚠️ Nghiêm trọng", stats['severe_risk'])
        with col3:
            st.metric("⚠️ Cảnh báo", stats['warning_risk'])
        with col4:
            st.metric("🔤 Tìm theo mã", stats['found_by_code'])
        with col5:
            st.metric("📝 Tìm theo tên", stats['found_by_name'])
        
        # Download button
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Sheet 1: Tất cả
            df.to_excel(writer, index=False, sheet_name='Tất cả')
            
            # Sheet 2: Nghiêm trọng
            df_severe = df[df['Risk'] == 'Nghiêm trọng']
            if len(df_severe) > 0:
                df_severe.to_excel(writer, index=False, sheet_name='Nghiêm trọng')
            
            # Sheet 3: Cảnh báo
            df_warning = df[df['Risk'] == 'Cảnh báo']
            if len(df_warning) > 0:
                df_warning.to_excel(writer, index=False, sheet_name='Cảnh báo')
        
        st.download_button(
            label="⬇️ Download Excel",
            data=buffer.getvalue(),
            file_name=f"Tin_CK_{datetime.now().strftime('%d%m%Y_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.markdown("---")
        
        # Filters
        st.subheader("🔍 LỌC & TÌM KIẾM")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            search_code = st.text_input("Mã CK", placeholder="VD: SHS")
        with col2:
            filter_san = st.selectbox("Sàn", ["Tất cả", "HNX", "UPCoM"])
        with col3:
            filter_risk = st.selectbox("Risk Level", ["Tất cả", "Nghiêm trọng", "Cảnh báo", "Bình thường", "Tích cực"])
        with col4:
            filter_method = st.selectbox("Tìm theo", ["Tất cả", "Mã CK", "Tên công ty"])
        
        # Apply filters
        df_filtered = df.copy()
        
        if search_code:
            df_filtered = df_filtered[
                df_filtered['Mã CK'].str.contains(search_code.upper(), case=False, na=False) |
                df_filtered['Tên công ty'].str.contains(search_code, case=False, na=False)
            ]
        
        if filter_san != "Tất cả":
            df_filtered = df_filtered[df_filtered['Sàn'] == filter_san]
        
        if filter_risk != "Tất cả":
            df_filtered = df_filtered[df_filtered['Risk'] == filter_risk]
        
        if filter_method != "Tất cả":
            df_filtered = df_filtered[df_filtered['Tìm theo'] == filter_method]
        
        st.info(f"Hiển thị {len(df_filtered)} / {len(df)} bài")
        
        # Display articles
        st.subheader("📰 DANH SÁCH BÀI VIẾT")
        
        for idx, row in df_filtered.iterrows():
            # Card color
            if row['Risk'] == 'Nghiêm trọng':
                card_class = "severe-card"
                icon = "⚠️"
            elif row['Risk'] == 'Cảnh báo':
                card_class = "warning-card"
                icon = "⚠️"
            elif row['Risk'] == 'Tích cực':
                card_class = "positive-card"
                icon = "✅"
            else:
                card_class = "metric-card"
                icon = "📄"
            
            with st.container():
                st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # Tiêu đề với mã và tên công ty
                    if row['Tên công ty']:
                        st.markdown(f"**{icon} {row['Mã CK']} - {row['Tên công ty']} ({row['Sàn']})**")
                    else:
                        st.markdown(f"**{icon} {row['Mã CK']} ({row['Sàn']})**")
                    
                    st.markdown(f"{row['Tiêu đề']}")
                    
                    caption_text = f"📅 {row['Ngày']} | "
                    caption_text += f"Sentiment: {row['Sentiment']} ({row['Điểm']}) | "
                    caption_text += f"Risk: {row['Risk']} | "
                    caption_text += f"🔍 {row['Tìm theo']}"
                    
                    if row['Vi phạm']:
                        caption_text += f" | ⚖️ {row['Vi phạm']}"
                    
                    st.caption(caption_text)
                
                with col2:
                    if st.button("🔗 Xem", key=f"view_{idx}"):
                        st.markdown(f"[Mở bài viết]({row['Link']})")
                
                if row['Keywords']:
                    st.info(f"🔑 Keywords: {row['Keywords']}")
                
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
        
        # Dashboard
        st.markdown("---")
        st.subheader("📊 DASHBOARD")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Phân bố Sentiment**")
            sentiment_counts = df['Sentiment'].value_counts()
            st.bar_chart(sentiment_counts)
        
        with col2:
            st.write("**Phân bố Risk Level**")
            risk_counts = df['Risk'].value_counts()
            st.bar_chart(risk_counts)
        
        col3, col4 = st.columns(2)
        
        with col3:
            st.write("**Top 10 Mã CK**")
            top_ma = df['Mã CK'].value_counts().head(10)
            st.bar_chart(top_ma)
        
        with col4:
            st.write("**Phân bố theo Sàn**")
            san_counts = df['Sàn'].value_counts()
            st.bar_chart(san_counts)
        
        # Thống kê chi tiết
        st.markdown("---")
        st.subheader("📈 CHI TIẾT THEO MÃ CK")
        
        with st.expander("Xem chi tiết"):
            # Tạo bảng tổng hợp
            summary = df.groupby('Mã CK').agg({
                'Tiêu đề': 'count',
                'Điểm': 'mean',
                'Risk': lambda x: x.mode()[0] if len(x) > 0 else 'N/A'
            }).rename(columns={
                'Tiêu đề': 'Số bài',
                'Điểm': 'Sentiment TB',
                'Risk': 'Risk chính'
            }).reset_index()
            
            # Thêm tên công ty
            summary = summary.merge(
                df[['Mã CK', 'Tên công ty', 'Sàn']].drop_duplicates(),
                on='Mã CK',
                how='left'
            )
            
            summary['Sentiment TB'] = summary['Sentiment TB'].round(1)
            summary = summary.sort_values('Số bài', ascending=False)
            
            st.dataframe(
                summary,
                use_container_width=True,
                hide_index=True
            )

if __name__ == "__main__":
    main()
