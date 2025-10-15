# ═══════════════════════════════════════════════════════════
#  🎯 STOCK NEWS SCRAPER - STREAMLIT WEB APP
# ═══════════════════════════════════════════════════════════
#  File: app.py
#  Deploy: Streamlit Cloud
# ═══════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
import time
from io import BytesIO

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
    .risk-high {
        background-color: #ffebee;
        color: #c62828;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: bold;
    }
    .risk-medium {
        background-color: #fff9c4;
        color: #f57f17;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: bold;
    }
    .risk-normal {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# CLASS: STOCK SCRAPER
# ═══════════════════════════════════════════════════════════

class StockScraperV2:
    """Stock News Scraper với Risk Analysis"""
    
    def __init__(self, time_filter_hours=24):
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
            'normal': 0
        }
    
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
                    ('lãnh đạo bị bắt', 10),
                    ('lãnh đạo bỏ trốn', 10),
                    ('lãnh đạo mất liên lạc', 9),
                    ('cổ đông lớn bán chui', 8),
                    ('cổ đông nội bộ bán chui', 8),
                    ('chủ tịch bán sạch cổ phiếu', 9),
                    ('chủ tịch bất ngờ thoái hết vốn', 9),
                    ('thâu tóm quyền lực', 7),
                    ('tranh chấp hđqt', 7),
                    ('tranh chấp hội đồng', 7),
                    ('đổi chủ', 6),
                    ('lãnh đạo mua chui', 7),
                ],
                'icon': '👥',
                'color': 'red'
            },
            
            'B. Kết quả kinh doanh & Tài chính': {
                'keywords': [
                    ('bất ngờ báo lỗ', 8),
                    ('thua lỗ bất thường', 8),
                    ('lợi nhuận đột biến', 6),
                    ('chậm công bố bctc', 7),
                    ('kiểm toán từ chối', 9),
                    ('kiểm toán ngoại trừ', 8),
                    ('nợ xấu bất thường', 8),
                    ('mất khả năng thanh toán', 9),
                    ('chuyển lỗ thành lãi', 7),
                    ('chuyển lãi thành lỗ', 8),
                    ('lỗ sau soát xét', 8),
                    ('lỗ âm vốn chủ', 9),
                    ('âm vốn chủ', 9),
                    ('doanh thu tăng nhưng vẫn lỗ', 7),
                    ('âm vốn chủ sau soát xét', 9),
                ],
                'icon': '💰',
                'color': 'red'
            },
            
            'C. Thao túng & Giao dịch bất thường': {
                'keywords': [
                    ('đội lái làm giá', 10),
                    ('đội lái', 9),
                    ('tăng trần liên tiếp', 7),
                    ('giảm sàn liên tục', 8),
                    ('khối lượng tăng bất thường', 6),
                    ('giao dịch nội gián', 9),
                    ('rò rỉ thông tin nội bộ', 8),
                    ('thị giá tăng nhiều lần', 6),
                    ('tăng dựng đứng', 7),
                    ('cổ phiếu tăng phi mã', 7),
                    ('cổ phiếu tăng ngược dòng', 6),
                    ('giá cổ phiếu tăng trong khi lỗ', 8),
                    ('thao túng', 9),
                ],
                'icon': '⚠️',
                'color': 'red'
            },
            
            'D. M&A & Sự kiện đặc biệt': {
                'keywords': [
                    ('thâu tóm', 7),
                    ('m&a', 6),
                    ('chào mua công khai', 6),
                    ('niêm yết cửa sau', 8),
                    ('sáp nhập ngược', 7),
                    ('nhân sự cấp cao bất ngờ từ nhiệm', 7),
                    ('bất ngờ giải thể', 9),
                    ('giải thể', 8),
                ],
                'icon': '🔄',
                'color': 'orange'
            },
            
            'E. Pháp lý & Xử phạt': {
                'keywords': [
                    ('công an điều tra', 10),
                    ('khởi tố lãnh đạo', 10),
                    ('khởi tố', 9),
                    ('gian lận tài chính', 10),
                    ('điều tra', 8),
                    ('vi phạm', 7),
                    ('xử phạt', 7),
                ],
                'icon': '⚖️',
                'color': 'red'
            },
            
            'F. Sự kiện bên ngoài tác động': {
                'keywords': [
                    ('mất hợp đồng lớn', 7),
                    ('sự cố môi trường', 8),
                    ('bị ngừng hoạt động sản xuất', 8),
                    ('tai nạn lao động nghiêm trọng', 8),
                    ('cháy kho', 7),
                    ('cháy nhà xưởng', 8),
                    ('bị thu hồi giấy phép', 9),
                    ('đối tác phá sản', 7),
                    ('phá sản', 8),
                ],
                'icon': '🔥',
                'color': 'orange'
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
                       'SEE', 'TWO', 'WAY', 'WHO', 'BOY', 'DID', 'ITS', 'LET'}
        
        return list(set([code for code in matches if code not in english_words]))
    
    def generate_demo_data(self):
        """Tạo dữ liệu demo"""
        demo_articles = [
            {
                'title': 'VNM: Vinamilk công bố KQKD quý 3/2025 tăng trưởng 15%',
                'content': 'Cổ phiếu VNM của Vinamilk ghi nhận lợi nhuận quý 3 tăng 15% so với cùng kỳ năm trước.',
                'date': datetime.now().strftime('%d/%m/%Y'),
                'url': 'https://example.com/vnm-tang-truong',
                'source': 'CafeF'
            },
            {
                'title': 'FPT: Chủ tịch bất ngờ thoái hết vốn, cổ đông nội bộ bán chui',
                'content': 'Thông tin về việc lãnh đạo FPT thực hiện giao dịch không công bố đang gây xôn xao thị trường.',
                'date': datetime.now().strftime('%d/%m/%Y'),
                'url': 'https://example.com/fpt-thoai-von',
                'source': 'VietStock'
            },
            {
                'title': 'HPG: Hòa Phát bất ngờ báo lỗ quý 3 sau nhiều quý liên tiếp lãi',
                'content': 'HPG chuyển lỗ thành lãi đột ngột, các chuyên gia đang phân tích nguyên nhân.',
                'date': datetime.now().strftime('%d/%m/%Y'),
                'url': 'https://example.com/hpg-bao-lo',
                'source': 'Báo Mới'
            },
            {
                'title': 'ABC: Công an điều tra vụ gian lận tài chính, khởi tố lãnh đạo',
                'content': 'Lãnh đạo bị bắt và đang được điều tra về hành vi thao túng giá cổ phiếu ABC.',
                'date': datetime.now().strftime('%d/%m/%Y'),
                'url': 'https://example.com/abc-dieu-tra',
                'source': 'Người Quan Sát'
            },
            {
                'title': 'XYZ: Công ty hoàn tất M&A với đối tác Nhật Bản',
                'content': 'Cổ phiếu XYZ tăng nhẹ sau thông tin thâu tóm công ty con tại thị trường châu Á.',
                'date': datetime.now().strftime('%d/%m/%Y'),
                'url': 'https://example.com/xyz-ma',
                'source': 'CafeF'
            },
            {
                'title': 'DEF: Cháy nhà xưởng, thiệt hại hàng chục tỷ đồng',
                'content': 'Sự cố môi trường nghiêm trọng tại nhà máy DEF, sản xuất bị ngừng hoạt động.',
                'date': datetime.now().strftime('%d/%m/%Y'),
                'url': 'https://example.com/def-chay',
                'source': 'VietStock'
            }
        ]
        
        results = []
        for article in demo_articles:
            if self.is_market_general_article(article['title'], article['content']):
                continue
            
            stock_codes = self.extract_stock_codes(article['title'] + " " + article['content'])
            if not stock_codes:
                continue
            
            risk = self.analyze_risk(article['title'], article['content'])
            
            if risk['alert'] == 'HIGH_RISK':
                self.stats['high_risk'] += 1
            elif risk['alert'] == 'MEDIUM_RISK':
                self.stats['medium_risk'] += 1
            else:
                self.stats['normal'] += 1
            
            keyword_str = ""
            if risk['matched_keywords']:
                kw_list = [f"{kw['icon']} {kw['keyword']}" for kw in risk['matched_keywords'][:3]]
                keyword_str = "; ".join(kw_list)
            
            results.append({
                'Mức độ': risk['risk_level'],
                'Điểm rủi ro': risk['risk_score'],
                'Tiêu đề': article['title'],
                'Mã CK': ', '.join(stock_codes),
                'Ngày': article['date'],
                'Keyword nguy cơ': keyword_str,
                'Số keyword': risk['keyword_count'],
                'Nhóm': '; '.join(risk['categories']) if risk['categories'] else '',
                'URL': article['url'],
                'Nguồn': article['source']
            })
        
        self.stats['specific_stocks'] = len(results)
        return pd.DataFrame(results)

