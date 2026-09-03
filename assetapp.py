import streamlit as st
import FinanceDataReader as fdr
import pyupbit
import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import plotly.express as px

# 페이지 설정
st.set_page_config(page_title="통합자산관리", layout="wide")

# (인덱스 숨기기 CSS 제거 - st.dataframe의 hide_index=True 사용)

# 한국 주식 종목 리스트 (캐싱을 통해 속도 향상)
@st.cache_data
def get_krx_names():
    try:
        df_krx = fdr.StockListing('KRX')
        return dict(zip(df_krx['Code'], df_krx['Name']))
    except:
        return {}

krx_symbols = get_krx_names()

# 한국 거래소 목록에 없거나 가져오기 실패한 경우 네이버 금융에서 종목명 조회
@st.cache_data
def get_naver_stock_name(symbol):
    try:
        import urllib.request
        import re
        url = f"https://finance.naver.com/item/main.naver?code={symbol}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            html = response.read().decode('utf-8', 'ignore')
            match = re.search(r'<title>(.*?)</title>', html)
            if match:
                name = match.group(1).split(':')[0].strip()
                if name:
                    return name
    except:
        pass
    return symbol

# 기본 자산 설정
DEFAULT_ASSETS = [
    {"symbol": "BTC", "count": 0.20},
    {"symbol": "ETH", "count": 3},
    {"symbol": "TSLA", "count": 45},
    {"symbol": "GOOGL", "count": 10},
    {"symbol": "SPCX", "count": 45},
    {"symbol": "BMNR", "count": 50},
#    {"symbol": "000660", "count": 2},
    {"symbol": "005935", "count": 20},
    {"symbol": "005930", "count": 20} 
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
            if symbol[0].isdigit(): # 한국 종목 코드인 경우
                currency = "KRW"
                name = krx_symbols.get(symbol) # 종목명으로 치환
                if not name:
                    name = get_naver_stock_name(symbol)
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
# --- 역사적 데이터 수집용 헬퍼 함수 ---
@st.cache_data
def get_historical_exchange_rate(days):
    start_date = (datetime.now() - pd.Timedelta(days=days)).strftime('%Y-%m-%d')
    # 1. yfinance 시도
    try:
        df = yf.Ticker("USDKRW=X").history(start=start_date)
        if not df.empty:
            df.index = df.index.tz_localize(None).normalize()
            return df['Close']
    except:
        pass
    # 2. FinanceDataReader 시도
    try:
        df = fdr.DataReader("USD/KRW", start_date)
        if not df.empty:
            df.index = pd.to_datetime(df.index).normalize()
            return df['Close']
    except:
        pass
    # 3. 실패 시 고정값 반환
    rate = get_live_rate()
    idx = pd.date_range(end=datetime.now(), periods=days + 1, freq='D').normalize()
    return pd.Series(rate, index=idx)

@st.cache_data
def get_asset_historical_prices(symbol, days):
    symbol = symbol.upper()
    start_date = (datetime.now() - pd.Timedelta(days=days)).strftime('%Y-%m-%d')
    
    # 1. 암호화폐 (업비트)
    try:
        # 업비트 get_ohlcv는 count 파라미터가 과거 거래일 수이므로 조금 넉넉하게 요청
        df = pyupbit.get_ohlcv(f"KRW-{symbol}", interval="day", count=days + 10)
        if df is not None and not df.empty:
            df.index = pd.to_datetime(df.index).normalize()
            return df['close'], "KRW"
    except:
        pass
        
    # 업비트 실패 시 yfinance 크립토 조회 시도 (BTC-USD 등)
    if symbol in ["BTC", "ETH", "XRP", "SOL", "ADA", "DOGE"]:
        try:
            df = yf.Ticker(f"{symbol}-USD").history(start=start_date)
            if not df.empty:
                df.index = df.index.tz_localize(None).normalize()
                return df['Close'], "USD"
        except:
            pass

    # 2. 한국 주식 (종목 코드가 숫자인 경우)
    if symbol.isdigit():
        # FinanceDataReader 시도
        try:
            df = fdr.DataReader(symbol, start=start_date)
            if not df.empty:
                df.index = pd.to_datetime(df.index).normalize()
                return df['Close'], "KRW"
        except:
            pass
        # yfinance KOSPI 시도 (.KS)
        try:
            df = yf.Ticker(f"{symbol}.KS").history(start=start_date)
            if not df.empty:
                df.index = df.index.tz_localize(None).normalize()
                return df['Close'], "KRW"
        except:
            pass
        # yfinance KOSDAQ 시도 (.KQ)
        try:
            df = yf.Ticker(f"{symbol}.KQ").history(start=start_date)
            if not df.empty:
                df.index = df.index.tz_localize(None).normalize()
                return df['Close'], "KRW"
        except:
            pass

    # 3. 해외 주식 (그 외의 경우)
    try:
        df = yf.Ticker(symbol).history(start=start_date)
        if not df.empty:
            df.index = df.index.tz_localize(None).normalize()
            return df['Close'], "USD"
    except:
        pass

    return pd.Series(dtype=float), "KRW"

# --- 메인 UI ---
if 'assets' not in st.session_state:
    st.session_state.assets = DEFAULT_ASSETS

rate = get_live_rate()

# 사이드바 메뉴 선택
menu = st.sidebar.radio("📋 메뉴 선택", ["💰 실시간 자산 현황", "📈 역사적 자산 추이"])

if menu == "💰 실시간 자산 현황":
    st.title("💰 통합자산관리 - 실시간 자산 현황")
    
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
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.caption(f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')} (30초 간격 갱신)")

    time.sleep(30)
    st.rerun()

else:
    st.title("📈 역사적 자산 추이 분석")
    
    # 사이드바 분석 설정
    st.sidebar.header("⚙️ 분석 설정")
    period_days = st.sidebar.selectbox(
        "조회 기간 선택",
        options=[7, 30, 90, 180, 365],
        format_func=lambda x: f"{x}일"
    )
    
    with st.spinner("과거 자산 데이터를 수집 및 분석 중입니다..."):
        # 1. 날짜 범위 생성
        start_dt = datetime.now() - pd.Timedelta(days=period_days)
        date_range = pd.date_range(start=start_dt, end=datetime.now(), freq='D').normalize()
        
        # 2. 환율 및 개별 자산 역사적 데이터 수집
        fx = get_historical_exchange_rate(period_days)
        fx_aligned = fx.reindex(date_range).ffill().bfill()
        
        df_val = pd.DataFrame(index=date_range)
        df_weight = pd.DataFrame(index=date_range)
        
        df_prices = pd.DataFrame(index=date_range)
        df_prices['FX'] = fx_aligned
        
        # 보유한 자산에 대해 계산
        has_assets = False
        for a in st.session_state.assets:
            symbol = a['symbol']
            count = a['count']
            if count <= 0:
                continue
                
            has_assets = True
            prices, curr = get_asset_historical_prices(symbol, period_days)
            
            # 조회 실패 시 실시간 가치 상수로 채워 백업 처리
            if prices.empty:
                live_price, live_curr, live_name = get_asset_info(symbol)
                prices = pd.Series(live_price, index=date_range)
                curr = live_curr
                
            prices_aligned = prices.reindex(date_range).ffill().bfill()
            if curr == "USD":
                prices_krw = prices_aligned * df_prices['FX']
            else:
                prices_krw = prices_aligned
                
            name = krx_symbols.get(symbol)
            if not name and symbol.isdigit():
                name = get_naver_stock_name(symbol)
            if not name:
                name = symbol
                
            col_name = f"{name} ({symbol})" if name != symbol else symbol
            df_val[col_name] = prices_krw * count
            
        if not has_assets or df_val.empty:
            st.warning("포트폴리오에 자산이 비어 있거나 보유 수량이 0입니다. '실시간 자산 현황' 페이지에서 자산을 먼저 추가해주세요.")
        else:
            df_val['Total'] = df_val.sum(axis=1)
            
            for col in df_val.columns:
                if col != 'Total':
                    df_weight[col] = (df_val[col] / df_val['Total'] * 100).fillna(0)
                    
            # --- 메트릭 및 요약 정보 ---
            initial_val = df_val['Total'].iloc[0]
            current_val = df_val['Total'].iloc[-1]
            diff_val = current_val - initial_val
            diff_pct = (diff_val / initial_val * 100) if initial_val > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    label="시작 자산 총액",
                    value=f"₩{initial_val:,.0f}"
                )
            with col2:
                st.metric(
                    label="현재 자산 총액",
                    value=f"₩{current_val:,.0f}",
                    delta=f"₩{diff_val:+,.0f} ({diff_pct:+.1f}%)"
                )
            with col3:
                # 최고 성과 자산 탐색
                best_asset = None
                best_perf = -999999
                for col in df_val.columns:
                    if col != 'Total':
                        init_asset_val = df_val[col].iloc[0]
                        curr_asset_val = df_val[col].iloc[-1]
                        if init_asset_val > 0:
                            perf = (curr_asset_val - init_asset_val) / init_asset_val * 100
                            if perf > best_perf:
                                best_perf = perf
                                best_asset = col
                if best_asset:
                    st.metric(
                        label=f"최고 성과 자산 ({period_days}일 기준)",
                        value=best_asset.split(" (")[0],
                        delta=f"{best_perf:+.1f}%"
                    )
                else:
                    st.metric(
                        label="최고 성과 자산",
                        value="N/A"
                    )
            
            # --- 그래프 시각화 ---
            st.divider()
            
            # 마지막 날짜 기준 평가액이 높은 자산 순서대로 컬럼 정렬 (범례 정렬 및 누적 영역 아래쪽 배치 목적)
            latest_val = df_val.drop(columns=['Total'], errors='ignore').iloc[-1]
            sorted_asset_cols = latest_val.sort_values(ascending=False).index.tolist()
            
            # 1. 총 자산 가치 변화 그래프 (Line Chart)
            st.subheader("📊 총 자산 가치 변화 추이 (KRW)")
            
            # Y축 범위를 데이터의 최솟값과 5,000만원 중 더 낮은 값으로 보정하여 시작점 설정
            ymin = min(50000000.0, float(df_val['Total'].min()) * 0.98)
            ymax = float(df_val['Total'].max()) * 1.02
            
            df_val_reset = df_val.reset_index().rename(columns={'index': 'Date'})
            fig_total = px.line(
                df_val_reset,
                x='Date',
                y='Total',
                labels={'Date': '날짜', 'Total': '평가액 (KRW)'}
            )
            fig_total.update_layout(
                yaxis=dict(range=[ymin, ymax], tickformat=",.0f"),
                xaxis=dict(title=None),
                hovermode="x unified",
                margin=dict(l=40, r=40, t=20, b=40)
            )
            fig_total.update_traces(
                hovertemplate="₩%{y:,.0f}<extra></extra>"
            )
            st.plotly_chart(fig_total, use_container_width=True, config={'displaylogo': False})
            
            # 2. 자산별 평가액 변화 그래프 (Line Chart)
            st.subheader("📈 자산별 평가액 변화 추이 (KRW)")
            
            fig_assets = px.line(
                df_val_reset,
                x='Date',
                y=sorted_asset_cols,
                labels={'Date': '날짜', 'value': '평가액 (KRW)', 'variable': '자산'}
            )
            fig_assets.update_layout(
                yaxis=dict(tickformat=",.0f"),
                xaxis=dict(title=None),
                hovermode="x unified",
                legend=dict(
                    title=None,
                    orientation="h",
                    yanchor="top",
                    y=-0.15,
                    xanchor="center",
                    x=0.5
                ),
                margin=dict(l=40, r=40, t=20, b=120)
            )
            fig_assets.update_traces(
                hovertemplate="₩%{y:,.0f}<extra></extra>"
            )
            st.plotly_chart(fig_assets, use_container_width=True, config={'displaylogo': False})
            
            # 3. 자산별 비중 변화 그래프 (Stacked Area Chart)
            st.subheader("🍰 자산별 비중 변화 추이 (%)")
            
            df_weight_reset = df_weight.reset_index().rename(columns={'index': 'Date'})
            fig_weight = px.area(
                df_weight_reset,
                x='Date',
                y=sorted_asset_cols,
                labels={'Date': '날짜', 'value': '비중 (%)', 'variable': '자산'}
            )
            fig_weight.update_layout(
                yaxis=dict(ticksuffix="%", range=[0, 100]),
                xaxis=dict(title=None),
                hovermode="x unified",
                legend=dict(
                    title=None,
                    orientation="h",
                    yanchor="top",
                    y=-0.15,
                    xanchor="center",
                    x=0.5
                ),
                margin=dict(l=40, r=40, t=20, b=120)
            )
            fig_weight.update_traces(
                hovertemplate="%{y:.1f}%<extra></extra>"
            )
            st.plotly_chart(fig_weight, use_container_width=True, config={'displaylogo': False})


