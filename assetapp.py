import streamlit as st
import pyupbit
import yfinance as yf
import pandas as pd
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="나의 자산 대시보드", layout="centered")

def get_asset_info(symbol):
    symbol = symbol.upper()
    # 1. 코인 체크 (Upbit)
    try:
        p = pyupbit.get_current_price(f"KRW-{symbol}")
        if p: return p, "KRW", "코인"
    except: pass

    # 2. 주식 체크 (yfinance)
    # 한국 주식은 티커 뒤에 .KS 또는 .KQ를 붙여 시도
    search_list = [symbol, symbol + ".KS", symbol + ".KQ"]
    for s in search_list:
        try:
            t = yf.Ticker(s)
            info = t.info
            # 장전 가격 우선, 없으면 현재가
            price = info.get('preMarketPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            if price:
                currency = "KRW" if ".K" in s else "USD"
                status = "장전(Pre)" if info.get('preMarketPrice') else "정규/종가"
                return price, currency, status
        except: continue
    return 0, "KRW", "미확인"

# 환율
@st.cache_data(ttl=600)
def get_rate():
    try:
        return yf.Ticker("USDKRW=X").fast_info['last_price']
    except: return 1350.0

st.title("📱 스마트 자산 관리")

if 'assets' not in st.session_state:
    # 이전에 말씀하신 자산 정보를 여기에 미리 넣으실 수 있습니다.
    st.session_state.assets = []

rate = get_rate()

with st.sidebar:
    st.header("자산 추가")
    new_sym = st.text_input("티커(BTC, AAPL, 005930 등)").upper()
    new_cnt = st.number_input("수량", min_value=0.0)
    if st.button("반영하기"):
        found = False
        for a in st.session_state.assets:
            if a['symbol'] == new_sym:
                a['count'] = new_cnt
                found = True; break
        if not found: st.session_state.assets.append({"symbol": new_sym, "count": new_cnt})
        st.rerun()

# 리스트 출력
total_krw = 0
display_list = []
for a in st.session_state.assets:
    price, curr, status = get_asset_info(a['symbol'])
    p_krw = price * rate if curr == "USD" else price
    total_val = p_krw * a['count']
    total_krw += total_val
    display_list.append({
        "자산": a['symbol'], "상태": status, "수량": a['count'],
        "현재가": f"{price:,.2f} ({curr})", "평가액": f"₩{total_val:,.0f}"
    })

st.metric("총 자산 합계", f"₩{total_krw:,.0f}", f"환율: {rate:,.1f}")
if display_list:
    st.table(pd.DataFrame(display_list))
else:
    st.info("사이드바에서 자산을 추가해 주세요.")
