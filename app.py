# app.py - Streamlit Web App V2.4 FINAL
# Deploy: Copy toàn bộ file này vào GitHub

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import re
from urllib.parse import urljoin
import io

st.set_page_config(
    page_title="Cào Tin Chứng Khoán V2.4",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 1rem;}
    .upload-box {background-color: #e8f4f8; padding: 1.5rem; border-radius: 0.5rem; border: 2px dashed #1f77b4; margin: 1rem 0;}
    .severe-card {background-color: #ffe6e6; border-left: 5px solid #ff4444; padding: 1rem; margin: 0.5rem 0; border-radius: 0.3rem;}
    .warning-card {background-color: #fff8e6; border-left: 5px solid #ffaa00; padding: 1rem; margin: 0.5rem 0; border-radius: 0.3rem;}
    .positive-card {background-color: #e6ffe6; border-left: 5px solid #44ff44; padding: 1rem; margin: 0.5rem 0; border-radius: 0.3rem;}
</style>
""", unsafe_allow_html=True)

def load_default_stock_list():
    return pd.DataFrame({
        'Mã CK': ['SHS', 'PVS', 'NVB', 'CEO', 'LPB', 'EIB'],
        'Sàn': ['HNX', 'HNX', 'HNX', 'HNX', 'UPCoM', 'UPCoM'],
        'Tên công ty': ['Chứng khoán SHS', 'Chứng khoán PVS', 'Ngân hàng NVB', 'Tập đoàn CEO', 'Ngân hàng LPB', 'Ngân hàng EIB']
    })

def parse_stock_file(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip().str.lower()
        
        mapping = {
            'mã ck': 'Mã CK', 'ma ck': 'Mã CK', 'mã': 'Mã CK', 'code': 'Mã CK',
            'sàn': 'Sàn', 'san': 'Sàn', 'exchange': 'Sàn',
            'tên công ty': 'Tên công ty', 'ten cong ty': 'Tên công ty', 'name': 'Tên công ty',
        }
        for old, new in mapping.items():
            if old in df.columns:
                df.rename(columns={old: new}, inplace=True)
        
        if 'Mã CK' not in df.columns or 'Sàn' not in df.columns:
            return None, "Thiếu cột bắt buộc"
        
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
        return None, f"Lỗi: {str(e)}"

def create_sample_excel():
    df = pd.DataFrame({
        'Mã CK': ['SHS', 'PVS', 'NVB', 'LPB', 'EIB', 'CEO'],
        'Sàn': ['HNX', 'HNX', 'HNX', 'UPCoM', 'UPCoM', 'HNX'],
        'Tên công ty': ['Chứng khoán SHS', 'Chứng khoán PVS', 'Ngân hàng NVB', 'Ngân hàng LPB', 'Ngân hàng EIB', 'Tập đoàn CEO']
    })
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Danh sách mã')
    return buffer.getvalue()

class KeywordRiskDetector:
    def __init__(self):
        self.keywords_db = {
            "lãnh đạo bị bắt": {"category": "A. Nội bộ", "severity": "severe", "score": -95, "violation": "I.2, II.A"},
            "bốc đầu": {"category": "C. Thao túng", "severity": "warning", "score": -65, "violation": "I.2, I.3, II.C"},
            "kịch trần": {"category": "C. Thao túng", "severity": "warning", "score": -65, "violation": "I.2, I.3, II.C"},
            "rớt đáy": {"category": "C. Thao túng", "severity": "warning", "score": -70, "violation": "I.2, I.3, II.C"},
            "đội lái làm giá": {"category": "C. Thao túng", "severity": "severe", "score": -95, "violation": "I.3, II.C"},
            "lợi nhuận tăng": {"category": "Tích cực", "severity": "positive", "score": 70, "violation": ""},
        }
    
    def analyze(self, text):
        text_lower = text.lower()
        found = []
        score = 0
        cats = set()
        viols = set()
        sev = "normal"
        
        for kw, info in self.keywords_db.items():
            if kw in text_lower:
                found.append({"keyword": kw, "category": info["category"], "severity": info["severity"], "score": info["score"], "violation": info["violation"]})
                score += info["score"]
                cats.add(info["category"])
                if info["violation"]:
                    viols.add(info["violation"])
                if info["severity"] == "severe":
                    sev = "severe"
                elif info["severity"] == "warning" and sev != "severe":
                    sev = "warning"
                elif info["severity"] == "positive" and sev == "normal":
                    sev = "positive"
        
        return {"keywords": found, "total_score": score, "severity": sev, "categories": list(cats), "violations": ", ".join(sorted(viols))}

class SimpleSentimentAnalyzer:
    def __init__(self):
        self.keyword_detector = KeywordRiskDetector()
        self.positive_words = ['tăng', 'tăng trưởng', 'lợi nhuận', 'thành công']
        self.negative_words = ['giảm', 'lỗ', 'khó khăn', 'tiêu cực']
    
    def analyze_sentiment(self, title, content):
        text = (title + " " + content).lower()
        kw_analysis = self.keyword_detector.analyze(title + " " + content)
        
        pos = sum(1 for w in self.positive_words if w in text)
        neg = sum(1 for w in self.negative_words if w in text)
        base = 50 + (pos * 5) - (neg * 5)
        
        if kw_analysis["severity"] == "severe":
            final = min(20, base + kw_analysis["total_score"])
        elif kw_analysis["severity"] == "warning":
            final = min(40, base + kw_analysis["total_score"] * 0.7)
        elif kw_analysis["severity"] == "positive":
            final = max(60, base + kw_analysis["total_score"])
        else:
            final = base
        
        final = max(0, min(100, final))
        label = "Tích cực" if final >= 60 else ("Trung lập" if final >= 40 else "Tiêu cực")
        risk = "Nghiêm trọng" if kw_analysis["severity"] == "severe" else ("Cảnh báo" if kw_analysis["severity"] == "warning" else ("Tích cực" if kw_analysis["severity"] == "positive" else "Bình thường"))
        
        return {
            "sentiment_score": round(final, 1),
            "sentiment_label": label,
            "risk_level": risk,
            "keywords": kw_analysis["keywords"],
            "categories": ", ".join(kw_analysis["categories"]) if kw_analysis["categories"] else "",
            "violations": kw_analysis["violations"]
        }

class StockScraperWeb:
    def __init__(self, stock_df, time_filter_hours=24):
        self.headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'vi-VN,vi;q=0.9'}
        self.all_articles = []
        self.session = requests.Session()
        self.vietnam_tz = timezone(timedelta(hours=7))
        self.cutoff_time = datetime.now(self.vietnam_tz) - timedelta(hours=time_filter_hours)
        self.sentiment_analyzer = SimpleSentimentAnalyzer()
        
        self.stock_df = stock_df
        self.hnx_stocks = set(stock_df[stock_df['Sàn'] == 'HNX']['Mã CK'].tolist())
        self.upcom_stocks = set(stock_df[stock_df['Sàn'] == 'UPCoM']['Mã CK'].tolist())
        self.code_to_name = dict(zip(stock_df['Mã CK'], stock_df['Tên công ty']))
        
        self.name_to_code = {}
        for code, name in self.code_to_name.items():
            if name:
                for word in name.lower().split():
                    if len(word) > 3:
                        if word not in self.name_to_code:
                            self.name_to_code[word] = []
                        self.name_to_code[word].append(code)
        
        self.stock_to_exchange = {}
        for code in self.hnx_stocks:
            self.stock_to_exchange[code] = 'HNX'
        for code in self.upcom_stocks:
            self.stock_to_exchange[code] = 'UPCoM'
        
        self.stats = {'total_crawled': 0, 'hnx_found': 0, 'upcom_found': 0, 'severe_risk': 0, 'warning_risk': 0, 'found_by_code': 0, 'found_by_name': 0}
    
    def clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'[^\w\s.,;:!?()%\-\+\/\"\'àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()
    
    def advanced_summarize(self, content, title, max_sentences=4):
        content = self.clean_text(content)
        title = self.clean_text(title)
        if not content or len(content) < 100:
            return content
        
        full_text = title + ". " + content
        sentences = [s.strip() for s in re.split(r'[.!?]+', full_text) if len(s.strip()) > 30]
        if len(sentences) <= max_sentences:
            return '. '.join(sentences) + '.'
        
        keywords = {'tăng': 3, 'giảm': 3, 'lợi nhuận': 4, 'doanh thu': 4, 'lỗ': 3, 'tỷ đồng': 3, 'cổ phiếu': 3, 'quý': 3}
        scored = []
        for i, s in enumerate(sentences):
            score = 5 if i == 0 else (3 if i == 1 else (1 if i < 5 else 0))
            for kw, w in keywords.items():
                if kw in s.lower():
                    score += w
            if '%' in s:
                score += 3
            scored.append((s, score, i))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:max_sentences]
        top.sort(key=lambda x: x[2])
        summary = '. '.join([s[0] for s in top])
        return (summary + '.' if not summary.endswith('.') else summary)
    
    def extract_stock(self, text):
        tu = text.upper()
        
        blacklist = [
            r'CHỨNG KHOÁN\s+\w+\s+CÓ\s+NHẬN ĐỊNH', r'CÔNG TY\s+CHỨNG KHOÁN', r'CTCK\s+\w+',
            r'VN-INDEX', r'TOP\s+CỔ', r'TOP\s+\d+', r'TOP\s+MÃ',
            r'TIN\s+VUI', r'TIN\s+VẮN', r'NHẬN\s+TIN', r'THEO\s+TIN',
            r'CEO\s+CÔNG\s+TY', r'CEO\s+CỦA', r'GIÁM\s+ĐỐC\s+CEO'
        ]
        
        for pat in blacklist:
            if re.search(pat, tu):
                return None, None, None
        
        for code in self.hnx_stocks:
            m = re.search(r'\b' + code + r'\b', tu)
            if m:
                skip = False
                if code == 'TOP' and m.end() < len(tu) - 1:
                    nt = tu[m.end():m.end()+10]
                    if re.match(r'\s+\d', nt) or re.match(r'\s+CỔ', nt):
                        skip = True
                if code == 'TIN':
                    if m.start() >= 5:
                        pt = tu[m.start()-10:m.start()]
                        if re.search(r'(NHẬN|THEO|MỘT)\s*$', pt):
                            skip = True
                    if m.end() < len(tu) - 5:
                        nt = tu[m.end():m.end()+15]
                        if re.match(r'\s+(VUI|VẮN|TỐT)', nt):
                            skip = True
                if code == 'CEO' and m.end() < len(tu) - 5:
                    nt = tu[m.end():m.end()+10]
                    if re.match(r'\s+CÔNG', nt) or re.match(r'\s+CỦA', nt):
                        skip = True
                if not skip:
                    return code, 'HNX', 'code'
        
        for code in self.upcom_stocks:
            m = re.search(r'\b' + code + r'\b', tu)
            if m:
                return code, 'UPCoM', 'code'
        
        words = text.lower().split()
        matched = []
        for w in words:
            if len(w) > 3 and w in self.name_to_code:
                matched.extend(self.name_to_code[w])
        
        if matched:
            from collections import Counter
            mc = Counter(matched).most_common(1)[0][0]
            return mc, self.stock_to_exchange.get(mc), 'name'
        
        return None, None, None
    
    def fetch_url(self, url, max_retries=2):
        for _ in range(max_retries):
            try:
                r = self.session.get(url, headers=self.headers, timeout=15)
                r.raise_for_status()
                return r
            except:
                time.sleep(1)
        return None
    
    def fetch_article_content(self, url):
        try:
            r = self.fetch_url(url)
            if not r:
                return None, None, None
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')
            
            date_str = datetime.now(self.vietnam_tz).strftime('%d/%m/%Y')
            date_obj = datetime.now(self.vietnam_tz)
            
            content = ""
            for sel in [('article', {}), ('div', {'class': re.compile(r'content|article', re.I)})]:
                div = soup.find(sel[0], sel[1])
                if div:
                    ps = div.find_all('p')
                    content = ' '.join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 50])
                    if content:
                        break
            
            return self.clean_text(content), date_str, date_obj
        except:
            return None, None, None
    
    def scrape_source(self, url, name, pattern, max_articles=20, progress_callback=None):
        try:
            r = self.fetch_url(url)
            if not r:
                return 0
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')
            
            count = 0
            seen = set()
            links = soup.find_all('a', href=True)
            
            for idx, tag in enumerate(links):
                if progress_callback:
                    progress_callback(f"{name}: {idx+1}/{len(links)}", (idx+1)/len(links))
                
                href = tag.get('href', '')
                if pattern(href) and href not in seen:
                    title = tag.get_text(strip=True)
                    if title and len(title) > 30:
                        self.stats['total_crawled'] += 1
                        seen.add(href)
                        
                        code, exchange, method = self.extract_stock(title)
                        if code and exchange in ['HNX', 'UPCoM']:
                            full_link = urljoin(url, href)
                            
                            if method == 'code':
                                self.stats['found_by_code'] += 1
                            else:
                                self.stats['found_by_name'] += 1
                            
                            company = self.code_to_name.get(code, '')
                            content, date_str, date_obj = self.fetch_article_content(full_link)
                            summary = self.advanced_summarize(content if content else "", title, 4)
                            sentiment = self.sentiment_analyzer.analyze_sentiment(title, content if content else "")
                            
                            if exchange == 'HNX':
                                self.stats['hnx_found'] += 1
                            else:
                                self.stats['upcom_found'] += 1
                            
                            if sentiment['risk_level'] == 'Nghiêm trọng':
                                self.stats['severe_risk'] += 1
                            elif sentiment['risk_level'] == 'Cảnh báo':
                                self.stats['warning_risk'] += 1
                            
                            self.all_articles.append({
                                'Tiêu đề': title,
                                'Link': full_link,
                                'Ngày': date_str,
                                'Mã CK': code,
                                'Tên công ty': company,
                                'Sàn': exchange,
                                'Sentiment': sentiment['sentiment_label'],
                                'Điểm': sentiment['sentiment_score'],
                                'Risk': sentiment['risk_level'],
                                'Vi phạm': sentiment['violations'],
                                'Keywords': "; ".join([k['keyword'] for k in sentiment['keywords'][:3]]),
                                'Nội dung tóm tắt': summary,
                                'Tìm theo': 'Mã CK' if method == 'code' else 'Tên công ty'
                            })
                            
                            count += 1
                            time.sleep(0.5)
                            if count >= max_articles:
                                break
            return count
        except Exception as e:
            st.error(f"Lỗi {name}: {str(e)}")
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

def main():
    st.markdown('<div class="main-header">📈 TOOL CÀO TIN V2.4</div>', unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("⚙️ CÀI ĐẶT")
        st.subheader("📂 DANH SÁCH MÃ CK")
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        st.write("**Upload file Excel/CSV**")
        
        uploaded = st.file_uploader("Chọn file", type=['xlsx', 'xls', 'csv'])
        st.download_button("📥 Tải file mẫu", create_sample_excel(), "mau_ma_ck.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if uploaded:
            sdf, err = parse_stock_file(uploaded)
            if err:
                st.error(f"❌ {err}")
                st.session_state['stock_df'] = load_default_stock_list()
            else:
                st.success(f"✅ Load {len(sdf)} mã")
                st.session_state['stock_df'] = sdf
        else:
            if 'stock_df' not in st.session_state:
                st.session_state['stock_df'] = load_default_stock_list()
                st.warning("⚠️ Dùng danh sách mặc định")
        
        st.markdown("---")
        time_filter = st.selectbox("⏰ Thời gian", [6,12,24,48,72,168], format_func=lambda x: f"{x}h" if x<168 else "1 tuần", index=2)
        max_arts = st.slider("📊 Số bài/nguồn", 5, 50, 20, 5)
    
    if st.button("🚀 BẮT ĐẦU", type="primary"):
        sdf = st.session_state.get('stock_df')
        if sdf is None or len(sdf)==0:
            st.error("❌ Chưa có danh sách mã!")
            return
        
        with st.spinner("Đang cào..."):
            pb = st.progress(0)
            stxt = st.empty()
            def upd(m,p):
                stxt.text(m)
                pb.progress(p)
            
            scraper = StockScraperWeb(sdf, time_filter)
            df = scraper.run(max_arts, upd)
            pb.empty()
            stxt.empty()
            
            if df is not None:
                st.success(f"✅ {len(df)} bài")
                st.session_state['df'] = df
                st.session_state['stats'] = scraper.stats
            else:
                st.error("Không tìm thấy!")
    
    if 'df' in st.session_state:
        df = st.session_state['df']
        stats = st.session_state['stats']
        
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("📊 Tổng", len(df))
        c2.metric("⚠️ Nghiêm trọng", stats['severe_risk'])
        c3.metric("⚠️ Cảnh báo", stats['warning_risk'])
        c4.metric("🔤 Theo mã", stats['found_by_code'])
        c5.metric("📝 Theo tên", stats['found_by_name'])
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df.to_excel(w, index=False, sheet_name='Tất cả')
        st.download_button("⬇️ Download Excel", buf.getvalue(), f"Tin_{datetime.now().strftime('%d%m%Y_%H%M')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        st.markdown("---")
        st.subheader("🔍 LỌC")
        c1,c2,c3 = st.columns(3)
        search = c1.text_input("Mã CK")
        fsan = c2.selectbox("Sàn", ["Tất cả", "HNX", "UPCoM"])
        frisk = c3.selectbox("Risk", ["Tất cả", "Nghiêm trọng", "Cảnh báo"])
        
        dff = df.copy()
        if search:
            dff = dff[dff['Mã CK'].str.contains(search.upper(), na=False)]
        if fsan != "Tất cả":
            dff = dff[dff['Sàn']==fsan]
        if frisk != "Tất cả":
            dff = dff[dff['Risk']==frisk]
        
        st.info(f"{len(dff)}/{len(df)} bài")
        
        for i,row in dff.iterrows():
            st.markdown(f"**{row['Mã CK']} - {row['Tên công ty']}**")
            st.caption(f"{row['Ngày']} | {row['Sentiment']} ({row['Điểm']}) | {row['Risk']}")
            if pd.notna(row['Nội dung tóm tắt']):
                with st.expander("📝 Tóm tắt"):
                    st.write(row['Nội dung tóm tắt'])

if __name__ == "__main__":
    main()
