# ═══════════════════════════════════════════════════════════
#  🎯 STOCK NEWS SCRAPER - STREAMLIT WEB APP (REAL DATA)
# ═══════════════════════════════════════════════════════════
#  File: app.py
#  Version: 2.2 - Real Data from CafeF & VietStock
#  Deploy: Streamlit Cloud
# ═══════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
import time
from io import BytesIO
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ═══════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Stock News Scraper",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════
# CUSTOM CSS
# ═══════════════════════════════════════════════════════════

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        padding: 1rem 0;
    }
    .stats-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# CLASS: STOCK SCRAPER WITH REAL DATA
# ═══════════════════════════════════════════════════════════

class StockScraperV2:
    """Stock News Scraper với Real Data từ CafeF & VietStock"""
    
    def __init__(self, time_filter_hours=24):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        self.time_filter_hours = time_filter_hours
        self.cutoff_time = datetime.now() - timedelta(hours=time_filter_hours)
        
        self._setup_blacklist()
        self._setup_risk_keywords()
        
        self.stats = {
            'total_crawled': 0,
            'specific_stocks': 0,
            'market_general_filtered': 0,
            'time_filtered': 0,
            'high_risk': 0,
            'medium_risk': 0,
            'normal': 0,
            'cafef_articles': 0,
            'vietstock_articles': 0,
            'errors': 0
        }
        
        self.all_articles = []
    
    def _setup_blacklist(self):
        """Blacklist - Loại bỏ tin tổng quan"""
        self.title_blacklist = {
            'vn-index', 'vnindex', 'vn index', 'vn30', 'hnx-index', 'hnxindex',
            'upcom-index', 'upcomindex', 'chỉ số', 'chi so',
            'tổng quan thị trường', 'tong quan thi truong', 'thị trường chứng khoán',
            'thi truong chung khoan', 'thị trường chung', 'phiên giao dịch',
            'phien giao dich', 'kết thúc phiên', 'ket thuc phien',
            'mở cửa', 'mo cua', 'đóng cửa', 'dong cua',
            'top cổ phiếu', 'top co phieu', 'top 10', 'top 5', 'top stock',
            'cổ phiếu nóng nhất', 'co phieu nong nhat', 'cổ phiếu hot',
            'danh sách cổ phiếu', 'danh sach co phieu',
            'tin vắn', 'tin van', 'điểm tin', 'diem tin', 'tổng hợp tin',
            'tong hop tin', 'bản tin', 'ban tin', 'sao chứng khoán',
            'trong tuần', 'trong tuan', 'tuần qua', 'tuan qua',
            'dòng tiền', 'dong tien', 'thanh khoản thị trường',
            'thanh khoan thi truong', 'xu hướng thị trường', 'xu huong',
            'nhận định', 'nhan dinh', 'triển vọng thị trường', 'trien vong',
            'khối ngoại mua ròng', 'khoi ngoai mua rong', 'khối ngoại bán',
            'giao dịch khối ngoại', 'giao dich khoi ngoai',
            'tuần này', 'tuan nay', 'ngày hôm nay', 'ngay hom nay',
            'hôm nay', 'hom nay', 'sáng nay', 'sang nay'
        }
        
        self.title_blacklist_patterns = [
            r'phiên \d+/\d+',
            r'\d+ cổ phiếu',
            r'top \d+',
            r'tuần \d+',
            r'tháng \d+',
            r'quý \d+',
        ]
        
        self.required_indicators = [
            r'\b[A-Z]{3,4}\b',
            r'(?:cổ phiếu|cp|mã)\s+[A-Z]{3,4}',
            r'[A-Z]{3,4}\s+(?:tăng|giảm|lãi|lỗ)',
        ]
    
    def _setup_risk_keywords(self):
        """Setup 6 nhóm keyword nguy cơ"""
        self.risk_categories = {
            'A. Nội bộ & Quản trị': {
                'keywords': [
                    ('lãnh đạo bị bắt', 10), ('lãnh đạo bỏ trốn', 10),
                    ('lãnh đạo mất liên lạc', 9), ('cổ đông lớn bán chui', 8),
                    ('cổ đông nội bộ bán chui', 8), ('chủ tịch bán sạch cổ phiếu', 9),
                    ('chủ tịch bất ngờ thoái hết vốn', 9), ('thâu tóm quyền lực', 7),
                    ('tranh chấp hđqt', 7), ('tranh chấp hội đồng', 7),
                    ('đổi chủ', 6), ('lãnh đạo mua chui', 7),
                ],
                'icon': '👥'
            },
            'B. Kết quả kinh doanh & Tài chính': {
                'keywords': [
                    ('bất ngờ báo lỗ', 8), ('thua lỗ bất thường', 8),
                    ('lợi nhuận đột biến', 6), ('chậm công bố bctc', 7),
                    ('kiểm toán từ chối', 9), ('kiểm toán ngoại trừ', 8),
                    ('nợ xấu bất thường', 8), ('mất khả năng thanh toán', 9),
                    ('chuyển lỗ thành lãi', 7), ('chuyển lãi thành lỗ', 8),
                    ('lỗ sau soát xét', 8), ('lỗ âm vốn chủ', 9),
                    ('âm vốn chủ', 9), ('doanh thu tăng nhưng vẫn lỗ', 7),
                ],
                'icon': '💰'
            },
            'C. Thao túng & Giao dịch bất thường': {
                'keywords': [
                    ('đội lái làm giá', 10), ('đội lái', 9),
                    ('tăng trần liên tiếp', 7), ('giảm sàn liên tục', 8),
                    ('khối lượng tăng bất thường', 6), ('giao dịch nội gián', 9),
                    ('rò rỉ thông tin nội bộ', 8), ('thị giá tăng nhiều lần', 6),
                    ('tăng dựng đứng', 7), ('cổ phiếu tăng phi mã', 7),
                    ('cổ phiếu tăng ngược dòng', 6), ('giá cổ phiếu tăng trong khi lỗ', 8),
                    ('thao túng', 9),
                ],
                'icon': '⚠️'
            },
            'D. M&A & Sự kiện đặc biệt': {
                'keywords': [
                    ('thâu tóm', 7), ('m&a', 6), ('chào mua công khai', 6),
                    ('niêm yết cửa sau', 8), ('sáp nhập ngược', 7),
                    ('nhân sự cấp cao bất ngờ từ nhiệm', 7),
                    ('bất ngờ giải thể', 9), ('giải thể', 8),
                ],
                'icon': '🔄'
            },
            'E. Pháp lý & Xử phạt': {
                'keywords': [
                    ('công an điều tra', 10), ('khởi tố lãnh đạo', 10),
                    ('khởi tố', 9), ('gian lận tài chính', 10),
                    ('điều tra', 8), ('vi phạm', 7), ('xử phạt', 7),
                ],
                'icon': '⚖️'
            },
            'F. Sự kiện bên ngoài tác động': {
                'keywords': [
                    ('mất hợp đồng lớn', 7), ('sự cố môi trường', 8),
                    ('bị ngừng hoạt động sản xuất', 8), ('tai nạn lao động nghiêm trọng', 8),
                    ('cháy kho', 7), ('cháy nhà xưởng', 8),
                    ('bị thu hồi giấy phép', 9), ('đối tác phá sản', 7), ('phá sản', 8),
                ],
                'icon': '🔥'
            }
        }
        
        self.all_risk_keywords = {}
        for category, data in self.risk_categories.items():
            for keyword, weight in data['keywords']:
                self.all_risk_keywords[keyword.lower()] = {
                    'category': category,
                    'weight': weight,
                    'icon': data['icon']
                }
    
    def fetch_url(self, url, timeout=10):
        """Fetch URL với retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    st.warning(f"⚠️ Không thể truy cập {url}: {str(e)}")
                    return None
                time.sleep(2)
        return None
    
    def parse_date_string(self, date_str):
        """Parse date từ string"""
        if not date_str:
            return datetime.now()
        
        try:
            date_str = date_str.strip().lower()
            
            # "X phút trước"
            if 'phút' in date_str:
                minutes = int(re.search(r'(\d+)', date_str).group(1))
                return datetime.now() - timedelta(minutes=minutes)
            
            # "X giờ trước"
            if 'giờ' in date_str or 'gio' in date_str:
                hours = int(re.search(r'(\d+)', date_str).group(1))
                return datetime.now() - timedelta(hours=hours)
            
            # "hôm qua" hoặc "yesterday"
            if 'hôm qua' in date_str or 'hom qua' in date_str:
                return datetime.now() - timedelta(days=1)
            
            # "hôm nay" hoặc "today"
            if 'hôm nay' in date_str or 'hom nay' in date_str or 'today' in date_str:
                return datetime.now()
            
            # Format: dd/mm/yyyy hoặc dd-mm-yyyy
            date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', date_str)
            if date_match:
                day, month, year = map(int, date_match.groups())
                return datetime(year, month, day)
            
            # Format: yyyy-mm-dd
            date_match = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', date_str)
            if date_match:
                year, month, day = map(int, date_match.groups())
                return datetime(year, month, day)
                
        except Exception as e:
            pass
        
        return datetime.now()
    
    def scrape_cafef(self, max_articles=30):
        """Cào tin từ CafeF"""
        st.info("🔄 Đang cào từ CafeF...")
        url = "https://cafef.vn/thi-truong-chung-khoan.chn"
        
        response = self.fetch_url(url)
        if not response:
            return
        
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Tìm các bài viết
            articles = soup.find_all('div', class_=['item', 'tlitem'], limit=max_articles)
            
            for article in articles:
                try:
                    # Tìm tiêu đề và link
                    title_tag = article.find(['h3', 'h4', 'a'])
                    if not title_tag:
                        continue
                    
                    link_tag = title_tag.find('a') if title_tag.name != 'a' else title_tag
                    if not link_tag:
                        continue
                    
                    title = link_tag.get_text(strip=True)
                    article_url = urljoin(url, link_tag.get('href', ''))
                    
                    # Tìm ngày
                    date_tag = article.find('span', class_=['time', 'date', 'timeago'])
                    date_str = date_tag.get_text(strip=True) if date_tag else ''
                    
                    # Tìm mô tả/tóm tắt
                    desc_tag = article.find(['p', 'div'], class_=['sapo', 'description', 'summary'])
                    description = desc_tag.get_text(strip=True) if desc_tag else ''
                    
                    if title and article_url:
                        self.all_articles.append({
                            'title': title,
                            'url': article_url,
                            'date_str': date_str,
                            'content': description,
                            'source': 'CafeF'
                        })
                        self.stats['cafef_articles'] += 1
                        
                except Exception as e:
                    continue
            
            st.success(f"✅ CafeF: {self.stats['cafef_articles']} bài")
            
        except Exception as e:
            st.error(f"❌ Lỗi khi cào CafeF: {str(e)}")
            self.stats['errors'] += 1
    
    def scrape_vietstock(self, max_articles=30):
        """Cào tin từ VietStock"""
        st.info("🔄 Đang cào từ VietStock...")
        url = "https://vietstock.vn/chung-khoan.htm"
        
        response = self.fetch_url(url)
        if not response:
            return
        
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Tìm các bài viết
            articles = soup.find_all(['div', 'li'], class_=['news-item', 'list-news-item', 'item'], limit=max_articles)
            
            for article in articles:
                try:
                    # Tìm tiêu đề và link
                    title_tag = article.find('a', class_=['title', 'news-title'])
                    if not title_tag:
                        title_tag = article.find('a')
                    
                    if not title_tag:
                        continue
                    
                    title = title_tag.get_text(strip=True)
                    article_url = urljoin(url, title_tag.get('href', ''))
                    
                    # Tìm ngày
                    date_tag = article.find(['span', 'time'], class_=['time', 'date', 'news-time'])
                    date_str = date_tag.get_text(strip=True) if date_tag else ''
                    
                    # Tìm mô tả
                    desc_tag = article.find(['p', 'div'], class_=['summary', 'description', 'news-summary'])
                    description = desc_tag.get_text(strip=True) if desc_tag else ''
                    
                    if title and article_url and 'vietstock.vn' in article_url:
                        self.all_articles.append({
                            'title': title,
                            'url': article_url,
                            'date_str': date_str,
                            'content': description,
                            'source': 'VietStock'
                        })
                        self.stats['vietstock_articles'] += 1
                        
                except Exception as e:
                    continue
            
            st.success(f"✅ VietStock: {self.stats['vietstock_articles']} bài")
            
        except Exception as e:
            st.error(f"❌ Lỗi khi cào VietStock: {str(e)}")
            self.stats['errors'] += 1
    
    def analyze_risk(self, title, content):
        """Phân tích rủi ro"""
        text = (title + " " + content).lower()
        
        matched = []
        total_score = 0
        categories_found = set()
        
        for keyword, info in self.all_risk_keywords.items():
            if keyword in text:
                matched.append({
                    'keyword': keyword,
                    'weight': info['weight'],
                    'category': info['category'],
                    'icon': info['icon']
                })
                total_score += info['weight']
                categories_found.add(info['category'])
        
        risk_score = min(total_score * 5, 100)
        
        if risk_score >= 50 or total_score >= 10:
            risk_level = '🔴 Nghiêm trọng'
            alert = 'HIGH_RISK'
        elif risk_score >= 25 or total_score >= 6:
            risk_level = '🟡 Cảnh báo'
            alert = 'MEDIUM_RISK'
        else:
            risk_level = '⚪ Bình thường'
            alert = 'NORMAL'
        
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'matched_keywords': matched,
            'categories': list(categories_found),
            'alert': alert,
            'keyword_count': len(matched)
        }
    
    def is_market_general_article(self, title, content=""):
        """Kiểm tra tin tổng quan"""
        title_lower = title.lower()
        
        for keyword in self.title_blacklist:
            if keyword in title_lower:
                return True
        
        for pattern in self.title_blacklist_patterns:
            if re.search(pattern, title_lower):
                return True
        
        has_stock_code = False
        for pattern in self.required_indicators:
            if re.search(pattern, title.upper()):
                has_stock_code = True
                break
        
        if not has_stock_code and content:
            for pattern in self.required_indicators:
                if re.search(pattern, content.upper()):
                    has_stock_code = True
                    break
        
        return not has_stock_code
    
    def extract_stock_codes(self, text):
        """Trích xuất mã CK"""
        if not text:
            return []
        
        text_upper = text.upper()
        pattern = r'\b([A-Z]{3,4})\b'
        matches = re.findall(pattern, text_upper)
        
        english_words = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 
                       'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET',
                       'HAS', 'HIM', 'HIS', 'HOW', 'MAN', 'NEW', 'NOW', 'OLD',
                       'SEE', 'TWO', 'WAY', 'WHO', 'BOY', 'DID', 'ITS', 'LET',
                       'VIA', 'PER', 'YET', 'NOR', 'OFF', 'PUT', 'RUN', 'TOP'}
        
        return list(set([code for code in matches if code not in english_words]))
    
    def process_articles(self):
        """Xử lý tất cả bài viết đã cào"""
        results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(self.all_articles)
        
        for idx, article in enumerate(self.all_articles):
            # Update progress
            progress = (idx + 1) / total
            progress_bar.progress(progress)
            status_text.text(f"Đang xử lý: {idx + 1}/{total} bài...")
            
            self.stats['total_crawled'] += 1
            
            title = article['title']
            content = article['content']
            url = article['url']
            source = article['source']
            date_str = article['date_str']
            
            # Parse date
            date_obj = self.parse_date_string(date_str)
            formatted_date = date_obj.strftime('%d/%m/%Y %H:%M')
            
            # Lọc theo thời gian
            if date_obj < self.cutoff_time:
                self.stats['time_filtered'] += 1
                continue
            
            # Lọc tin tổng quan
            if self.is_market_general_article(title, content):
                self.stats['market_general_filtered'] += 1
                continue
            
            # Trích xuất mã CK
            stock_codes = self.extract_stock_codes(title + " " + content)
            if not stock_codes:
                continue
            
            # Phân tích rủi ro
            risk = self.analyze_risk(title, content)
            
            # Update stats
            if risk['alert'] == 'HIGH_RISK':
                self.stats['high_risk'] += 1
            elif risk['alert'] == 'MEDIUM_RISK':
                self.stats['medium_risk'] += 1
            else:
                self.stats['normal'] += 1
            
            self.stats['specific_stocks'] += 1
            
            # Format keywords
            keyword_str = ""
            if risk['matched_keywords']:
                kw_list = [f"{kw['icon']} {kw['keyword']}" for kw in risk['matched_keywords'][:3]]
                keyword_str = "; ".join(kw_list)
                if len(risk['matched_keywords']) > 3:
                    keyword_str += f" (+{len(risk['matched_keywords'])-3})"
            
            results.append({
                'Mức độ': risk['risk_level'],
                'Điểm rủi ro': risk['risk_score'],
                'Tiêu đề': title,
                'Mã CK': ', '.join(stock_codes),
                'Số mã': len(stock_codes),
                'Ngày': formatted_date,
                'Keyword nguy cơ': keyword_str,
                'Số keyword': risk['keyword_count'],
                'Nhóm': '; '.join(risk['categories']) if risk['categories'] else '',
                'Tóm tắt': content[:200] + '...' if len(content) > 200 else content,
                'URL': url,
                'Nguồn': source
            })
        
        progress_bar.empty()
        status_text.empty()
        
        return pd.DataFrame(results)
    
    def run(self, max_articles_per_source=30):
        """Chạy toàn bộ scraper"""
        # Cào từ 2 nguồn
        self.scrape_cafef(max_articles=max_articles_per_source)
        time.sleep(1)  # Delay giữa các requests
        self.scrape_vietstock(max_articles=max_articles_per_source)
        
        if not self.all_articles:
            st.error("❌ Không cào được tin nào. Vui lòng thử lại sau.")
            return pd.DataFrame()
        
        st.info(f"📊 Đang phân tích {len(self.all_articles)} bài viết...")
        
        # Xử lý và phân tích
        df = self.process_articles()
        
        return df

# ═══════════════════════════════════════════════════════════
# STREAMLIT APP
# ═══════════════════════════════════════════════════════════

def main():
    # Header
    st.markdown('<div class="main-header">📰 Stock News Scraper & Risk Analyzer</div>', unsafe_allow_html=True)
    st.markdown("### 🌐 Dữ liệu thực từ CafeF & VietStock")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Cấu hình")
        
        # Time filter
        time_option = st.selectbox(
            "Khoảng thời gian",
            ["6 giờ", "12 giờ", "24 giờ (1 ngày)", "48 giờ (2 ngày)", "72 giờ (3 ngày)", "168 giờ (1 tuần)"],
            index=2
        )
        time_hours = int(time_option.split()[0])
        
        # Articles limit
        max_articles = st.slider(
            "Số bài tối đa mỗi nguồn",
            min_value=10,
            max_value=50,
            value=30,
            step=5
        )
        
        # Risk filter
        risk_filter = st.multiselect(
            "Lọc theo mức độ rủi ro",
            ["🔴 Nghiêm trọng", "🟡 Cảnh báo", "⚪ Bình thường"],
            default=["🔴 Nghiêm trọng", "🟡 Cảnh báo", "⚪ Bình thường"]
        )
        
        st.markdown("---")
        
        # Run button
        if st.button("🚀 BẮT ĐẦU CÀO TIN", type="primary", use_container_width=True):
            st.session_state['run_scraper'] = True
        
        st.markdown("---")
        
        # Info
        with st.expander("ℹ️ Thông tin"):
            st.markdown("""
            **Nguồn dữ liệu:**
            - ✅ CafeF (Real-time)
            - ✅ VietStock (Real-time)
            
            **Tính năng:**
            - Lọc tin tổng quan thị trường
            - Phân tích 6 nhóm keyword nguy cơ
            - Tính điểm rủi ro tự động
            - Xuất Excel
            
            **Version:** 2.2  
            **Updated:** 15/10/2025
            """)
    
    # Main content
    if 'run_scraper' not in st.session_state:
        st.session_state['run_scraper'] = False
    
    if st.session_state['run_scraper']:
        scraper = StockScraperV2(time_filter_hours=time_hours)
        df = scraper.run(max_articles_per_source=max_articles)
        
        if not df.empty:
            # Filter by risk level
            if risk_filter:
                df = df[df['Mức độ'].isin(risk_filter)]
            
            # Sort by risk score descending
            df = df.sort_values('Điểm rủi ro', ascending=False)
            
            st.session_state['df'] = df
            st.session_state['stats'] = scraper.stats
            st.session_state['scraper'] = scraper
        
        st.success('✅ Hoàn tất!')
        st.session_state['run_scraper'] = False
    
    if 'df' in st.session_state:
        df = st.session_state['df']
        stats = st.session_state['stats']
        scraper = st.session_state['scraper']
        
        # Stats
        st.subheader("📊 Thống kê")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("Tổng tin", stats['specific_stocks'])
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("🔴 Nghiêm trọng", stats['high_risk'])
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("🟡 Cảnh báo", stats['medium_risk'])
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("⚪ Bình thường", stats['normal'])
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col5:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("📰 Nguồn", f"CafeF: {stats['cafef_articles']}\nVietStock: {stats['vietstock_articles']}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Additional stats
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"📥 Đã cào: {stats['total_crawled']} bài")
        
        with col2:
            st.warning(f"❌ Đã lọc (tổng quan): {stats['market_general_filtered']} bài")
        
        with col3:
            st.warning(f"⏰ Đã lọc (thời gian): {stats['time_filtered']} bài")
        
        st.markdown("---")
        
        # Data table
        st.subheader("📋 Kết quả")
        
        # Display options
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"Hiển thị {len(df)} bài viết")
        with col2:
            view_mode = st.selectbox("Chế độ xem", ["Bảng đầy đủ", "Chỉ tin quan trọng"], index=0)
        
        # Filter for important news only
        if view_mode == "Chỉ tin quan trọng":
            df_display = df[df['Mức độ'].isin(['🔴 Nghiêm trọng', '🟡 Cảnh báo'])]
        else:
            df_display = df
        
        # Display dataframe
        st.dataframe(
            df_display,
            use_container_width=True,
            height=500,
            column_config={
                "URL": st.column_config.LinkColumn("URL"),
                "Điểm rủi ro": st.column_config.ProgressColumn(
                    "Điểm rủi ro",
                    format="%d",
                    min_value=0,
                    max_value=100,
                ),
            }
        )
        
        # Export section
        st.markdown("---")
        st.subheader("💾 Xuất dữ liệu")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.write("Tải xuống dữ liệu dưới dạng Excel để phân tích thêm")
        
        with col2:
            # Excel export
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Stock News')
                
                # Add stats sheet
                stats_df = pd.DataFrame([stats])
                stats_df.to_excel(writer, index=False, sheet_name='Statistics')
            
            st.download_button(
                label="📥 Tải Excel (Tất cả)",
                data=output.getvalue(),
                file_name=f"stock_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col3:
            # CSV export
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Tải CSV",
                data=csv,
                file_name=f"stock_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        # Detailed analysis
        st.markdown("---")
        
        with st.expander("📊 Phân tích chi tiết"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Top 10 mã CK được nhắc nhiều nhất")
                # Count stock codes
                all_codes = []
                for codes in df['Mã CK']:
                    all_codes.extend([c.strip() for c in codes.split(',')])
                
                if all_codes:
                    code_counts = pd.Series(all_codes).value_counts().head(10)
                    st.bar_chart(code_counts)
                else:
                    st.info("Không có dữ liệu")
            
            with col2:
                st.markdown("### Phân bố theo mức độ rủi ro")
                risk_counts = df['Mức độ'].value_counts()
                st.bar_chart(risk_counts)
        
        # Keyword table
        with st.expander("📋 Bảng 6 nhóm keyword nguy cơ"):
            for category, data in scraper.risk_categories.items():
                st.markdown(f"### {data['icon']} {category}")
                keywords = [kw for kw, _ in data['keywords']]
                # Display in columns for better readability
                cols = st.columns(3)
                for i, keyword in enumerate(keywords):
                    with cols[i % 3]:
                        st.write(f"• {keyword}")
                st.markdown("---")
        
        # Refresh button
        st.markdown("---")
        if st.button("🔄 Cào lại tin mới", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    else:
        # Welcome screen
        st.info("👈 Chọn cấu hình và nhấn **BẮT ĐẦU CÀO TIN** để bắt đầu")
        
        st.markdown("### 🎯 Tính năng chính")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **🔍 Lọc thông minh**
            - Loại bỏ tin tổng quan thị trường
            - Chỉ giữ tin về cổ phiếu cụ thể
            - Lọc theo khoảng thời gian
            
            **📊 Phân tích rủi ro**
            - 6 nhóm keyword nguy cơ
            - Tính điểm rủi ro tự động (0-100)
            - Phân loại 3 mức độ
            """)
        
        with col2:
            st.markdown("""
            **📰 Nguồn tin THỰC**
            - ✅ CafeF (Real-time)
            - ✅ VietStock (Real-time)
            
            **💾 Xuất dữ liệu**
            - File Excel đầy đủ
            - File CSV
            - Bảng thống kê chi tiết
            """)
        
        st.markdown("---")
        
        # Usage guide
        with st.expander("📖 Hướng dẫn sử dụng"):
            st.markdown("""
            ### Các bước sử dụng:
            
            1. **Chọn khoảng thời gian**: Từ 6 giờ đến 1 tuần
            2. **Điều chỉnh số bài**: 10-50 bài mỗi nguồn
            3. **Chọn mức độ rủi ro**: Lọc tin cần xem
            4. **Nhấn "BẮT ĐẦU CÀO TIN"**: Đợi 30-60 giây
            5. **Xem kết quả**: Bảng tin với điểm rủi ro
            6. **Tải Excel/CSV**: Phân tích thêm nếu cần
            
            ### Giải thích mức độ rủi ro:
            
            - 🔴 **Nghiêm trọng** (điểm ≥ 50): Tin có nhiều keyword nguy hiểm như "lãnh đạo bị bắt", "gian lận tài chính", "đội lái"...
            - 🟡 **Cảnh báo** (điểm 25-49): Tin có keyword cần lưu ý như "báo lỗ", "M&A", "sự cố"...
            - ⚪ **Bình thường** (điểm < 25): Tin thông thường về hoạt động doanh nghiệp
            
            ### Tips:
            
            - Chạy vào **buổi sáng** để có tin mới nhất
            - Lọc chỉ xem tin **Nghiêm trọng** để tiết kiệm thời gian
            - **Tải Excel** để lưu trữ và theo dõi dài hạn
            - Chạy lại **mỗi vài giờ** để cập nhật tin mới
            """)
        
        # Sample data preview
        with st.expander("👁️ Xem dữ liệu mẫu"):
            sample_data = pd.DataFrame([
                {
                    'Mức độ': '🔴 Nghiêm trọng',
                    'Điểm rủi ro': 85,
                    'Tiêu đề': 'FPT: Chủ tịch bất ngờ thoái vốn, cổ đông nội bộ bán chui',
                    'Mã CK': 'FPT',
                    'Ngày': '15/10/2025 08:30',
                    'Keyword nguy cơ': '👥 chủ tịch thoái vốn; 👥 bán chui',
                    'Nguồn': 'CafeF'
                },
                {
                    'Mức độ': '🟡 Cảnh báo',
                    'Điểm rủi ro': 35,
                    'Tiêu đề': 'HPG: Hòa Phát bất ngờ báo lỗ quý 3/2025',
                    'Mã CK': 'HPG',
                    'Ngày': '15/10/2025 07:15',
                    'Keyword nguy cơ': '💰 bất ngờ báo lỗ',
                    'Nguồn': 'VietStock'
                },
                {
                    'Mức độ': '⚪ Bình thường',
                    'Điểm rủi ro': 0,
                    'Tiêu đề': 'VNM: Vinamilk công bố kế hoạch mở rộng thị trường',
                    'Mã CK': 'VNM',
                    'Ngày': '15/10/2025 06:45',
                    'Keyword nguy cơ': '',
                    'Nguồn': 'CafeF'
                }
            ])
            
            st.dataframe(sample_data, use_container_width=True)

if __name__ == "__main__":
    main()
