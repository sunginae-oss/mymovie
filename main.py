from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="시네마 인사이트 대시보드", layout="wide", page_icon="🎬"
)

st.title("🎬 시네마 인사이트 & 박스오피스 대시보드")

# Secrets 키 확인 및 예외 처리
if "KOBIS_KEY" not in st.secrets:
    st.error(
        "Secrets 설정에서 'KOBIS_KEY'를 찾을 수 없습니다. Streamlit Cloud 설정을 확인해 주세요."
    )
    st.stop()

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 상단 탭 구성 (기존 기능 + 신규 창의적 페이지)
tab1, tab2, tab3 = st.tabs(
    [
        "📅 일별 박스오피스",
        "🏆 최근 10년 장르별 흥행 TOP",
        "💎 1000만 클럽 & 알짜 영화 분석",
    ]
)

# KST 기준 날짜 설정
today_kst = datetime.now(ZoneInfo("Asia/Seoul")).date()
max_allowed_date = today_kst - timedelta(days=1)


# ==============================================================================
# TAB 1: 일별 박스오피스 (기존 개선 기능)
# ==============================================================================
with tab1:
    st.sidebar.header("📅 일별 박스오피스 설정")
    selected_date = st.sidebar.date_input(
        "조회하고 싶은 날짜를 선택하세요",
        value=max_allowed_date,
        max_value=max_allowed_date,
        help="오늘 날짜는 아직 집계 전이므로 어제까지 선택할 수 있습니다.",
    )

    target_dt = selected_date.strftime("%Y%m%d")
    st.caption(
        f"📍 조회 기준일: **{selected_date.strftime('%Y년 %m월 %d일')}**"
    )

    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

    try:
        res = requests.get(
            url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10
        )
        data = res.json()

        if "faultInfo" in data:
            st.error("인증키가 올바르지 않습니다. KOBIS_KEY를 확인해 주세요.")
            st.stop()

        box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

        if not box_list:
            st.warning(
                "⚠️ 해당 날짜는 아직 집계 전이거나 데이터가 없습니다. 다른 날짜를 선택해 주세요."
            )
        else:
            df = pd.DataFrame(box_list)

            numeric_cols = [
                "rank",
                "rankInten",
                "audiCnt",
                "audiAcc",
                "scrnCnt",
                "showCnt",
            ]
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col])

            # 포맷팅 함수
            def format_rank_change(row):
                if row.get("rankOldAndNew") == "NEW":
                    return "✨ NEW"
                inten = row.get("rankInten", 0)
                if inten > 0:
                    return f"🔴 ▲{inten}"
                elif inten < 0:
                    return f"🔵 ▼{abs(inten)}"
                return "➖ 0"

            def format_movie_title(row):
                title = row["movieNm"]
                if row["audiAcc"] >= 1_000_000:
                    return f"🏆 {title}"
                return title

            df["순위변동"] = df.apply(format_rank_change, axis=1)
            df["표시영화명"] = df.apply(format_movie_title, axis=1)

            # 상단 1위 지표 카드
            top_movie = df.sort_values("rank").iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("🥇 당일 1위", top_movie["표시영화명"])
            c2.metric("🍿 당일 관객수", f"{top_movie['audiCnt']:,} 명")
            c3.metric("🎞️ 누적 관객수", f"{top_movie['audiAcc']:,} 명")

            st.divider()

            # 메인 표
            table = df[
                [
                    "rank",
                    "순위변동",
                    "표시영화명",
                    "openDt",
                    "audiCnt",
                    "audiAcc",
                    "scrnCnt",
                ]
            ].copy()
            table.columns = [
                "순위",
                "변동",
                "영화명",
                "개봉일",
                "당일 관객수",
                "누적 관객수",
                "스크린수",
            ]

            st.subheader("📋 박스오피스 TOP 10")
            st.dataframe(
                table.sort_values("순위"),
                column_config={
                    "당일 관객수": st.column_config.NumberColumn(
                        format="%d 명"
                    ),
                    "누적 관객수": st.column_config.NumberColumn(
                        format="%d 명"
                    ),
                    "스크린수": st.column_config.NumberColumn(
                        format="%d 개"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )

            # 차트
            st.subheader("📈 당일 관객수 상위 5편")
            top5 = table.sort_values("당일 관객수", ascending=False).head(5)
            st.bar_chart(top5.set_index("영화명")["당일 관객수"])

    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")


# ==============================================================================
# TAB 2: 최근 10년간 장르별 흥행 TOP (추가 요청 반영)
# ==============================================================================
with tab2:
    st.header("🏆 최근 10년 역대 장르별 대표 흥행작 명예의 전당")
    st.caption(
        "KOBIS 공식 10개년 대표 흥행작 데이터를 장르별로 나열하여 보여줍니다."
    )

    # 10년간 장르별 역대 흥행 리스트 (KOBIS 통계 기반 큐레이션 데이터)
    genre_data = [
        {
            "장르": "드라마/코미디",
            "영화명": "극한직업",
            "개봉연도": "2019년",
            "누적관객수": "1,626만 명",
            "매출액": "약 1,396억 원",
            "한줄평": "지금까지 이런 맛은 없었다! 역대 한국 코미디 영화 최고 흥행작",
        },
        {
            "장르": "액션/SF",
            "영화명": "범죄도시2",
            "개봉연도": "2022년",
            "누적관객수": "1,269만 명",
            "매출액": "약 1,312억 원",
            "한줄평": "진실의 방으로! 팬데믹 이후 첫 1,000만 관객을 돌파한 마동석 표 액션",
        },
        {
            "장르": "시대극/사극",
            "영화명": "명량",
            "개봉연도": "2014년",
            "누적관객수": "1,761만 명",
            "매출액": "약 1,357억 원",
            "한줄평": "대한민국 역대 박스오피스 최다 관객 수 1위 불멸의 기록",
        },
        {
            "장르": "판타지/웹툰원작",
            "영화명": "신과함께-죄와 벌",
            "개봉연도": "2017년",
            "누적관객수": "1,441만 명",
            "매출액": "약 1,157억 원",
            "한줄평": "저승법에 따라 49일간 7개의 재판을 받는 화려한 CG 판타지 대작",
        },
        {
            "장르": "애니메이션",
            "영화명": "겨울왕국 2",
            "개봉연도": "2019년",
            "누적관객수": "1,375만 명",
            "매출액": "약 1,147억 원",
            "한줄평": "애니메이션 최초 1,000만 클럽 연타석 홈런을 친 디즈니 스튜디오",
        },
        {
            "장르": "오컬트/스릴러",
            "영화명": "파묘",
            "개봉연도": "2024년",
            "누적관객수": "1,191만 명",
            "매출액": "약 1,151억 원",
            "한줄평": "험한 것이 나왔다! 오컬트 장르 최초 1,000만 관객 신화 작성",
        },
        {
            "장르": "뮤지컬/음악",
            "영화명": "알라딘",
            "개봉연도": "2019년",
            "누적관객수": "1,279만 명",
            "매출액": "약 1,090억 원",
            "한줄평": "N차 관람과 떼창 열풍을 일으킨 흥겨운 실사 라이브 액션",
        },
        {
            "장르": "어드벤처/히어로",
            "영화명": "어벤져스: 엔드게임",
            "개봉연도": "2019년",
            "누적관객수": "1,397만 명",
            "매출액": "약 1,221억 원",
            "한줄평": "마블 10년 대서사의 장엄한 피날레",
        },
    ]

    df_genre = pd.DataFrame(genre_data)

    # 장르 선택 필터 위젯
    genres = ["전체"] + list(df_genre["장르"].unique())
    selected_genre = st.selectbox("🎭 보고 싶은 장르를 선택하세요", genres)

    if selected_genre != "전체":
        df_show = df_genre[df_genre["장르"] == selected_genre]
    else:
        df_show = df_genre

    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.info(
        "💡 **알고 계셨나요?** 지난 10년간 최고 흥행 수익(매출액 기준) 1위는 1,396억 원을 기록한 **<극한직업>**입니다."
    )


# ==============================================================================
# TAB 3: 1000만 클럽 & 알짜 영화 분석 (창의적 페이지)
# ==============================================================================
with tab3:
    st.header("⚡ 박스오피스 알짜배기 영화 분석 (가성비 지수)")
    st.caption(
        "스크린수 대비 관객수를 얼마나 끌어모았는지 계산하여 '알짜배기 영화'를 판별합니다."
    )

    if "df" in locals() and not df.empty:
        # 알짜 지수 계산 (스크린 1개당 관객 수)
        df_efficiency = df.copy()
        df_efficiency["스크린당관객수"] = (
            df_efficiency["audiCnt"] / df_efficiency["scrnCnt"]
        ).round(1)

        st.subheader("📊 선택한 날짜 기준 '스크린 대비 최고 효율' TOP 5")

        top_eff = df_efficiency.sort_values(
            by="스크린당관객수", ascending=False
        ).head(5)

        cols = st.columns(5)
        for idx, (_, row) in enumerate(top_eff.iterrows()):
            with cols[idx]:
                st.metric(
                    label=f"🔥 {row['movieNm']}",
                    value=f"{int(row['스크린당관객수']):,} 명/관",
                    delta=f"순위: {row['rank']}위",
                )

        st.markdown("---")

        # 천만영화 달성 여부 모션 이벤트
        has_ten_million = (df["audiAcc"] >= 10_000_000).any()
        if has_ten_million:
            st.balloons()
            st.success(
                "🎉 현재 박스오피스에 **누적 관객 1,000만 명**을 돌파한 명예의 전당 영화가 상영 중입니다!"
            )
        else:
            st.info(
                "💬 현재 순위권 내에 1,000만 돌파 영화는 없지만, 새로운 대박작이 성장 중입니다."
            )
    else:
        st.warning(
            "Tab 1에서 날짜를 선택하여 정상적으로 데이터를 불러온 후 확인하실 수 있습니다."
        )
