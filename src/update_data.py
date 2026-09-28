from __future__ import annotations
import csv, io, json, os, re, sys, time, zipfile
from datetime import datetime, date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
REPORTS = ROOT / 'reports'
DASHBOARD = ROOT / 'dashboard'
CFG = ROOT / 'config' / 'metrics.json'

BASE = 'https://opendart.fss.or.kr/api'
CORP_CODE = os.getenv('DART_CORP_CODE', '00126380')
STOCK_CODE = '005930'
START_YEAR = int(os.getenv('START_YEAR', '2010'))
END_YEAR = int(os.getenv('END_YEAR', str(datetime.now().year)))
API_KEY = os.getenv('OPENDART_API_KEY', '').strip()
SAVE_RAW = os.getenv('SAVE_RAW_REPORTS', 'false').lower() == 'true'

REPORT_CODES = {'annual':'11011','half-year':'11012','quarterly-q1':'11013','quarterly-q3':'11014'}
REPORT_NAMES = {'11011':'사업보고서','11012':'반기보고서','11013':'1분기보고서','11014':'3분기보고서'}

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=[]; self.cell=[]; self.in_cell=False
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='tr': self.row=[]
        if tag.lower() in ('td','th'): self.cell=[]; self.in_cell=True
    def handle_data(self, data):
        if self.in_cell: self.cell.append(data)
    def handle_endtag(self, tag):
        t=tag.lower()
        if t in ('td','th') and self.in_cell:
            self.row.append(' '.join(''.join(self.cell).split())); self.in_cell=False
        elif t=='tr' and self.row: self.rows.append(self.row)

def api(path, params, binary=False):
    if not API_KEY: raise RuntimeError('OPENDART_API_KEY가 설정되지 않았습니다.')
    q = dict(params); q['crtfc_key']=API_KEY
    req=Request(BASE+'/'+path+'?'+urlencode(q), headers={'User-Agent':'yw-samsung-dart-agent/1.0'})
    with urlopen(req, timeout=60) as r: body=r.read()
    if binary: return body
    obj=json.loads(body.decode('utf-8'))
    if obj.get('status') != '000':
        raise RuntimeError(f"DART API {path}: {obj.get('status')} {obj.get('message')}")
    return obj

def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def get_filings(year):
    # Query a full year so monthly refresh discovers amended/new filings too.
    return api('list.json', {'corp_code':CORP_CODE,'bgn_de':f'{year}0101','end_de':f'{year+1}0430','pblntf_detail_ty':'a001','page_no':1,'page_count':100}, False).get('list',[])

def relevant_filings(year):
    rows=[]
    for x in get_filings(year):
        code=x.get('report_nm','')
        if not any(n in code for n in ('사업보고서','반기보고서','1분기보고서','3분기보고서')):
            continue
        # DART filing date can be in the following calendar year for annual reports.
        # Prefer the business period shown in report_nm, e.g. '(2025.12)'.
        m=re.search(r'\((20\d{2})\.', code)
        if m and int(m.group(1)) != year:
            continue
        rows.append(x)
    # Prefer the latest filing for the same report name, because amended filings can exist.
    best={}
    for x in rows:
        name=x.get('report_nm','')
        if '사업보고서' in name: key='annual'
        elif '반기보고서' in name: key='half-year'
        elif '1분기보고서' in name: key='quarterly-q1'
        elif '3분기보고서' in name: key='quarterly-q3'
        else: continue
        if key not in best or x.get('rcept_dt','') > best[key].get('rcept_dt',''):
            best[key]=dict(x, report_type=key)
    return list(best.values())

def fetch_financials_2015_plus(year, code):
    out=api('fnlttSinglAcntAll.json', {'corp_code':CORP_CODE,'bsns_year':str(year),'reprt_code':code,'fs_div':'CFS'}, False)
    return out.get('list',[])

def parse_num(s):
    if s is None: return None
    s=str(s).strip().replace(',','').replace(' ','')
    if s in ('','-','—','N/A','n/a'): return None
    s=s.replace('(', '-').replace(')', '')
    try: return float(s)
    except: return None

def download_original(rcept_no):
    return api('document.xml', {'rcept_no':rcept_no}, binary=True)

def parse_legacy_zip(blob):
    """Best-effort parser for 2010-2014 original DART filings.
    It searches extracted HTML/XML tables for common account labels and numeric cells.
    The parser intentionally stores raw candidate rows so ambiguous mappings can be audited.
    """
    candidates=[]
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=[n for n in z.namelist() if n.lower().endswith(('.xml','.html','.htm'))]
        for name in names:
            try: txt=z.read(name).decode('utf-8',errors='ignore')
            except: continue
            if '<table' not in txt.lower() and '<row' not in txt.lower(): continue
            p=TableParser();
            try: p.feed(txt)
            except Exception: continue
            for row in p.rows:
                joined=' | '.join(row)
                if any(k in joined for k in ['자산총계','부채총계','자본총계','매출액','영업이익','당기순이익','현금및현금성자산','영업활동현금흐름']):
                    nums=[parse_num(v) for v in row]
                    nums=[v for v in nums if v is not None]
                    if nums: candidates.append({'source':name,'row':row,'numeric_candidates':nums})
    return candidates

