import streamlit as st
import pyupbit
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="통합자산관리", layout="wide")

# 인덱스(번호) 열 숨기기 CSS
st.markdown("""
    <style>
    thead tr th:first-child {display:none}
    tbody th {display:none}
    </style>
    """, unsafe_allow_html=True)

def get_asset_info(symbol):
    symbol = symbol.upper()
    # 1. 코인 체크
    try:
        p = pyupbit.get_current_price(f"KRW-{symbol}")
        if p: return p, "KRW"
    except: pass

    # 2. 주식 체크
    search_list = [symbol, symbol + ".KS", symbol + ".KQ"]
    for s in search_list:
        try:
            t = yf.Ticker(s)
            info = t.info
            price = info.get('preMarketPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            if price:
                currency = "KRW" if ".K" in s else "USD"
                return price, currency
        except: continue
    return 0, "KRW"

def get_live_rate():
    try:
        rate_data = yf.Ticker("USDKRW=X")
        return rate_data.fast_info['last_price']
    except:
        return 1350.0

# --- 메인 UI ---
st.title("💰 통합자산관리")
st.caption("30초마다 자동으로 데이터를 갱신합니다.")

if 'assets' not in st.session_state:
    st.session_state.assets = []

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

# 데이터 계산
total_krw = 0
display_data = []

for a in st.session_state.assets:
    price, curr = get_asset_info(a['symbol'])
    price_krw = price * rate if curr == "USD" else price
    valuation = price_krw * a['count']
    total_krw += valuation
    
    # 수량 포맷팅: 소수점 이하가 0이면 정수로, 아니면 소수점 둘째자리까지
    count_display = int(a['count']) if a['count'] == int(a['count']) else f"{a['count']:.2f}"
    
    display_data.append({
        "자산명": a['symbol'],
        "수량": count_display,
        "현재가": f"{price:,.2f} ({curr})",
        "원화 평가액": f"₩{valuation:,.0f}"
    })

# 상단 대시보드
col1, col2 = st.columns(2)
with col1:
    st.metric("총 자산 합계", f"₩{total_krw:,.0f}")
with col2:
    st.metric("실시간 환율 (USD/KRW)", f"{rate:,.2f}원")

# 자산 현황 테이블
if display_data:
    df = pd.DataFrame(display_data)
    st.table(df)
else:
    st.info("왼쪽 사이드바를 이용해 자산을 추가해 주세요.")

st.divider()
st.caption(f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')} (30초 간격 갱신)")

# 30초 대기 후 리로드
time.sleep(30)
st.rerun()