# ═══════════════════════════════════════════════════════════
# STREAMLIT APP
# ═══════════════════════════════════════════════════════════

def main():
    # Header
    st.markdown('<div class="main-header">📰 Stock News Scraper & Risk Analyzer</div>', unsafe_allow_html=True)
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
            **Tính năng:**
            - ✅ Lọc tin tổng quan thị trường
            - ✅ Phân tích 6 nhóm keyword nguy cơ
            - ✅ Tính điểm rủi ro tự động
            - ✅ Xuất Excel
            
            **Version:** 2.1  
            **Updated:** 15/10/2025
            """)
    
    # Main content
    if 'run_scraper' not in st.session_state:
        st.session_state['run_scraper'] = False
    
    if st.session_state['run_scraper']:
        with st.spinner('🔄 Đang cào tin...'):
            time.sleep(1)  # Simulate scraping
            
            scraper = StockScraperV2(time_filter_hours=time_hours)
            df = scraper.generate_demo_data()
            
            # Filter by risk level
            if risk_filter:
                df = df[df['Mức độ'].isin(risk_filter)]
            
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
        col1, col2, col3, col4 = st.columns(4)
        
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
        
        st.markdown("---")
        
        # Data table
        st.subheader("📋 Kết quả")
        st.dataframe(
            df,
            use_container_width=True,
            height=400,
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
        
        # Export
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("💾 Xuất dữ liệu")
        
        with col2:
            # Excel export
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Stock News')
            
            st.download_button(
                label="📥 Tải Excel",
                data=output.getvalue(),
                file_name=f"stock_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        # Keyword table
        with st.expander("📋 Bảng 6 nhóm keyword nguy cơ"):
            for category, data in scraper.risk_categories.items():
                st.markdown(f"### {data['icon']} {category}")
                keywords = [kw for kw, _ in data['keywords']]
                st.write(", ".join(keywords))
                st.markdown("---")
    
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
            **📰 Nguồn tin**
            - CafeF
            - VietStock
            - Báo Mới
            - Người Quan Sát
            
            **💾 Xuất dữ liệu**
            - File Excel đầy đủ
            - Bảng phân tích chi tiết
            """)

if __name__ == "__main__":
    main()
