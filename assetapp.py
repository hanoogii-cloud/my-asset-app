import streamlit as st
import FinanceDataReader as fdr
import pyupbit
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="통합자산관리", layout="wide")

# 인덱스 숨기기 CSS
st.markdown("""
    <style>
    thead tr th:first-child {display:none}
    tbody th {display:none}
    </style>
    """, unsafe_allow_html=True)

# 한국 주식 종목 리스트 (캐싱을 통해 속도 향상)
@st.cache_data
def get_krx_names():
    try:
        df_krx = fdr.StockListing('KRX')
        return dict(zip(df_krx['Code'], df_krx['Name']))
    except:
        return {}

krx_symbols = get_krx_names()

# 기본 자산 설정
DEFAULT_ASSETS = [
    {"symbol": "BTC", "count": 0.21},
    {"symbol": "ETH", "count": 3},
    {"symbol": "TSLA", "count": 48},
    {"symbol": "GOOGL", "count": 30},
    {"symbol": "304100", "count": 150} # 솔트룩스
]

def get_asset_info(symbol):
    symbol = symbol.upper()
    name = symbol
    
    # 1. 암호화폐 (업비트)
    try:
        p = pyupbit.get_current_price(f"KRW-{symbol}")
        if p: return p, "KRW", symbol
    except: pass

    # 2. 주식 (국내/해외)
    try:
        df = fdr.DataReader(symbol)
        if not df.empty:
            price = df['Close'].iloc[-1]
            if symbol.isdigit(): # 한국 종목 코드인 경우
                currency = "KRW"
                name = krx_symbols.get(symbol, symbol) # 종목명으로 치환
            else:
                currency = "USD"
                name = symbol
            return float(price), currency, name
    except: pass

    return 0, "KRW", symbol

def get_live_rate():
    try:
        rate_data = yf.Ticker("USDKRW=X")
        return rate_data.fast_info['last_price']
    except:
        return 1350.0

# --- 메인 UI ---
st.title("💰 통합자산관리")

if 'assets' not in st.session_state:
    st.session_state.assets = DEFAULT_ASSETS

rate = get_live_rate()

# 사이드바 입력창
with st.sidebar:
    st.header("➕ 자산 추가/수정")
    new_sym = st.text_input("티커 (예: BTC, NVDA, 005930)").upper()
    new_cnt = st.number_input("보유 수량", min_value=0.0, step=0.01)
    if st.button("포트폴리오에 반영"):
        if new_sym:
            found = False
            for a in st.session_state.assets:
                if a['symbol'] == new_sym:
                    a['count'] = new_cnt
                    found = True; break
            if not found:
                st.session_state.assets.append({"symbol": new_sym, "count": new_cnt})
            st.rerun()

# --- 데이터 계산 ---
total_krw = 0
temp_details = []

for a in st.session_state.assets:
    price, curr, name = get_asset_info(a['symbol'])
    price_krw = price * rate if curr == "USD" else price
    valuation = price_krw * a['count']
    total_krw += valuation
    
    temp_details.append({
        "name": name,
        "count": a['count'],
        "price": price,
        "curr": curr,
        "valuation": valuation
    })

# 테이블용 데이터 구성
display_data = []
for d in temp_details:
    percentage = (d['valuation'] / total_krw * 100) if total_krw > 0 else 0
    
    # 수량 표시 (정수면 깔끔하게, 소수면 2자리까지)
    count_str = f"{d['count']:,}" if d['count'] == int(d['count']) else f"{d['count']:,.2f}"
    
    # 현재가 표시 ($ 또는 ₩ 기호 포함 전체 금액)
    price_str = f"${d['price']:,.2f}" if d['curr'] == "USD" else f"₩{int(d['price']):,}"

    # 리스트에 딕셔너리 추가 (키 이름이 그대로 헤더가 됩니다)
    display_data.append({
        "종목": d['name'],
        "수량": count_str,
        "현재가": price_str,
        "평가액": f"₩{int(d['valuation']):,}",
        "비중(%)": f"{percentage:.1f}%"
    })

# --- 화면 출력 ---
col1, col2 = st.columns(2)
with col1:
    st.metric("총 자산 합계", f"₩{total_krw:,.0f}")
with col2:
    st.metric("실시간 환율 (USD/KRW)", f"{rate:,.2f}원")

if display_data:
    # 딕셔너리의 키가 테이블의 헤더 이름이 됩니다.
    df = pd.DataFrame(display_data)
    st.table(df)

st.divider()
st.caption(f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')} (30초 간격 갱신)")

time.sleep(30)
st.rerun()
