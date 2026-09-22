import os
import json
import datetime
import time
import requests

# ==========================================
# 1. 수집 대상 아파트 단지 및 설정
# ==========================================
TARGET_APARTS = [
    {
        "name": "행당 신동아",
        "complexNo": "2297",
        "tradeType": "A1",  # 매매
        "targetAreas": ["76", "81"] # 소수점 생략하여 유연하게 매칭
    },
    {
        "name": "염리 상록",
        "complexNo": "3326",
        "tradeType": "A1",
        "targetAreas": ["83"]
    },
    {
        "name": "고덕 아남",
        "complexNo": "3175",
        "tradeType": "A1",
        "targetAreas": ["60", "61"]
    },
    {
        "name": "상아 2차 (오금동)",
        "complexNo": "3158",
        "tradeType": "A1",
        "targetAreas": ["64"]
    },
    {
        "name": "양평 한신",
        "complexNo": "3087",
        "tradeType": "A1",
        "targetAreas": ["83", "84"]
    },
    {
        "name": "약수 하이츠",
        "complexNo": "874",
        "tradeType": "A1",
        "targetAreas": ["80", "81"]
    }
]

# 특이사항 감지 키워드
SPECIAL_KEYWORDS = ['갭투자', '세낀', '입주유예', '주인거주', '급매', '실입주가능', '월세낀', '안고']

DATA_FILE = "realestate_data.json"
HTML_FILE = "index.html"

# ==========================================
# 2. 네이버 부동산 API 수집 함수
# ==========================================
def fetch_naver_articles(complex_no, trade_type="A1"):
    url = f"https://m.land.naver.com/complex/getComplexArticleList?mktNo=0&complexNo={complex_no}&tradeType={trade_type}&order=prc_asc&page=1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"https://m.land.naver.com/complex/info/{complex_no}",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }
    
    articles = []
    for attempt in range(3):
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if "result" in data and "list" in data["result"]:
                    articles = data["result"]["list"]
                    break
        except Exception as e:
            print(f"[{attempt+1}/3] Retry fetching complexNo {complex_no}: {e}")
            time.sleep(2)
            
    return articles

def parse_price(price_str):
    """ '12억 5,000' 형태의 문자열을 만원 단위 정수로 변환 """
    try:
        price_str = price_str.replace(",", "").strip()
        total = 0
        if "억" in price_str:
            parts = price_str.split("억")
            uk = int(parts[0].strip()) if parts[0].strip() else 0
            total += uk * 10000
            rest = parts[1].replace("만", "").strip() if len(parts) > 1 and parts[1].strip() else "0"
            if rest:
                total += int(rest)
        else:
            total = int(price_str.replace("만", "").strip())
        return total
    except:
        return 0

# ==========================================
# 3. 데이터 수집 및 비교 로직
# ==========================================
def collect_today_data(previous_history):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    today_records = []

    last_price_map = {}
    if previous_history:
        latest_date = max(previous_history.keys())
        for item in previous_history[latest_date]:
            art_no = item.get("articleNo")
            if art_no:
                last_price_map[art_no] = item.get("priceNum", 0)

    for apt in TARGET_APARTS:
        raw_list = fetch_naver_articles(apt["complexNo"], apt["tradeType"])
        time.sleep(1)
        
        print(f"[{apt['name']}] 전체 수집된 매물 수: {len(raw_list)}개")
        
        for item in raw_list:
            spc2 = str(item.get("spc2", "")) # 전용면적
            spc1 = str(item.get("spc1", "")) # 공급면적
            
            # targetAreas가 비어있거나 매칭되면 포함
            match_area = False
            if not apt.get("targetAreas"):
                match_area = True
            else:
                for target_area in apt["targetAreas"]:
                    if target_area in spc2 or target_area in spc1:
                        match_area = True
                        break
            
            if not match_area:
                continue

            art_no = str(item.get("atclNo", ""))
            price_str = str(item.get("prc", ""))
            price_num = parse_price(price_str)
            
            price_diff_str = "-"
            if art_no in last_price_map:
                prev_price = last_price_map[art_no]
                diff = price_num - prev_price
                if diff > 0:
                    price_diff_str = f"▲ {diff:,}만원"
                elif diff < 0:
                    price_diff_str = f"▼ {abs(diff):,}만원"
                else:
                    price_diff_str = "변동없음"
            else:
                price_diff_str = "신규"

            feature_text = f"{item.get('atclNm', '')} {item.get('atclFtrDesc', '')}"
            found_specials = [kw for kw in SPECIAL_KEYWORDS if kw in feature_text]
            special_note = ", ".join(found_specials) if found_specials else "-"

            record = {
                "date": today_str,
                "aptName": apt["name"],
                "articleNo": art_no,
                "priceStr": price_str + ("만원" if "억" in price_str or price_str.isdigit() else ""),
                "priceNum": price_num,
                "floor": item.get("flrInfo", "-"),
                "area": f"{spc2}㎡ (전용)",
                "realtor": item.get("rltrNm", "자체등록"),
                "specialNote": special_note,
                "priceDiff": price_diff_str,
                "direction": item.get("direction", "-"),
                "confirmDate": item.get("atclCfmYmd", "-")
            }
            today_records.append(record)

    return today_str, today_records

