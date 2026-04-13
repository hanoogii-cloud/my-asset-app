import streamlit as st
import FinanceDataReader as fdr
import pyupbit
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="통합자산관리", layout="wide")

# 인덱스 숨기기 및 테이블 스타일 CSS
st.markdown("""
    <style>
    thead tr th:first-child {display:none}
    tbody th {display:none}
    </style>
    """, unsafe_allow_html=True)

# 한국 주식 종목명 리스트 가져오기 (캐싱 처리하여 속도 최적화)
@st.cache_data
def get_krx_list():
    df_krx = fdr.StockListing('KRX')
    return dict(zip(df_krx['Code'], df_krx['Name']))

krx_symbols = get_krx_list()

# 기본 보유 자산 설정
DEFAULT_ASSETS = [
    {"symbol": "BTC", "count": 0.22},
    {"symbol": "ETH", "count": 3},
    {"symbol": "TSLA", "count": 45},
    {"symbol": "GOOGL", "count": 27},
    {"symbol": "304100", "count": 200} # SOL 미국배당다우존스 예시
]

def get_asset_info(symbol):
    symbol = symbol.upper()
    name = symbol
    
    # 1. 암호화폐 확인 (업비트)
    try:
        p = pyupbit.get_current_price(f"KRW-{symbol}")
        if p: return p, "KRW", symbol
    except: pass

    # 2. 주식 확인
    try:
        df = fdr.DataReader(symbol)
        if not df.empty:
            price = df['Close'].iloc[-1]
            if symbol.isdigit(): # 한국 주식인 경우
                currency = "KRW"
                name = krx_symbols.get(symbol, symbol) # 종목명으로 변환
            else:
                currency = "USD"
                name = symbol
            return float(price), currency, name
    except Exception as e:
        pass

    return 0, "KRW", symbol

def get_live_rate():
    try:
        rate_data = yf.Ticker("USDKRW=X")
        return rate_data.fast_info['last_price']
    except:
        return 1350.0

# --- 메인 UI ---
st.title("💰 통합자산관리 시스템")
st.caption("30초마다 자동으로 데이터를 갱신하며, 금액은 전체 단위로 표시됩니다.")

if 'assets' not in st.session_state:
    st.session_state.assets = DEFAULT_ASSETS

rate = get_live_rate()

with st.sidebar:
    st.header("➕ 자산 추가/수정")
    new_sym = st.text_input("티커 (예: BTC, NVDA, 005930)").upper()
    new_cnt = st.number_input("보유 수량", min_value=0.0, step=0.01, format="%.2f")
    
    if st.button("포트폴리오에 반영"):
        if new_sym:
            found = False
            for a in st.session_state.assets:
                if a['symbol'] == new_sym:
                    a['count'] = new_cnt
                    found = True; break
            if not found:
                st.session_state.assets.append({"symbol": new_sym, "count": new_cnt})
            st.success(f"{new_sym} 반영 완료!")
            time.sleep(0.5)
            st.rerun()

# --- 데이터 계산 ---
total_krw = 0
asset_details = []

for a in st.session_state.assets:
    price, curr, name = get_asset_info(a['symbol'])
    price_krw = price * rate if curr == "USD" else price
    valuation = price_krw * a['count']
    
    total_krw += valuation
    
    asset_details.append({
        "name": name,
        "count": a['count'],
        "price": price,
        "curr": curr,
        "valuation": valuation
    })

display_data = []
for detail in asset_details:
    count_display = f"{detail['count']:,}" if detail['count'] == int(detail['count']) else f"{detail['count']:,.2f}"
    percentage = (detail['valuation'] / total_krw * 100) if total_krw > 0 else 0
    
    # 현재가 포맷팅
    if detail['curr'] == "USD":
        price_display = f"${detail['price']:,.2f}"
    else:
        price_display = f"₩{int(detail['price']):,}"

    display_data.append({
        "종목": detail['name'],
        "수량": count_display,
        "현재가": price_display,
        "평가액": f"₩{int(detail['valuation']):,}",
        "비중(%)": f"{percentage:.1f}%"
    })

# --- 화면 출력 ---
col1, col2 = st.columns(2)
with col1:
    st.metric("총 자산 합계", f"₩{total_krw:,.0f}")
with col2:
    st.metric("실시간 환율 (USD/KRW)", f"{rate:,.2f}원")

if display_data:
    df = pd.DataFrame(display_data)
    st.table(df)
else:
    st.info("왼쪽 사이드바를 이용해 자산을 추가해 주세요.")

st.divider()
st.caption(f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')} (30초 간격 갱신)")

time.sleep(30)
st.rerun()
