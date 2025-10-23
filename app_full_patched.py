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
    
    def is_generic_news(self, title):
        """Kiểm tra xem có phải tin tức chung không"""
        title_lower = title.lower()
        
        generic_patterns = [
            r'lịch\s+sự\s+kiện',
            r'tin\s+vắn',
            r'tổng\s+hợp',
            r'điểm\s+tin',
            r'nhịp\s+đập',
            r'thị\s+trường\s+ngày',
            r'chứng\s+khoán\s+ngày',
            r'phiên\s+giao\s+dịch',
            r'các\s+tin\s+tức',
            r'tin\s+nhanh',
            r'cập\s+nhật',
            r'điểm\s+lại',
        ]
        
        for pattern in generic_patterns:
            if re.search(pattern, title_lower):
                return True
        
        return False
    
    def extract_stock(self, text):
        """Trích xuất mã CK - NÂNG CAO: YÊU CẦU TÍN HIỆU NHẬN DIỆN"""
        text_upper = text.upper()
        text_lower = text.lower()
        
        # ============================================================
        # DANH SÁCH MÃ "NGUY HIỂM" - CHỈ NHẬN DIỆN KHI CÓ TÍN HIỆU RÕ RÀNG
        # ============================================================
        RISKY_CODES = {'THU', 'TIN', 'TOP', 'HAI', 'LAI', 'CEO', 'CCP'}
        
        # ============================================================
        # BƯỚC 1: TÌM THEO CÁC PATTERN RÕ RÀNG (ƯU TIÊN CAO NHẤT)
        # ============================================================
        
        # Pattern nhóm 1: Trong ngoặc với sàn
        patterns_with_exchange = [
            r'\((?:UPCOM|HNX):\s*([A-Z]{3})\)',           # (UPCOM: ABC), (HNX: ABC)
            r'\(([A-Z]{3})\s*[-–]\s*(?:UPCOM|HNX)\)',     # (ABC - UPCOM), (ABC - HNX)
            r'\(([A-Z]{3})\s*,\s*(?:UPCOM|HNX)\)',        # (ABC, UPCOM), (ABC, HNX)
            r'\((?:UPCOM|HNX)\s*[-–]\s*([A-Z]{3})\)',     # (UPCOM - ABC), (HNX - ABC)
        ]
        
        for pattern in patterns_with_exchange:
            match = re.search(pattern, text_upper)
            if match:
                code = match.group(1)
                if code in self.hnx_stocks:
                    return code, 'HNX', 'code'
                elif code in self.upcom_stocks:
                    return code, 'UPCoM', 'code'
        
        # Pattern nhóm 2: Có từ khóa "mã"
        patterns_with_ma = [
            r'MÃ\s*(?:CK|CHỨNG KHOÁN|CP)?:?\s*([A-Z]{3})\b',    # Mã CK: ABC, Mã: ABC
            r'MÃ\s+([A-Z]{3})\b',                                # Mã ABC
            r'\(MÃ:?\s*([A-Z]