# ==========================================
# 4. HTML 대시보드 리포트 생성 함수
# ==========================================
def generate_html_report(history_data):
    dates = sorted(list(history_data.keys()))
    latest_date = dates[-1] if dates else "-"
    prev_date = dates[-2] if len(dates) >= 2 else None

    latest_items = history_data.get(latest_date, [])
    prev_items = history_data.get(prev_date, []) if prev_date else []

    total_count_latest = len(latest_items)
    total_count_prev = len(prev_items)
    count_diff = total_count_latest - total_count_prev

    avg_price_latest = int(sum(x["priceNum"] for x in latest_items) / total_count_latest) if total_count_latest > 0 else 0
    avg_price_prev = int(sum(x["priceNum"] for x in prev_items) / total_count_prev) if total_count_prev > 0 else 0
    price_diff = avg_price_latest - avg_price_prev

    apt_names = sorted(list(set(x["name"] for x in TARGET_APARTS)))

    chart_labels = dates
    chart_datasets = {}
    
    for name in apt_names:
        chart_datasets[name] = {"min": [], "max": [], "avg": []}
        for d in dates:
            day_apts = [x for x in history_data[d] if x.get("aptName") == name]
            if day_apts:
                prices = [x["priceNum"] for x in day_apts]
                chart_datasets[name]["min"].append(min(prices))
                chart_datasets[name]["max"].append(max(prices))
                chart_datasets[name]["avg"].append(int(sum(prices) / len(prices)))
            else:
                chart_datasets[name]["min"].append(None)
                chart_datasets[name]["max"].append(None)
                chart_datasets[name]["avg"].append(None)

    count_diff_class = "up" if count_diff > 0 else ("down" if count_diff < 0 else "")
    count_diff_sign = "+" if count_diff > 0 else ""
    price_diff_class = "up" if price_diff > 0 else ("down" if price_diff < 0 else "")
    price_diff_sign = "+" if price_diff > 0 else ""

    filter_buttons = '<button class="filter-btn active" onclick="filterApt(\'ALL\', this)">전체 보기</button>'
    for name in apt_names:
        filter_buttons += f' <button class="filter-btn" onclick="filterApt(\'{name}\', this)">{name}</button>'

    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>부동산 매물 시세 대시보드</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-color: #f4f6f9;
            --card-bg: #ffffff;
            --primary-color: #2563eb;
            --text-color: #1e293b;
            --border-color: #e2e8f0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 20px; text-align: center; }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}
        .card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border: 1px solid var(--border-color);
        }}
        .card h3 {{ font-size: 0.9rem; color: #64748b; margin: 0 0 8px 0; }}
        .card .value {{ font-size: 1.6rem; font-weight: 700; }}
        .card .sub-info {{ font-size: 0.85rem; margin-top: 5px; }}
        .up {{ color: #dc2626; }}
        .down {{ color: #2563eb; }}

        .filter-container {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }}
        .filter-btn {{
            padding: 8px 16px;
            background: #e2e8f0;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.9rem;
            transition: 0.2s;
        }}
        .filter-btn.active {{
            background: var(--primary-color);
            color: white;
        }}

        .chart-box {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 25px;
            border: 1px solid var(--border-color);
        }}

        .table-container {{
            background: var(--card-bg);
            border-radius: 12px;
            overflow-x: auto;
            border: 1px solid var(--border-color);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            text-align: left;
        }}
        th, td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            white-space: nowrap;
        }}
        th {{ background-color: #f8fafc; font-weight: 600; color: #475569; }}
        tr:hover {{ background-color: #f1f5f9; }}
        .badge-special {{
            background-color: #fef2f2;
            color: #dc2626;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 부동산 매물 자동 추적 대시보드</h1>
        <p style="text-align:center; color:#64748b; margin-top:-15px; margin-bottom:25px;">최종 업데이트: {latest_date}</p>

        <div class="summary-grid">
            <div class="card">
                <h3>총 추적 매물 수</h3>
                <div class="value">{total_count_latest}개</div>
                <div class="sub-info">전일 대비: <span class="{count_diff_class}">{count_diff_sign}{count_diff}개</span></div>
            </div>
            <div class="card">
                <h3>전체 평균 매매가</h3>
                <div class="value">{avg_price_latest:,}만원</div>
                <div class="sub-info">전일 대비: <span class="{price_diff_class}">{price_diff_sign}{price_diff:,}만원</span></div>
            </div>
            <div class="card">
                <h3>추적 아파트 단지</h3>
                <div class="value">{len(apt_names)}개 단지</div>
                <div class="sub-info">매매 전용면적 기준 필터링</div>
            </div>
        </div>

        <div class="filter-container">
            {filter_buttons}
        </div>

        <div class="chart-box">
            <h3 id="chart-title">📈 일자별 가격 추이 (전체 평균가)</h3>
            <canvas id="priceChart" height="90"></canvas>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>수집 일자</th>
                        <th>아파트명</th>
                        <th>매매가</th>
                        <th>전일 대비</th>
                        <th>층 / 향</th>
                        <th>특이사항</th>
                        <th>공인중개사</th>
                        <th>매물번호</th>
                    </tr>
                </thead>
                <tbody id="table-body">
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const rawHistory = {json.dumps(history_data, ensure_ascii=False)};
        const chartLabels = {json.dumps(chart_labels, ensure_ascii=False)};
        const chartDatasets = {json.dumps(chart_datasets, ensure_ascii=False)};

        let currentFilter = 'ALL';
        let priceChart = null;

        function renderTable(filterName) {{
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';

            const dates = Object.keys(rawHistory).sort().reverse();
            
            dates.forEach(d => {{
                rawHistory[d].forEach(item => {{
                    if (filterName !== 'ALL' && item.aptName !== filterName) return;

                    const tr = document.createElement('tr');
                    
                    let diffClass = '';
                    if (item.priceDiff && item.priceDiff.includes('▲')) diffClass = 'up';
                    else if (item.priceDiff && item.priceDiff.includes('▼')) diffClass = 'down';

                    const specialHtml = (item.specialNote && item.specialNote !== '-') 
                        ? `<span class="badge-special">${{item.specialNote}}</span>` 
                        : '-';

                    tr.innerHTML = `
                        <td>${{item.date}}</td>
                        <td><b>${{item.aptName}}</b></td>
                        <td><b>${{item.priceStr}}</b></td>
                        <td class="${{diffClass}}">${{item.priceDiff}}</td>
                        <td>${{item.floor}} / ${{item.direction}}</td>
                        <td>${{specialHtml}}</td>
                        <td>${{item.realtor}}</td>
                        <td><a href="https://m.land.naver.com/article/info/${{item.articleNo}}" target="_blank" style="color:#2563eb; text-decoration:none;">${{item.articleNo}}</a></td>
                    `;
                    tbody.appendChild(tr);
                }});
            }});
        }}

        function renderChart(filterName) {{
            const ctx = document.getElementById('priceChart').getContext('2d');
            
            if (priceChart) priceChart.destroy();

            let datasets = [];

            if (filterName === 'ALL') {{
                document.getElementById('chart-title').innerText = '📈 단지별 평균 매매가 추이 (만원)';
                const colors = ['#2563eb', '#dc2626', '#16a34a', '#d97706', '#9333ea', '#0891b2'];
                Object.keys(chartDatasets).forEach((name, idx) => {{
                    datasets.push({{
                        label: name,
                        data: chartDatasets[name].avg,
                        borderColor: colors[idx % colors.length],
                        tension: 0.2,
                        fill: false
                    }});
                }});
            }} else {{
                document.getElementById('chart-title').innerText = `📈 ${{filterName}} 최저 / 최고 / 평균가 추이 (만원)`;
                datasets = [
                    {{ label: '최고가', data: chartDatasets[filterName].max, borderColor: '#dc2626', backgroundColor: '#fef2f2', tension: 0.2 }},
                    {{ label: '평균가', data: chartDatasets[filterName].avg, borderColor: '#2563eb', tension: 0.2 }},
                    {{ label: '최저가', data: chartDatasets[filterName].min, borderColor: '#16a34a', tension: 0.2 }}
                ];
            }}

            priceChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: chartLabels, datasets: datasets }},
                options: {{
                    responsive: true,
                    plugins: {{ legend: {{ position: 'bottom' }} }},
                    scales: {{ y: {{ beginAtZero: false }} }}
                }}
            }});
        }}

        function filterApt(aptName, btn) {{
            currentFilter = aptName;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            renderTable(aptName);
            renderChart(aptName);
        }}

        window.onload = function() {{
            renderTable('ALL');
            renderChart('ALL');
        }};
    </script>
</body>
</html>
"""
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

# ==========================================
# 5. 메인 실행부
# ==========================================
if __name__ == "__main__":
    history_data = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception as e:
            print(f"JSON 읽기 오류: {e}")

    today_str, today_records = collect_today_data(history_data)
    history_data[today_str] = today_records

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    generate_html_report(history_data)
    print(f"[{today_str}] 수집 완료 및 {HTML_FILE} 리포트 생성 성공! (매물 수: {len(today_records)}개)")