def normalize_account(name):
    n=re.sub(r'\s+','',name or '')
    aliases={
      '매출액':'revenue','영업수익':'revenue','수익(매출액)':'revenue',
      '영업이익':'operating_income','영업이익(손실)':'operating_income',
      '당기순이익':'net_income','당기순이익(손실)':'net_income',
      '자산총계':'total_assets','부채총계':'total_liabilities','자본총계':'total_equity',
      '현금및현금성자산':'cash_and_equivalents','현금및현금성자산(금융기관예치금포함)':'cash_and_equivalents',
      '영업활동으로인한현금흐름':'operating_cash_flow','영업활동현금흐름':'operating_cash_flow',
      '투자활동으로인한현금흐름':'investing_cash_flow','재무활동으로인한현금흐름':'financing_cash_flow',
      '기본주당순이익':'eps','기본주당이익':'eps'
    }
    return aliases.get(n)

def extract_major(rows):
    result={}
    for r in rows:
        key=normalize_account(r.get('account_nm',''))
        if not key: continue
        # DART API has thstrm_amount / thstrm_add_amount etc.
        val=parse_num(r.get('thstrm_amount'))
        if val is None: val=parse_num(r.get('thstrm_add_amount'))
        if val is None: continue
        result[key]=val
    return result

def build_record(year, typ, filing, raw_rows=None):
    rec={'year':year,'period':typ,'report_name':REPORT_NAMES.get(filing.get('reprt_code'),filing.get('report_nm','')),
         'rcept_no':filing.get('rcept_no'),'rcept_dt':filing.get('rcept_dt'),
         'dart_url':f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={filing.get('rcept_no')}",
         'source':'OpenDART'}
    if raw_rows is not None:
        rec['major']=raw_rows
    else:
        rec['major']=extract_major(raw_rows or [])
    m=rec['major']
    a=m.get('total_assets'); l=m.get('total_liabilities'); e=m.get('total_equity'); rev=m.get('revenue'); op=m.get('operating_income'); ni=m.get('net_income')
    def div(x,y): return None if x is None or y in (None,0) else x/y
    rec['ratios']={
      'operating_margin':div(op,rev),'net_margin':div(ni,rev),'roe':div(ni,e),'roa':div(ni,a),
      'debt_ratio':div(l,e),'equity_ratio':div(e,a),'current_ratio':None,'asset_turnover':div(rev,a)
    }
    return rec

def collect():
    DATA.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True)
    all_records=[]; filings_index=[]
    for year in range(START_YEAR, END_YEAR+1):
        try: filings=relevant_filings(year)
        except Exception as ex:
            print(f'[WARN] filings {year}: {ex}'); continue
        for f in filings:
            typ=f['report_type']; code=REPORT_CODES[typ]
            filing=dict(f, reprt_code=code)
            filings_index.append(filing)
            if year>=2015:
                try:
                    rows=fetch_financials_2015_plus(year,code)
                    rec=build_record(year,typ,filing,rows)
                    all_records.append(rec)
                except Exception as ex: print(f'[WARN] financials {year} {typ}: {ex}')
            else:
                try:
                    blob=download_original(f['rcept_no'])
                    candidates=parse_legacy_zip(blob)
                    # Preserve candidates for manual/audit mapping rather than inventing values.
                    rec=build_record(year,typ,filing,{})
                    rec['source']='DART original filing (legacy parser)'
                    rec['legacy_candidates']=candidates[:500]
                    all_records.append(rec)
                    if SAVE_RAW:
                        p=REPORTS/str(year)/f"{typ}_{f['rcept_no']}.zip"; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(blob)
                except Exception as ex: print(f'[WARN] legacy {year} {typ}: {ex}')
            if SAVE_RAW and year>=2015:
                try:
                    blob=download_original(f['rcept_no'])
                    p=REPORTS/str(year)/f"{typ}_{f['rcept_no']}.zip"; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(blob)
                except Exception as ex: print(f'[WARN] raw {year} {typ}: {ex}')
        time.sleep(0.2)
    save_json(DATA/'financials.json',all_records)
    save_json(DATA/'filings.json',filings_index)
    write_csv(all_records)
    return all_records

def write_csv(records):
    fields=['year','period','report_name','rcept_dt','dart_url','revenue','operating_income','net_income','total_assets','total_liabilities','total_equity','cash_and_equivalents','operating_cash_flow','investing_cash_flow','financing_cash_flow','eps','operating_margin','net_margin','roe','roa','debt_ratio','equity_ratio','asset_turnover']
    with (DATA/'financials.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in records:
            row={k:r.get(k) for k in fields}; row.update(r.get('major',{})); row.update(r.get('ratios',{})); w.writerow(row)

def main():
    if not API_KEY: print('ERROR: GitHub Secret OPENDART_API_KEY가 필요합니다.',file=sys.stderr); sys.exit(2)
    records=collect()
    save_json(DATA/'last_update.json',{'updated_at':datetime.now().astimezone().isoformat(),'record_count':len(records),'start_year':START_YEAR,'end_year':END_YEAR})
    print(f'Collected {len(records)} records')

if __name__=='__main__': main()
