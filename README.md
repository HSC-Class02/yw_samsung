# Samsung Electronics DART Financial Analysis Agent

[![🔗 대시보드 바로가기](docs/dashboard-badge.svg)](https://hsc-class02.github.io/yw_samsung/)

삼성전자(005930, OpenDART Corp. Code `00126380`)의 DART 정기보고서를 자동 수집하고 연결재무제표 주요 수치와 재무비율을 계산하여 GitHub Pages Dashboard로 제공하는 프로젝트입니다.

## 🔗 대시보드

**https://hsc-class02.github.io/yw_samsung/**

GitHub 저장소: https://github.com/HSC-Class02/yw_samsung

> 현재 저장소가 비어 있는 상태를 기준으로 프로젝트를 생성했습니다. GitHub 계정 연결이 완료되면 아래 파일을 저장소에 업로드하면 됩니다.

## 제공 기능

- 2010년부터 사업보고서 / 반기보고서 / 1분기보고서 / 3분기보고서 수집
- 2015년 이후: OpenDART `fnlttSinglAcntAll.json` 기반 연결재무제표(CFS) 추출
- 2010~2014년: OpenDART 공시검색 + 원문 `document.xml` 다운로드 및 legacy table 후보 추출
- 주요 수치: 매출액, 영업이익, 당기순이익, 자산, 부채, 자본, 현금성자산, 현금흐름, EPS
- 주요 비율: 영업이익률, 순이익률, ROE, ROA, 부채비율, 자기자본비율, 총자산회전율
- Annual / Half-year / Quarterly 3개 표 제공
- 매출/영업이익, 수익성, 재무상태, 현금흐름 차트 제공
- DART 원문 접수번호 및 링크 저장
- DART 원문 접수번호/원문 URL 저장
- 원문 보고서 ZIP 저장 옵션(기본값 false; 대용량 repo 방지를 위해 필요 시 true)
- GitHub Actions: 매월 1일 자동 수집 + Dashboard 배포
- 국내 비교 참고 기업(Peer Firms) 표 제공

## DART API 키 입력

1. OpenDART에서 인증키를 발급합니다: https://opendart.fss.or.kr/
2. GitHub 저장소의 **Settings → Secrets and variables → Actions → New repository secret**으로 이동합니다.
3. 다음 Secret을 생성합니다.

```text
Name: OPENDART_API_KEY
Value: 발급받은 40자리 OpenDART 인증키
```

선택적으로 다음 Variables를 사용할 수 있습니다.

```text
START_YEAR=2010
END_YEAR=2026
DART_CORP_CODE=00126380
SAVE_RAW_REPORTS=false
```

API 키는 코드나 README에 직접 입력하지 말고 반드시 GitHub Actions Secret으로 관리하세요.

## GitHub Pages 설정

1. 저장소의 **Settings → Pages**로 이동합니다.
2. **Build and deployment → Source: GitHub Actions**를 선택합니다.
3. `.github/workflows/dart-update-and-pages.yml`이 실행되면 `dashboard/`가 GitHub Pages로 배포됩니다.
4. 대시보드 주소는 `https://hsc-class02.github.io/yw_samsung/`입니다.

## 월 1일 자동 업데이트

Workflow는 다음과 같이 구성되어 있습니다.

- `schedule`: 매월 1일 03:00 UTC (한국시간 12:00)
- `workflow_dispatch`: 수동 실행 가능
- DART 데이터 수집 → JSON/CSV/원문 저장 → Dashboard artifact 생성 → GitHub Pages 배포 → 변경 파일 commit/push

OpenDART 공시검색 API는 `list.json`, 원문 보고서는 `document.xml`, 2015년 이후 정기보고서 전체 재무제표는 `fnlttSinglAcntAll.json`을 사용합니다. 공식 문서상 재무제표 API의 사업연도는 2015년 이후부터 제공되며, 보고서 코드는 사업보고서 `11011`, 반기 `11012`, 1분기 `11013`, 3분기 `11014`입니다.

## 2010~2014 데이터에 대한 주의

OpenDART의 정기보고서 재무 API가 2015년 이후 제공되므로 2010~2014년은 공시 원문 ZIP을 수집하고 표 형태의 계정 후보를 추출하는 별도 경로를 사용합니다. 과거 문서 형식의 차이 때문에 자동 매핑이 불확실한 값은 임의로 확정하지 않고 `legacy_candidates`에 원문 후보를 보존합니다. 따라서 2010~2014 수치의 완전 자동 표준화가 필요한 경우에는 해당 연도 원문 구조에 맞춘 계정 매핑을 추가하는 것이 안전합니다.

## 폴더 구조

```text
.
├── .github/workflows/dart-update-and-pages.yml
├── config/metrics.json
├── dashboard/index.html
├── data/financials.csv
├── data/financials.json
├── data/filings.json
├── data/last_update.json
├── docs/dashboard-badge.svg
├── reports/YYYY/*.zip
├── src/update_data.py
├── requirements.txt
└── README.md
```

## 데이터 단위

원본 DART 금액 단위는 보고서/API 응답의 원단위를 유지합니다. Dashboard에서는 가독성을 위해 금액을 억원/조원 수준으로 표시합니다. 재무비율은 원 데이터에서 계산하며, 분기/반기 손익은 DART의 당기/누적 금액 구조를 보존합니다.

## 국내 Peer Firms

비교 참고 기업군은 삼성전자의 사업영역과 국내 반도체·전자산업의 중첩성을 기준으로 구성했습니다.

| 기업 | 종목코드 | 비교 관점 |
|---|---:|---|
| SK하이닉스 | 000660 | 메모리 반도체·HBM |
| DB하이텍 | 000990 | 파운드리·아날로그/전력 반도체 |
| LX세미콘 | 108320 | 팹리스·디스플레이/반도체 설계 |
| 삼성전기 | 009150 | 전자부품·MLCC·패키지 기판 |
| LG전자 | 066570 | 가전·전장·전자제품 |

이는 공식적인 증권사 peer-group이나 투자등급을 의미하지 않습니다.

## 데이터 출처

- Financial Supervisory Service OpenDART: https://opendart.fss.or.kr/
- DART disclosure viewer: https://dart.fss.or.kr/

재무정보는 공시의무자가 제출한 자료에 기반하며, OpenDART 역시 원문 공시와 비교·확인할 것을 안내하고 있습니다.

## ZIP 업로드 시 주의

제공 ZIP은 `.github` 같은 숨김 디렉터리를 ZIP에 넣지 않는 **업로드 편의형**으로 만들었습니다. `workflows/dart-update-and-pages.yml`을 GitHub 저장소에서 다음 경로로 이동해 주세요.

```text
.github/workflows/dart-update-and-pages.yml
```

GitHub 웹에서 `Add file → Create new file`을 선택한 뒤 파일 경로를 `.github/workflows/dart-update-and-pages.yml`로 지정하고, ZIP 안의 workflow 내용을 붙여넣어도 됩니다.
