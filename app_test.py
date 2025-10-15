# ============================================================
# 🎯 STREAMLIT WEB APP V2.4 - UPLOAD + SUMMARIZE
# ============================================================
# ✅ Upload danh sách mã CK
# ✅ Tóm tắt extractive (từ V1.0)
# ✅ Sentiment analysis
# ✅ Risk detection
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
    page_title="Cào Tin Chứng Khoán V2.4",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS
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
</style>
""", unsafe_allow_html=True)

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_default_stock_list():
    """Danh sách mã mặc định"""
    default_data = {
        'Mã CK': ['SHS', 'PVS', 'NVB', 'VCS', 'BVS', 'CEO', 'VGC', 'PVC',
                  'LPB', 'EIB', 'BAB', 'OCB', 'HDG', 'PAN'],
        'Sàn': ['HNX']*8 + ['UPCoM']*6,
        'Tên công ty': ['Chứng khoán SHS', 'Chứng khoán PVS', 'Ngân hàng NVB',
                        'Chứng khoán VCS', 'Chứng khoán BVS', 'Tập đoàn CEO',
                        'Viglacera', 'PVC', 'Ngân hàng LPB', 'Ngân hàng EIB',
                        'Ngân hàng BAB', 'Ngân hàng OCB', 'Tập đoàn HDG', 'PAN Group']
    }
    return pd.DataFrame(default_data)

def parse_stock_file(uploaded_file):
    """Parse Excel/CSV file"""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = df.columns.str.strip().str.lower()
        
        column_mapping = {
            'mã ck': 'Mã CK', 'ma ck': 'Mã CK', 'mã': 'Mã CK', 'code': 'Mã CK',
            'sàn': 'Sàn', 'san': 'Sàn', 'exchange': 'Sàn',
            'tên công ty': 'Tên công ty', 'ten cong ty': 'Tên công ty', 'name': 'Tên công ty',
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)
        
        required_cols = ['Mã CK', 'Sàn']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            return None, f"Thiếu các cột: {', '.join(missing_cols)}"
        
        if 'Tên công ty' not in df.columns:
            df['Tên công ty'] = ''
        
        df['Mã CK'] = df['Mã CK'].astype(str).str.strip().str.upper()
        df['Sàn'] = df['Sàn'].astype(str).str.strip().str.upper()
        df['Tên công ty'] = df['Tên công ty'].astype(str).str.strip()
        
        df = df[df['Sàn'].isin(['HNX', 'UPCOM'])]
        df['Sàn'] = df['Sàn'].replace('UPCOM', 'UPCoM')
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
# KEYWORD RISK DETECTOR
# ============================================================

class KeywordRiskDetector:
    def __init__(self):
        self.keywords_db = {
            # A. Nội bộ & Quản trị
            "lãnh đạo bị bắt": {"category": "A. Nội bộ", "severity": "severe", "score": -95, "violation": "I.2, II.A"},
            "lãnh đạo bỏ trốn": {"category": "A. Nội bộ", "severity": "severe", "score": -95, "violation": "I.2, II.A"},
            "cổ đông lớn bán chui": {"category": "A. Nội bộ", "severity": "severe", "score": -85, "violation": "I.1, II.A"},
            "chủ tịch bất ngờ thoái hết vốn": {"category": "A. Nội bộ", "severity": "severe", "score": -85, "violation": "I.1, II.A"},
            
            # B. Tài chính
            "bất ngờ báo lỗ": {"category": "B. Tài chính", "severity": "severe", "score": -80, "violation": "I.4, II.B"},
            "âm vốn chủ": {"category": "B. Tài chính", "severity": "severe", "score": -90, "violation": "II.B"},
            "mất khả năng thanh toán": {"category": "B. Tài chính", "severity": "severe", "score": -90, "violation": "II.B"},
            "nợ xấu bất thường": {"category": "B. Tài chính", "severity": "severe", "score": -80, "violation": "II.B"},
            
            # C. Thao túng & Biến động giá bất thường
            "đội lái làm giá": {"category": "C. Thao túng", "severity": "severe", "score": -95, "violation": "I.3, II.C"},
            "tăng trần liên tiếp": {"category": "C. Thao túng", "severity": "warning", "score": -60, "violation": "I.2, II.C"},
            "giảm sàn liên tục": {"category": "C. Thao túng", "severity": "warning", "score": -70, "violation": "I.2, II.C"},
            "bốc đầu": {"category": "C. Thao túng", "severity": "warning", "score": -65, "violation": "I.2, I.3, II.C"},
            "kịch trần": {"category": "C. Thao túng", "severity": "warning", "score": -65, "violation": "I.2, I.3, II.C"},
            "rớt đáy": {"category": "C. Thao túng", "severity": "warning", "score": -70, "violation": "I.2, I.3, II.C"},
            "cổ phiếu tăng phi mã": {"category": "C. Thao túng", "severity": "warning", "score": -65, "violation": "I.2, I.4, II.C"},
            "tăng dựng đứng": {"category": "C. Thao túng", "severity": "warning", "score": -60, "violation": "I.2, II.C"},
            "khối lượng tăng bất thường": {"category": "C. Thao túng", "severity": "warning", "score": -65, "violation": "I.6, II.C"},
            "giao dịch nội gián": {"category": "C. Thao túng", "severity": "severe", "score": -90, "violation": "I.1, II.C"},
            
            # D. M&A
            "niêm yết cửa sau": {"category": "D. M&A", "severity": "severe", "score": -85, "violation": "I.5, II.D"},
            "thâu tóm": {"category": "D. M&A", "severity": "warning", "score": -50, "violation": "I.5, II.D"},
            
            # E. Pháp lý
            "công an điều tra": {"category": "E. Pháp lý", "severity": "severe", "score": -90, "violation": "II.E"},
            "khởi tố lãnh đạo": {"category": "E. Pháp lý", "severity": "severe", "score": -95, "violation": "II.E"},
            "gian lận tài chính": {"category": "E. Pháp lý", "severity": "severe", "score": -95, "violation": "II.E"},
            
            # F. Sự kiện bên ngoài
            "cháy nhà xưởng": {"category": "F. Sự kiện ngoài", "severity": "severe", "score": -75, "violation": "II.F"},
            "bị thu hồi giấy phép": {"category": "F. Sự kiện ngoài", "severity": "severe", "score": -90, "violation": "II.F"},
            
            # Tích cực
            "lợi nhuận tăng": {"category": "Tích cực", "severity": "positive", "score": 70, "violation": ""},
            "tăng trưởng mạnh": {"category": "Tích cực", "severity": "positive", "score": 65, "violation": ""},
            "doanh thu kỷ lục": {"category": "Tích cực", "severity": "positive", "score": 75, "violation": ""},
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

# ============================================================
# SENTIMENT ANALYZER
# ============================================================

class SimpleSentimentAnalyzer:
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

# ============================================================
# STOCK SCRAPER
# ============================================================

class StockScraperWeb:
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
        
        # Load stock list
        self.stock_df = stock_df
        self.hnx_stocks = set(stock_df[stock_df['Sàn'] == 'HNX']['Mã CK'].tolist())
        self.upcom_stocks = set(stock_df[stock_df['Sàn'] == 'UPCoM']['Mã CK'].tolist())
        
        self.code_to_name = dict(zip(stock_df['Mã CK'], stock_df['Tên công ty']))
        
        self.name_to_code = {}
        for code, name in self.code_to_name.items():
            if name:
                words = name.lower().split()
                for word in words:
                    if len(word) > 3:
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
        """Làm sạch text - từ V1.0"""
        if not text:
            return ""
        text = re.sub(r'[^\w\s.,;:!?()%\-\+\/\"\'àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def advanced_summarize(self, content, title, max_sentences=4):
        """Tóm tắt EXTRACTIVE - từ V1.0"""
        content = self.clean_text(content)
        title = self.clean_text(title)
        
        if not content or len(content) < 100:
            return content
        
        full_text = title + ". " + content
        sentences = re.split(r'[.!?]+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
        
        if len(sentences) <= max_sentences:
            return '. '.join(sentences) + '.'
        
        important_keywords = {
            'tăng': 3, 'giảm': 3, 'tăng trưởng': 3,
            'lợi nhuận': 4, 'doanh thu': 4, 'lỗ': 3,
            'tỷ đồng': 3, 'nghìn tỷ': 4,
            'cổ phiếu': 3, 'niêm yết': 3,
            'giao dịch': 2, 'thanh khoản': 3,
            'quý': 3, 'năm': 2,
            'phát hành': 3, 'trái phiếu': 3,
            'đầu tư': 2, 'vốn': 3,
        }
        
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = 0
            sentence_lower = sentence.lower()
            
            if i == 0:
                score += 5
            elif i == 1:
                score += 3
            elif i < 5:
                score += 1
            
            for keyword, weight in important_keywords.items():
                if keyword in sentence_lower:
                    score += weight
            
            numbers = re.findall(r'\d+(?:[.,]\d+)*', sentence)
            if numbers:
                score += len(numbers)
                if any(num for num in numbers if len(num.replace('.', '').replace(',', '')) >= 4):
                    score += 2
            
            if '%' in sentence:
                score += 3
            
            word_count = len(sentence.split())
            if 12 <= word_count <= 35:
                score += 2
            elif word_count < 8 or word_count > 50:
                score -= 1
            
            for code in list(self.hnx_stocks) + list(self.upcom_stocks):
                if code in sentence.upper():
                    score += 3
                    break
            
            scored_sentences.append((sentence, score, i))
        
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        top_sentences = scored_sentences[:max_sentences]
        top_sentences.sort(key=lambda x: x[2])
        
        summary = '. '.join([s[0] for s in top_sentences])
        if not summary.endswith('.'):
            summary += '.'
        
        summary = self.clean_text(summary)
        return summary
    
    def extract_stock(self, text):
        """Trích xuất mã CK - Xử lý đặc biệt TOP, TIN, CEO"""
        text_upper = text.upper()
        text_lower = text.lower()
        
        # BLACKLIST - Mở rộng
        blacklist_patterns = [
            # Tin tổng quan thị trường
            r'CHỨNG KHOÁN\s+\w+\s+CÓ\s+NHẬN ĐỊNH',
            r'CHỨNG KHOÁN\s+\w+\s+DỰ BÁO',
            r'CHỨNG KHOÁN\s+\w+\s+PHÂN TÍCH',
            r'CÔNG TY\s+CHỨNG KHOÁN',
            r'CTCK\s+\w+',
            
            # Index
            r'VN-INDEX',
            r'HNX-INDEX',
            r'UPCOM-INDEX',
            
            # Top cổ phiếu (tránh nhầm với mã TOP)
            r'TOP\s+CỔ\s+PHIẾU',
            r'TOP\s+\d+',
            r'TOP\s+MÃ',
            
            # Tin tức (tránh nhầm với mã TIN)
            r'TIN\s+VUI',
            r'TIN\s+TỐT',
            r'TIN\s+XẤU',
            r'TIN\s+VẮN',
            r'TIN\s+CHỨNG\s+KHOÁN',
            r'TIN\s+THỊ\s+TRƯỜNG',
            r'NHẬN\s+TIN',
            r'THEO\s+TIN',
            r'MỘT\s+TIN',
            r'CÁC\s+TIN',
            r'NHIỀU\s+TIN',
            
            # CEO (tránh nhầm với mã CEO)
            r'CEO\s+CÔNG\s+TY',
            r'CEO\s+CỦA',
            r'CEO\s+MỚI',
            r'GIÁM\s+ĐỐC\s+CEO',
            r'TỔNG\s+GIÁM\s+ĐỐC\s+CEO',
            
            # Tổng quan
            r'THỊ TRƯỜNG CHUNG',
            r'DIỄN BIẾN THỊ TRƯỜNG',
            r'TỔNG QUAN THỊ TRƯỜNG',
            r'ĐIỂM TIN',
            r'BẢN TIN',
        ]
        
        for pattern in blacklist_patterns:
            if re.search(pattern, text_upper):
                return None, None, None
        
        # Tìm theo mã
        for code in self.hnx_stocks:
            match = re.search(r'\b' + code + r'\b', text_upper)
            if match:
                context = text_upper[max(0, match.start()-15):match.end()+15]
                
                # Check context xung quanh
                if re.search(r'CHỨNG KHOÁN\s+' + code, context):
                    continue
                if re.search(r'CTCK\s+' + code, context):
                    continue
                
                # ĐẶC BIỆT 1: Mã "TOP"
                if code == 'TOP':
                    if match.start() > 0:
                        prev_char = text_upper[match.start()-1]
                        if prev_char.isalnum():
                            continue
                    
                    if match.end() < len(text_upper) - 1:
                        next_chars = text_upper[match.end():match.end()+15]
                        if re.match(r'\s+\d+', next_chars):
                            continue
                        if re.match(r'\s+(CỔ|MÃ)', next_chars):
                            continue
                
                # ĐẶC BIỆT 2: Mã "TIN"
                if code == 'TIN':
                    # Check từ TRƯỚC "TIN"
                    if match.start() >= 5:
                        prev_words = text_upper[match.start()-15:match.start()]
                        if re.search(r'(NHẬN|THEO|MỘT|CÁC|NHIỀU)\s*$'):
    
   def fetch_url(self, url, max_retries=2):
    for attempt in range(max_retries):
        try:
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                return None
    
    def fetch_article_content(self, url):
        """Lấy nội dung bài viết - từ V1.0"""
        try:
            response = self.fetch_url(url)
            if not response:
                return None, None, None
            
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm ngày
            date_text = None
            for pattern in [
                {'class': re.compile(r'date|time|publish', re.I)},
                {'itemprop': 'datePublished'}
            ]:
                date_elem = soup.find(['time', 'span', 'div'], pattern)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    break
            
            # Parse ngày (GMT+7)
            article_date_str = datetime.now(self.vietnam_tz).strftime('%d/%m/%Y')
            article_date_obj = datetime.now(self.vietnam_tz)
            
            # Tìm nội dung
            content = ""
            for selector in [
                ('article', {}),
                ('div', {'class': re.compile(r'content|article|detail', re.I)}),
            ]:
                content_div = soup.find(selector[0], selector[1])
                if content_div:
                    paragraphs = content_div.find_all('p')
                    content = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
                    if content:
                        break
            
            if not content:
                paragraphs = soup.find_all('p')
                valid_p = [p.get_text(strip=True) for p in paragraphs if 50 < len(p.get_text(strip=True)) < 1000]
                content = ' '.join(valid_p[:8])
            
            content = self.clean_text(content)
            return content, article_date_str, article_date_obj
        
        except:
            return None, None, None
    
    def scrape_source(self, url, source_name, pattern, max_articles=20, progress_callback=None):
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
                            
                            if match_method == 'code':
                                self.stats['found_by_code'] += 1
                            else:
                                self.stats['found_by_name'] += 1
                            
                            company_name = self.code_to_name.get(stock_code, '')
                            
                            # FETCH NỘI DUNG ĐẦY ĐỦ
                            content, article_date_str, article_date_obj = self.fetch_article_content(full_link)
                            
                            if content:
                                # TÓM TẮT
                                summary = self.advanced_summarize(content, title, max_sentences=4)
                            else:
                                content = ""
                                summary = title  # Fallback nếu không lấy được content
                            
                            # SENTIMENT
                            sentiment_result = self.sentiment_analyzer.analyze_sentiment(title, content)
                            
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
                                'Ngày': article_date_str,
                                'Mã CK': stock_code,
                                'Tên công ty': company_name,
                                'Sàn': exchange,
                                'Sentiment': sentiment_result['sentiment_label'],
                                'Điểm': sentiment_result['sentiment_score'],
                                'Risk': sentiment_result['risk_level'],
                                'Vi phạm': sentiment_result['violations'],
                                'Keywords': "; ".join([k['keyword'] for k in sentiment_result['keywords'][:3]]),
                                'Nội dung tóm tắt': summary,  # ← CỘT MỚI
                                'Tìm theo': 'Mã CK' if match_method == 'code' else 'Tên công ty'
                            })
                            
                            count += 1
                            time.sleep(0.5)
                            
                            if count >= max_articles:
                                break
            
            return count
        
        except Exception as e:
            st.error(f"Lỗi {source_name}: {str(e)}")
            return 0
    
    def run(self, max_articles_per_source=20, progress_callback=None):
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
    st.markdown('<div class="main-header">📈 TOOL CÀO TIN V2.4</div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;color:#666;margin-bottom:2rem;">HNX & UPCoM - Upload + Summarize + Sentiment</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ CÀI ĐẶT")
        
        st.subheader("📂 DANH SÁCH MÃ CK")
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        st.write("**Upload file Excel/CSV**")
        st.caption("Gồm 3 cột: Mã CK | Sàn | Tên công ty")
        
        uploaded_file = st.file_uploader(
            "Chọn file",
            type=['xlsx', 'xls', 'csv'],
            help="File phải có các cột: Mã CK, Sàn (HNX/UPCoM), Tên công ty"
        )
        
        sample_excel = create_sample_excel()
        st.download_button(
            label="📥 Tải file mẫu",
            data=sample_excel,
            file_name="mau_danh_sach_ma_ck.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        if uploaded_file is not None:
            stock_df, error = parse_stock_file(uploaded_file)
            
            if error:
                st.error(f"❌ {error}")
                st.session_state['stock_df'] = load_default_stock_list()
            else:
                st.success(f"✅ Đã load {len(stock_df)} mã CK")
                st.session_state['stock_df'] = stock_df
                
                hnx_count = len(stock_df[stock_df['Sàn'] == 'HNX'])
                upcom_count = len(stock_df[stock_df['Sàn'] == 'UPCoM'])
                st.info(f"HNX: {hnx_count} | UPCoM: {upcom_count}")
        else:
            if 'stock_df' not in st.session_state:
                st.session_state['stock_df'] = load_default_stock_list()
                st.warning("⚠️ Đang dùng danh sách mặc định")
        
        st.markdown("---")
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
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(progress)
            
            scraper = StockScraperWeb(stock_df, time_filter_hours=time_filter)
            df = scraper.run(max_articles_per_source=max_articles, progress_callback=update_progress)
            
            progress_bar.empty()
            status_text.empty()
            
            if df is not None:
                st.success(f"✅ Hoàn tất! Tìm thấy {len(df)} bài viết")
                st.info(f"🔍 Tìm theo mã CK: {scraper.stats['found_by_code']} | Tìm theo tên: {scraper.stats['found_by_name']}")
                
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
            df.to_excel(writer, index=False, sheet_name='Tất cả')
            
            df_severe = df[df['Risk'] == 'Nghiêm trọng']
            if len(df_severe) > 0:
                df_severe.to_excel(writer, index=False, sheet_name='Nghiêm trọng')
            
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
                
                # HIỂN THỊ TÓM TẮT
                if pd.notna(row['Nội dung tóm tắt']) and row['Nội dung tóm tắt']:
                    with st.expander("📝 Xem tóm tắt"):
                        st.write(row['Nội dung tóm tắt'])
                
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
        
        # Chi tiết theo mã
        st.markdown("---")
        st.subheader("📈 CHI TIẾT THEO MÃ CK")
        
        with st.expander("Xem chi tiết"):
            summary = df.groupby('Mã CK').agg({
                'Tiêu đề': 'count',
                'Điểm': 'mean',
                'Risk': lambda x: x.mode()[0] if len(x) > 0 else 'N/A'
            }).rename(columns={
                'Tiêu đề': 'Số bài',
                'Điểm': 'Sentiment TB',
                'Risk': 'Risk chính'
            }).reset_index()
            
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
    main(), prev_words):
                            continue
                    
                    # Check từ SAU "TIN"
                    if match.end() < len(text_upper) - 5:
                        next_chars = text_upper[match.end():match.end()+20]
                        if re.match(r'\s+(VUI|TỐT|XẤU|VẮN|CHỨNG|THỊ)', next_chars):
                            continue
                
                # ĐẶC BIỆT 3: Mã "CEO"
                if code == 'CEO':
                    # Check từ SAU "CEO"
                    if match.end() < len(text_upper) - 5:
                        next_chars = text_upper[match.end():match.end()+15]
                        if re.match(r'\s+(CÔNG\s+TY|CỦA|MỚI)', next_chars):
                            continue
                    
                    # Check từ TRƯỚC "CEO"
                    if match.start() >= 10:
                        prev_words = text_upper[match.start()-20:match.start()]
                        if re.search(r'(GIÁM\s+ĐỐC|TỔNG\s+GIÁM\s+ĐỐC)\s*$'):
    
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
    
    def fetch_article_content(self, url):
        """Lấy nội dung bài viết - từ V1.0"""
        try:
            response = self.fetch_url(url)
            if not response:
                return None, None, None
            
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm ngày
            date_text = None
            for pattern in [
                {'class': re.compile(r'date|time|publish', re.I)},
                {'itemprop': 'datePublished'}
            ]:
                date_elem = soup.find(['time', 'span', 'div'], pattern)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    break
            
            # Parse ngày (GMT+7)
            article_date_str = datetime.now(self.vietnam_tz).strftime('%d/%m/%Y')
            article_date_obj = datetime.now(self.vietnam_tz)
            
            # Tìm nội dung
            content = ""
            for selector in [
                ('article', {}),
                ('div', {'class': re.compile(r'content|article|detail', re.I)}),
            ]:
                content_div = soup.find(selector[0], selector[1])
                if content_div:
                    paragraphs = content_div.find_all('p')
                    content = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
                    if content:
                        break
            
            if not content:
                paragraphs = soup.find_all('p')
                valid_p = [p.get_text(strip=True) for p in paragraphs if 50 < len(p.get_text(strip=True)) < 1000]
                content = ' '.join(valid_p[:8])
            
            content = self.clean_text(content)
            return content, article_date_str, article_date_obj
        
        except:
            return None, None, None
    
    def scrape_source(self, url, source_name, pattern, max_articles=20, progress_callback=None):
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
                            
                            if match_method == 'code':
                                self.stats['found_by_code'] += 1
                            else:
                                self.stats['found_by_name'] += 1
                            
                            company_name = self.code_to_name.get(stock_code, '')
                            
                            # FETCH NỘI DUNG ĐẦY ĐỦ
                            content, article_date_str, article_date_obj = self.fetch_article_content(full_link)
                            
                            if content:
                                # TÓM TẮT
                                summary = self.advanced_summarize(content, title, max_sentences=4)
                            else:
                                content = ""
                                summary = title  # Fallback nếu không lấy được content
                            
                            # SENTIMENT
                            sentiment_result = self.sentiment_analyzer.analyze_sentiment(title, content)
                            
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
                                'Ngày': article_date_str,
                                'Mã CK': stock_code,
                                'Tên công ty': company_name,
                                'Sàn': exchange,
                                'Sentiment': sentiment_result['sentiment_label'],
                                'Điểm': sentiment_result['sentiment_score'],
                                'Risk': sentiment_result['risk_level'],
                                'Vi phạm': sentiment_result['violations'],
                                'Keywords': "; ".join([k['keyword'] for k in sentiment_result['keywords'][:3]]),
                                'Nội dung tóm tắt': summary,  # ← CỘT MỚI
                                'Tìm theo': 'Mã CK' if match_method == 'code' else 'Tên công ty'
                            })
                            
                            count += 1
                            time.sleep(0.5)
                            
                            if count >= max_articles:
                                break
            
            return count
        
        except Exception as e:
            st.error(f"Lỗi {source_name}: {str(e)}")
            return 0
    
    def run(self, max_articles_per_source=20, progress_callback=None):
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
    st.markdown('<div class="main-header">📈 TOOL CÀO TIN V2.4</div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;color:#666;margin-bottom:2rem;">HNX & UPCoM - Upload + Summarize + Sentiment</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ CÀI ĐẶT")
        
        st.subheader("📂 DANH SÁCH MÃ CK")
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        st.write("**Upload file Excel/CSV**")
        st.caption("Gồm 3 cột: Mã CK | Sàn | Tên công ty")
        
        uploaded_file = st.file_uploader(
            "Chọn file",
            type=['xlsx', 'xls', 'csv'],
            help="File phải có các cột: Mã CK, Sàn (HNX/UPCoM), Tên công ty"
        )
        
        sample_excel = create_sample_excel()
        st.download_button(
            label="📥 Tải file mẫu",
            data=sample_excel,
            file_name="mau_danh_sach_ma_ck.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        if uploaded_file is not None:
            stock_df, error = parse_stock_file(uploaded_file)
            
            if error:
                st.error(f"❌ {error}")
                st.session_state['stock_df'] = load_default_stock_list()
            else:
                st.success(f"✅ Đã load {len(stock_df)} mã CK")
                st.session_state['stock_df'] = stock_df
                
                hnx_count = len(stock_df[stock_df['Sàn'] == 'HNX'])
                upcom_count = len(stock_df[stock_df['Sàn'] == 'UPCoM'])
                st.info(f"HNX: {hnx_count} | UPCoM: {upcom_count}")
        else:
            if 'stock_df' not in st.session_state:
                st.session_state['stock_df'] = load_default_stock_list()
                st.warning("⚠️ Đang dùng danh sách mặc định")
        
        st.markdown("---")
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
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(progress)
            
            scraper = StockScraperWeb(stock_df, time_filter_hours=time_filter)
            df = scraper.run(max_articles_per_source=max_articles, progress_callback=update_progress)
            
            progress_bar.empty()
            status_text.empty()
            
            if df is not None:
                st.success(f"✅ Hoàn tất! Tìm thấy {len(df)} bài viết")
                st.info(f"🔍 Tìm theo mã CK: {scraper.stats['found_by_code']} | Tìm theo tên: {scraper.stats['found_by_name']}")
                
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
            df.to_excel(writer, index=False, sheet_name='Tất cả')
            
            df_severe = df[df['Risk'] == 'Nghiêm trọng']
            if len(df_severe) > 0:
                df_severe.to_excel(writer, index=False, sheet_name='Nghiêm trọng')
            
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
                
                # HIỂN THỊ TÓM TẮT
                if pd.notna(row['Nội dung tóm tắt']) and row['Nội dung tóm tắt']:
                    with st.expander("📝 Xem tóm tắt"):
                        st.write(row['Nội dung tóm tắt'])
                
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
        
        # Chi tiết theo mã
        st.markdown("---")
        st.subheader("📈 CHI TIẾT THEO MÃ CK")
        
        with st.expander("Xem chi tiết"):
            summary = df.groupby('Mã CK').agg({
                'Tiêu đề': 'count',
                'Điểm': 'mean',
                'Risk': lambda x: x.mode()[0] if len(x) > 0 else 'N/A'
            }).rename(columns={
                'Tiêu đề': 'Số bài',
                'Điểm': 'Sentiment TB',
                'Risk': 'Risk chính'
            }).reset_index()
            
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
    main(), prev_words):
                            continue
                
                return code, 'HNX', 'code'
        
        for code in self.upcom_stocks:
            match = re.search(r'\b' + code + r'\b', text_upper)
            if match:
                context = text_upper[max(0, match.start()-15):match.end()+15]
                
                if re.search(r'CHỨNG KHOÁN\s+' + code, context):
                    continue
                if re.search(r'CTCK\s+' + code, context):
                    continue
                
                # Áp dụng logic đặc biệt cho TOP, TIN, CEO nếu có trong UPCoM
                if code == 'TOP':
                    if match.start() > 0:
                        prev_char = text_upper[match.start()-1]
                        if prev_char.isalnum():
                            continue
                    if match.end() < len(text_upper) - 1:
                        next_chars = text_upper[match.end():match.end()+15]
                        if re.match(r'\s+\d+', next_chars) or re.match(r'\s+(CỔ|MÃ)', next_chars):
                            continue
                
                if code == 'TIN':
                    if match.start() >= 5:
                        prev_words = text_upper[match.start()-15:match.start()]
                        if re.search(r'(NHẬN|THEO|MỘT|CÁC|NHIỀU)\s*$'):
    
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
    
    def fetch_article_content(self, url):
        """Lấy nội dung bài viết - từ V1.0"""
        try:
            response = self.fetch_url(url)
            if not response:
                return None, None, None
            
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm ngày
            date_text = None
            for pattern in [
                {'class': re.compile(r'date|time|publish', re.I)},
                {'itemprop': 'datePublished'}
            ]:
                date_elem = soup.find(['time', 'span', 'div'], pattern)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    break
            
            # Parse ngày (GMT+7)
            article_date_str = datetime.now(self.vietnam_tz).strftime('%d/%m/%Y')
            article_date_obj = datetime.now(self.vietnam_tz)
            
            # Tìm nội dung
            content = ""
            for selector in [
                ('article', {}),
                ('div', {'class': re.compile(r'content|article|detail', re.I)}),
            ]:
                content_div = soup.find(selector[0], selector[1])
                if content_div:
                    paragraphs = content_div.find_all('p')
                    content = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
                    if content:
                        break
            
            if not content:
                paragraphs = soup.find_all('p')
                valid_p = [p.get_text(strip=True) for p in paragraphs if 50 < len(p.get_text(strip=True)) < 1000]
                content = ' '.join(valid_p[:8])
            
            content = self.clean_text(content)
            return content, article_date_str, article_date_obj
        
        except:
            return None, None, None
    
    def scrape_source(self, url, source_name, pattern, max_articles=20, progress_callback=None):
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
                            
                            if match_method == 'code':
                                self.stats['found_by_code'] += 1
                            else:
                                self.stats['found_by_name'] += 1
                            
                            company_name = self.code_to_name.get(stock_code, '')
                            
                            # FETCH NỘI DUNG ĐẦY ĐỦ
                            content, article_date_str, article_date_obj = self.fetch_article_content(full_link)
                            
                            if content:
                                # TÓM TẮT
                                summary = self.advanced_summarize(content, title, max_sentences=4)
                            else:
                                content = ""
                                summary = title  # Fallback nếu không lấy được content
                            
                            # SENTIMENT
                            sentiment_result = self.sentiment_analyzer.analyze_sentiment(title, content)
                            
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
                                'Ngày': article_date_str,
                                'Mã CK': stock_code,
                                'Tên công ty': company_name,
                                'Sàn': exchange,
                                'Sentiment': sentiment_result['sentiment_label'],
                                'Điểm': sentiment_result['sentiment_score'],
                                'Risk': sentiment_result['risk_level'],
                                'Vi phạm': sentiment_result['violations'],
                                'Keywords': "; ".join([k['keyword'] for k in sentiment_result['keywords'][:3]]),
                                'Nội dung tóm tắt': summary,  # ← CỘT MỚI
                                'Tìm theo': 'Mã CK' if match_method == 'code' else 'Tên công ty'
                            })
                            
                            count += 1
                            time.sleep(0.5)
                            
                            if count >= max_articles:
                                break
            
            return count
        
        except Exception as e:
            st.error(f"Lỗi {source_name}: {str(e)}")
            return 0
    
    def run(self, max_articles_per_source=20, progress_callback=None):
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
    st.markdown('<div class="main-header">📈 TOOL CÀO TIN V2.4</div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;color:#666;margin-bottom:2rem;">HNX & UPCoM - Upload + Summarize + Sentiment</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ CÀI ĐẶT")
        
        st.subheader("📂 DANH SÁCH MÃ CK")
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        st.write("**Upload file Excel/CSV**")
        st.caption("Gồm 3 cột: Mã CK | Sàn | Tên công ty")
        
        uploaded_file = st.file_uploader(
            "Chọn file",
            type=['xlsx', 'xls', 'csv'],
            help="File phải có các cột: Mã CK, Sàn (HNX/UPCoM), Tên công ty"
        )
        
        sample_excel = create_sample_excel()
        st.download_button(
            label="📥 Tải file mẫu",
            data=sample_excel,
            file_name="mau_danh_sach_ma_ck.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        if uploaded_file is not None:
            stock_df, error = parse_stock_file(uploaded_file)
            
            if error:
                st.error(f"❌ {error}")
                st.session_state['stock_df'] = load_default_stock_list()
            else:
                st.success(f"✅ Đã load {len(stock_df)} mã CK")
                st.session_state['stock_df'] = stock_df
                
                hnx_count = len(stock_df[stock_df['Sàn'] == 'HNX'])
                upcom_count = len(stock_df[stock_df['Sàn'] == 'UPCoM'])
                st.info(f"HNX: {hnx_count} | UPCoM: {upcom_count}")
        else:
            if 'stock_df' not in st.session_state:
                st.session_state['stock_df'] = load_default_stock_list()
                st.warning("⚠️ Đang dùng danh sách mặc định")
        
        st.markdown("---")
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
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(progress)
            
            scraper = StockScraperWeb(stock_df, time_filter_hours=time_filter)
            df = scraper.run(max_articles_per_source=max_articles, progress_callback=update_progress)
            
            progress_bar.empty()
            status_text.empty()
            
            if df is not None:
                st.success(f"✅ Hoàn tất! Tìm thấy {len(df)} bài viết")
                st.info(f"🔍 Tìm theo mã CK: {scraper.stats['found_by_code']} | Tìm theo tên: {scraper.stats['found_by_name']}")
                
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
            df.to_excel(writer, index=False, sheet_name='Tất cả')
            
            df_severe = df[df['Risk'] == 'Nghiêm trọng']
            if len(df_severe) > 0:
                df_severe.to_excel(writer, index=False, sheet_name='Nghiêm trọng')
            
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
                
                # HIỂN THỊ TÓM TẮT
                if pd.notna(row['Nội dung tóm tắt']) and row['Nội dung tóm tắt']:
                    with st.expander("📝 Xem tóm tắt"):
                        st.write(row['Nội dung tóm tắt'])
                
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
        
        # Chi tiết theo mã
        st.markdown("---")
        st.subheader("📈 CHI TIẾT THEO MÃ CK")
        
        with st.expander("Xem chi tiết"):
            summary = df.groupby('Mã CK').agg({
                'Tiêu đề': 'count',
                'Điểm': 'mean',
                'Risk': lambda x: x.mode()[0] if len(x) > 0 else 'N/A'
            }).rename(columns={
                'Tiêu đề': 'Số bài',
                'Điểm': 'Sentiment TB',
                'Risk': 'Risk chính'
            }).reset_index()
            
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
    main(), prev_words):
                            continue
                    if match.end() < len(text_upper) - 5:
                        next_chars = text_upper[match.end():match.end()+20]
                        if re.match(r'\s+(VUI|TỐT|XẤU|VẮN|CHỨNG|THỊ)', next_chars):
                            continue
                
                if code == 'CEO':
                    if match.end() < len(text_upper) - 5:
                        next_chars = text_upper[match.end():match.end()+15]
                        if re.match(r'\s+(CÔNG\s+TY|CỦA|MỚI)', next_chars):
                            continue
                    if match.start() >= 10:
                        prev_words = text_upper[match.start()-20:match.start()]
                        if re.search(r'(GIÁM\s+ĐỐC|TỔNG\s+GIÁM\s+ĐỐC)\s*$'):
    
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
    
    def fetch_article_content(self, url):
        """Lấy nội dung bài viết - từ V1.0"""
        try:
            response = self.fetch_url(url)
            if not response:
                return None, None, None
            
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm ngày
            date_text = None
            for pattern in [
                {'class': re.compile(r'date|time|publish', re.I)},
                {'itemprop': 'datePublished'}
            ]:
                date_elem = soup.find(['time', 'span', 'div'], pattern)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    break
            
            # Parse ngày (GMT+7)
            article_date_str = datetime.now(self.vietnam_tz).strftime('%d/%m/%Y')
            article_date_obj = datetime.now(self.vietnam_tz)
            
            # Tìm nội dung
            content = ""
            for selector in [
                ('article', {}),
                ('div', {'class': re.compile(r'content|article|detail', re.I)}),
            ]:
                content_div = soup.find(selector[0], selector[1])
                if content_div:
                    paragraphs = content_div.find_all('p')
                    content = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
                    if content:
                        break
            
            if not content:
                paragraphs = soup.find_all('p')
                valid_p = [p.get_text(strip=True) for p in paragraphs if 50 < len(p.get_text(strip=True)) < 1000]
                content = ' '.join(valid_p[:8])
            
            content = self.clean_text(content)
            return content, article_date_str, article_date_obj
        
        except:
            return None, None, None
    
    def scrape_source(self, url, source_name, pattern, max_articles=20, progress_callback=None):
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
                            
                            if match_method == 'code':
                                self.stats['found_by_code'] += 1
                            else:
                                self.stats['found_by_name'] += 1
                            
                            company_name = self.code_to_name.get(stock_code, '')
                            
                            # FETCH NỘI DUNG ĐẦY ĐỦ
                            content, article_date_str, article_date_obj = self.fetch_article_content(full_link)
                            
                            if content:
                                # TÓM TẮT
                                summary = self.advanced_summarize(content, title, max_sentences=4)
                            else:
                                content = ""
                                summary = title  # Fallback nếu không lấy được content
                            
                            # SENTIMENT
                            sentiment_result = self.sentiment_analyzer.analyze_sentiment(title, content)
                            
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
                                'Ngày': article_date_str,
                                'Mã CK': stock_code,
                                'Tên công ty': company_name,
                                'Sàn': exchange,
                                'Sentiment': sentiment_result['sentiment_label'],
                                'Điểm': sentiment_result['sentiment_score'],
                                'Risk': sentiment_result['risk_level'],
                                'Vi phạm': sentiment_result['violations'],
                                'Keywords': "; ".join([k['keyword'] for k in sentiment_result['keywords'][:3]]),
                                'Nội dung tóm tắt': summary,  # ← CỘT MỚI
                                'Tìm theo': 'Mã CK' if match_method == 'code' else 'Tên công ty'
                            })
                            
                            count += 1
                            time.sleep(0.5)
                            
                            if count >= max_articles:
                                break
            
            return count
        
        except Exception as e:
            st.error(f"Lỗi {source_name}: {str(e)}")
            return 0
    
    def run(self, max_articles_per_source=20, progress_callback=None):
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
    st.markdown('<div class="main-header">📈 TOOL CÀO TIN V2.4</div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;color:#666;margin-bottom:2rem;">HNX & UPCoM - Upload + Summarize + Sentiment</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ CÀI ĐẶT")
        
        st.subheader("📂 DANH SÁCH MÃ CK")
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        st.write("**Upload file Excel/CSV**")
        st.caption("Gồm 3 cột: Mã CK | Sàn | Tên công ty")
        
        uploaded_file = st.file_uploader(
            "Chọn file",
            type=['xlsx', 'xls', 'csv'],
            help="File phải có các cột: Mã CK, Sàn (HNX/UPCoM), Tên công ty"
        )
        
        sample_excel = create_sample_excel()
        st.download_button(
            label="📥 Tải file mẫu",
            data=sample_excel,
            file_name="mau_danh_sach_ma_ck.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        if uploaded_file is not None:
            stock_df, error = parse_stock_file(uploaded_file)
            
            if error:
                st.error(f"❌ {error}")
                st.session_state['stock_df'] = load_default_stock_list()
            else:
                st.success(f"✅ Đã load {len(stock_df)} mã CK")
                st.session_state['stock_df'] = stock_df
                
                hnx_count = len(stock_df[stock_df['Sàn'] == 'HNX'])
                upcom_count = len(stock_df[stock_df['Sàn'] == 'UPCoM'])
                st.info(f"HNX: {hnx_count} | UPCoM: {upcom_count}")
        else:
            if 'stock_df' not in st.session_state:
                st.session_state['stock_df'] = load_default_stock_list()
                st.warning("⚠️ Đang dùng danh sách mặc định")
        
        st.markdown("---")
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
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(progress)
            
            scraper = StockScraperWeb(stock_df, time_filter_hours=time_filter)
            df = scraper.run(max_articles_per_source=max_articles, progress_callback=update_progress)
            
            progress_bar.empty()
            status_text.empty()
            
            if df is not None:
                st.success(f"✅ Hoàn tất! Tìm thấy {len(df)} bài viết")
                st.info(f"🔍 Tìm theo mã CK: {scraper.stats['found_by_code']} | Tìm theo tên: {scraper.stats['found_by_name']}")
                
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
            df.to_excel(writer, index=False, sheet_name='Tất cả')
            
            df_severe = df[df['Risk'] == 'Nghiêm trọng']
            if len(df_severe) > 0:
                df_severe.to_excel(writer, index=False, sheet_name='Nghiêm trọng')
            
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
                
                # HIỂN THỊ TÓM TẮT
                if pd.notna(row['Nội dung tóm tắt']) and row['Nội dung tóm tắt']:
                    with st.expander("📝 Xem tóm tắt"):
                        st.write(row['Nội dung tóm tắt'])
                
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
        
        # Chi tiết theo mã
        st.markdown("---")
        st.subheader("📈 CHI TIẾT THEO MÃ CK")
        
        with st.expander("Xem chi tiết"):
            summary = df.groupby('Mã CK').agg({
                'Tiêu đề': 'count',
                'Điểm': 'mean',
                'Risk': lambda x: x.mode()[0] if len(x) > 0 else 'N/A'
            }).rename(columns={
                'Tiêu đề': 'Số bài',
                'Điểm': 'Sentiment TB',
                'Risk': 'Risk chính'
            }).reset_index()
            
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
    main(), prev_words):
                            continue
                
                return code, 'UPCoM', 'code'
        
        # Tìm theo tên
        words = text_lower.split()
        matched_codes = []
        for word in words:
            if len(word) > 3 and word in self.name_to_code:
                matched_codes.extend(self.name_to_code[word])
        
        if matched_codes:
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
    
    def fetch_article_content(self, url):
        """Lấy nội dung bài viết - từ V1.0"""
        try:
            response = self.fetch_url(url)
            if not response:
                return None, None, None
            
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm ngày
            date_text = None
            for pattern in [
                {'class': re.compile(r'date|time|publish', re.I)},
                {'itemprop': 'datePublished'}
            ]:
                date_elem = soup.find(['time', 'span', 'div'], pattern)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    break
            
            # Parse ngày (GMT+7)
            article_date_str = datetime.now(self.vietnam_tz).strftime('%d/%m/%Y')
            article_date_obj = datetime.now(self.vietnam_tz)
            
            # Tìm nội dung
            content = ""
            for selector in [
                ('article', {}),
                ('div', {'class': re.compile(r'content|article|detail', re.I)}),
            ]:
                content_div = soup.find(selector[0], selector[1])
                if content_div:
                    paragraphs = content_div.find_all('p')
                    content = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
                    if content:
                        break
            
            if not content:
                paragraphs = soup.find_all('p')
                valid_p = [p.get_text(strip=True) for p in paragraphs if 50 < len(p.get_text(strip=True)) < 1000]
                content = ' '.join(valid_p[:8])
            
            content = self.clean_text(content)
            return content, article_date_str, article_date_obj
        
        except:
            return None, None, None
    
    def scrape_source(self, url, source_name, pattern, max_articles=20, progress_callback=None):
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
                            
                            if match_method == 'code':
                                self.stats['found_by_code'] += 1
                            else:
                                self.stats['found_by_name'] += 1
                            
                            company_name = self.code_to_name.get(stock_code, '')
                            
                            # FETCH NỘI DUNG ĐẦY ĐỦ
                            content, article_date_str, article_date_obj = self.fetch_article_content(full_link)
                            
                            if content:
                                # TÓM TẮT
                                summary = self.advanced_summarize(content, title, max_sentences=4)
                            else:
                                content = ""
                                summary = title  # Fallback nếu không lấy được content
                            
                            # SENTIMENT
                            sentiment_result = self.sentiment_analyzer.analyze_sentiment(title, content)
                            
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
                                'Ngày': article_date_str,
                                'Mã CK': stock_code,
                                'Tên công ty': company_name,
                                'Sàn': exchange,
                                'Sentiment': sentiment_result['sentiment_label'],
                                'Điểm': sentiment_result['sentiment_score'],
                                'Risk': sentiment_result['risk_level'],
                                'Vi phạm': sentiment_result['violations'],
                                'Keywords': "; ".join([k['keyword'] for k in sentiment_result['keywords'][:3]]),
                                'Nội dung tóm tắt': summary,  # ← CỘT MỚI
                                'Tìm theo': 'Mã CK' if match_method == 'code' else 'Tên công ty'
                            })
                            
                            count += 1
                            time.sleep(0.5)
                            
                            if count >= max_articles:
                                break
            
            return count
        
        except Exception as e:
            st.error(f"Lỗi {source_name}: {str(e)}")
            return 0
    
    def run(self, max_articles_per_source=20, progress_callback=None):
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
    st.markdown('<div class="main-header">📈 TOOL CÀO TIN V2.4</div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;color:#666;margin-bottom:2rem;">HNX & UPCoM - Upload + Summarize + Sentiment</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ CÀI ĐẶT")
        
        st.subheader("📂 DANH SÁCH MÃ CK")
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        st.write("**Upload file Excel/CSV**")
        st.caption("Gồm 3 cột: Mã CK | Sàn | Tên công ty")
        
        uploaded_file = st.file_uploader(
            "Chọn file",
            type=['xlsx', 'xls', 'csv'],
            help="File phải có các cột: Mã CK, Sàn (HNX/UPCoM), Tên công ty"
        )
        
        sample_excel = create_sample_excel()
        st.download_button(
            label="📥 Tải file mẫu",
            data=sample_excel,
            file_name="mau_danh_sach_ma_ck.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        if uploaded_file is not None:
            stock_df, error = parse_stock_file(uploaded_file)
            
            if error:
                st.error(f"❌ {error}")
                st.session_state['stock_df'] = load_default_stock_list()
            else:
                st.success(f"✅ Đã load {len(stock_df)} mã CK")
                st.session_state['stock_df'] = stock_df
                
                hnx_count = len(stock_df[stock_df['Sàn'] == 'HNX'])
                upcom_count = len(stock_df[stock_df['Sàn'] == 'UPCoM'])
                st.info(f"HNX: {hnx_count} | UPCoM: {upcom_count}")
        else:
            if 'stock_df' not in st.session_state:
                st.session_state['stock_df'] = load_default_stock_list()
                st.warning("⚠️ Đang dùng danh sách mặc định")
        
        st.markdown("---")
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
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(progress)
            
            scraper = StockScraperWeb(stock_df, time_filter_hours=time_filter)
            df = scraper.run(max_articles_per_source=max_articles, progress_callback=update_progress)
            
            progress_bar.empty()
            status_text.empty()
            
            if df is not None:
                st.success(f"✅ Hoàn tất! Tìm thấy {len(df)} bài viết")
                st.info(f"🔍 Tìm theo mã CK: {scraper.stats['found_by_code']} | Tìm theo tên: {scraper.stats['found_by_name']}")
                
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
            df.to_excel(writer, index=False, sheet_name='Tất cả')
            
            df_severe = df[df['Risk'] == 'Nghiêm trọng']
            if len(df_severe) > 0:
                df_severe.to_excel(writer, index=False, sheet_name='Nghiêm trọng')
            
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
                
                # HIỂN THỊ TÓM TẮT
                if pd.notna(row['Nội dung tóm tắt']) and row['Nội dung tóm tắt']:
                    with st.expander("📝 Xem tóm tắt"):
                        st.write(row['Nội dung tóm tắt'])
                
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
        
        # Chi tiết theo mã
        st.markdown("---")
        st.subheader("📈 CHI TIẾT THEO MÃ CK")
        
        with st.expander("Xem chi tiết"):
            summary = df.groupby('Mã CK').agg({
                'Tiêu đề': 'count',
                'Điểm': 'mean',
                'Risk': lambda x: x.mode()[0] if len(x) > 0 else 'N/A'
            }).rename(columns={
                'Tiêu đề': 'Số bài',
                'Điểm': 'Sentiment TB',
                'Risk': 'Risk chính'
            }).reset_index()
            
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
