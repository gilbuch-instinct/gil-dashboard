import json,urllib.request,urllib.parse,datetime,time,concurrent.futures,os
from zoneinfo import ZoneInfo
R=os.path.dirname(os.path.abspath(__file__)); now=datetime.datetime.now(ZoneInfo('Asia/Jerusalem')); UA={'User-Agent':'Mozilla/5.0'}
def load(f):return json.load(open(R+'/'+f))
def write(f,d):
 with open(R+'/'+f,'w') as h:json.dump(d,h,ensure_ascii=False,separators=(',',':'));h.write('\n')
def chart(sym,rng,interval,pre=False):
 path=urllib.parse.quote(sym,safe=''); q=urllib.parse.urlencode({'range':rng,'interval':interval,'includePrePost':str(pre).lower()})
 for host in ('query1','query2'):
  try:
   req=urllib.request.Request(f'https://{host}.finance.yahoo.com/v8/finance/chart/{path}?{q}',headers=UA)
   with urllib.request.urlopen(req,timeout=12) as resp:return json.load(resp)['chart']['result'][0]
  except Exception:time.sleep(.3)
 raise RuntimeError(f'{sym} {rng} {interval}: two chart hosts failed')
H=load('3-history.json'); I=load('5-intraday.json'); D=load('data.json'); F=load('4-fundamentals.json')
# Reviewed, source-linked news entries live in a small file so the large snapshot need not be edited in the browser.
extra=load('market_updates.json') if os.path.exists(R+'/market_updates.json') else []
assert isinstance(extra,list) and all(isinstance(x,dict) and all(k in x for k in ('title','body','source_url','date')) for x in extra)
updates=D.setdefault('updates',[])
for incoming in extra:
 title=incoming['title']
 matches=[x for x in updates if x.get('title')==title]
 if matches:
  for current in matches:
   current['body']=incoming['body']
   for key in list(current):
    if key=='source_name' or key.startswith('source_url'):current.pop(key)
   for key,value in incoming.items():
    if key=='source_name' or key.startswith('source_url'):current[key]=value
 else:
  updates.insert(0,incoming)

maphist={'NASDAQ:CIFR':'CIFR','NASDAQ:IREN':'IREN','NYSE:CLS':'CLS','NASDAQ:ACMR':'ACMR','NASDAQ:META':'META','NASDAQ:ADEA':'ADEA','TASE:ENLT':'ENLT.TA','SP:SPX':'^GSPC','NASDAQ:NDX':'^NDX','DJ:DJI':'^DJI','TVC:GOLD':'GC=F','TVC:USOIL':'CL=F','TVC:US10Y':'^TNX','COINBASE:BTCUSD':'BTC-USD','TASE:TA35':'TA35.TA','TASE:TA125':'^TA125.TA','TVC:US30Y':'^TYX','NYSE:NVO':'NVO','AMEX:XLF':'XLF'}
assert set(I['series'])==set(maphist)
# Snapshot quotes come from the CNBC quote webservice - the same source the page's live mode uses.
# Yahoo chart meta served hours-stale regularMarketPrice values under a fresh fetch-time label (2026-10-30: CIFR 7.02/CLS 256.05 shown after the close while CNBC had the verified closes 7.29/265.53).
cnbc={'SPX':'.SPX','NDX':'.NDX','DJI':'.DJI','CIFR':'CIFR','IREN':'IREN','CLS':'CLS','ACMR':'ACMR','META':'META','ADEA':'ADEA','GOLD':'@GC.1','WTI':'@CL.1','BRENT':'@LCO.1','US10Y':'US10Y','US30Y':'US30Y','BTC':'BTC=','PWR':'PWR','NVO':'NVO','XLF':'XLF'}
sector=list(D['sector_quotes']);jobs={}
tase_yahoo={'TA125':'^TA125.TA','TA35':'TA35.TA','ENLT':'ENLT.TA'}
for k,s in tase_yahoo.items():jobs[('q',k,'5d')]=(s,'5d','1d',False)
for k,s in maphist.items():
 for range_key,rng,interval in [('1d','1d','5m'),('1w','5d','15m')]:jobs[('i',k,range_key)]=(s,rng,interval,True)
 for range_key,rng,interval in [('6m','6mo','1d'),('1y','1y','1d'),('5y','5y','1wk'),('max','max','1wk')]:jobs[('h',k,range_key)]=(s,rng,interval,False)
# repeated symbol+range calls share one result
unique={v for v in jobs.values()}; results={};errors={}
def run(v):return v,chart(*v)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 for fut in concurrent.futures.as_completed([ex.submit(run,v) for v in unique]):
  try:v,z=fut.result();results[v]=z
  except Exception as e:errors[str(e)]=1
print('charts',len(results),'/',len(unique),'errors',list(errors)[:12],flush=True)
def rows(z,history=False):
 q=z.get('indicators',{}).get('quote',[{}])[0];adj=z.get('indicators',{}).get('adjclose',[{}])[0].get('adjclose',[]) if history else []
 out=[]
 for ix,t in enumerate(z.get('timestamp') or []):
  c=(adj[ix] if ix<len(adj) else None) or (q.get('close') or [])[ix]
  if c is None:continue
  out.append([datetime.datetime.fromtimestamp(t,datetime.timezone.utc).astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d') if history else t,round(c,4), (q.get('volume') or [0]*len(z['timestamp']))[ix] or 0])
 return out
for key,v in jobs.items():
 if v not in results:continue
 typ,k,r=key;z=results[v]
 if typ=='q':
  # TASE quotes stay on Yahoo daily bars: CNBC's TASE index feed returned the session open as "last" (verified 2026-10-30 against Yahoo/Investing/TV10).
  q0=z.get('indicators',{}).get('quote',[{}])[0]
  bars=[c for c in (q0.get('close') or []) if c is not None]
  if not bars:continue
  px=bars[-1];prev=bars[-2] if len(bars)>1 else None
  t=z.get('meta',{}).get('regularMarketTime')
  d=D['quotes'][k]
  if isinstance(t,(int,float)) and isinstance(d.get('t'),(int,float)) and t<d['t']:
   print('yahoo:',k,'served data older than stored, keeping stored quote');continue
  if k=='ENLT' and px<1000:px*=100;prev=prev*100 if prev else prev
  d['px']=round(px,4)
  if prev:d['ch']=round(100*(px/prev-1),3)
  if isinstance(t,(int,float)):
   d['t']=int(t);d['tstr']=datetime.datetime.fromtimestamp(int(t),datetime.timezone.utc).astimezone(ZoneInfo('Asia/Jerusalem')).strftime('%H:%M')
 elif typ in 'ih':
  out=rows(z,typ=='h')
  if typ=='h' and not out:continue
  (I if typ=='i' else H)['series'][k]['ranges'][r]['rows']=out
# --- CNBC snapshot quotes (regular-session last; extended hours never mixed in) ---
def cnum(s):
 if isinstance(s,bool):return None
 if isinstance(s,(int,float)):return float(s)
 if s is None:return None
 s=str(s).replace(',','').replace('%','').strip()
 try:return float(s)
 except ValueError:return None
def ctime(s):
 try:return int(datetime.datetime.strptime(str(s),'%Y-%m-%dT%H:%M:%S.%f%z').timestamp())
 except Exception:return None
def cnbc_fetch(codes):
 url='https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols='+urllib.parse.quote('|'.join(sorted(set(codes))),safe='')+'&exthrs=1&output=json'
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers=UA)
   with urllib.request.urlopen(req,timeout=15) as resp:
    arr=(json.load(resp).get('FormattedQuoteResult') or {}).get('FormattedQuote') or []
   return {q.get('symbol'):q for q in arr}
  except Exception as e:print('cnbc fetch attempt',attempt+1,'failed:',e);time.sleep(1)
 return {}
fresh=cnbc_fetch(list(cnbc.values())+sector)
def apply_cnbc(store,mapping):
 for key,code in mapping.items():
  q=fresh.get(code)
  if not q or str(q.get('code'))!='0':print('cnbc:',key,'missing at source, keeping previous quote');continue
  px=cnum(q.get('last'))
  if px is None or px<=0:print('cnbc:',key,'invalid last price, keeping previous quote');continue
  ch=cnum(q.get('change_pct'))
  if ch is None:
   prev=cnum(q.get('previous_day_closing'))
   if prev:ch=100*(px/prev-1)
  t=ctime(q.get('last_time'))
  d=store[key]
  if t is not None and isinstance(d.get('t'),(int,float)) and t<d['t']:
   # Source served data older than what we already stored: never regress to a staler value.
   print('cnbc:',key,'served data older than stored, keeping stored quote');continue
  d['px']=round(px,4)
  if ch is not None:d['ch']=round(ch,3)
  if t is not None:
   d['t']=t;d['tstr']=datetime.datetime.fromtimestamp(t,datetime.timezone.utc).astimezone(ZoneInfo('Asia/Jerusalem')).strftime('%H:%M')
apply_cnbc(D['quotes'],cnbc)
apply_cnbc(D['sector_quotes'],{k:k for k in sector})
# Freshness is judged per session group against the freshest peer at the source, never against fetch time.
# Indices keep ticking ~30-50 min after the equity close, so stocks and indices are judged separately.
US_STOCKS=['CIFR','IREN','CLS','ACMR','META','ADEA','PWR','NVO','XLF']
US_INDEX=['SPX','NDX','DJI']
US_GROUP=US_STOCKS+US_INDEX
TA_GROUP=['TA125','TA35','ENLT']
def flag_stale(store,keys):
 ts=[store[k]['t'] for k in keys if isinstance(store.get(k,{}).get('t'),(int,float))]
 if not ts:return
 mt=max(ts)
 for k in keys:
  q=store.get(k,{})
  if not isinstance(q.get('t'),(int,float)):continue
  if mt-q['t']>2700:q['stale']=True
  else:q.pop('stale',None)
flag_stale(D['quotes'],US_STOCKS)
flag_stale(D['quotes'],US_INDEX)
flag_stale(D['quotes'],TA_GROUP)
flag_stale(D['sector_quotes'],sector)
us_t=[D['quotes'][k]['t'] for k in US_GROUP if isinstance(D['quotes'].get(k,{}).get('t'),(int,float))]
if us_t:
 am=datetime.datetime.fromtimestamp(max(us_t),datetime.timezone.utc).astimezone(ZoneInfo('Asia/Jerusalem'))
 D['quotes_data_asof']=f'{am.day}.{am.month} · {am:%H:%M} · CNBC'
# Israeli end-of-day series (Bizportal yearly graph). Exact series: INFRA=IBI index 2126, ELEC=fund 5143078, KSM125K=security 1155365, TAINFRA=TASE index 206 (paper 784). d comes from the returned row's own date, never a calendar assumption. A bad row (invalid or non-finite values, future date, date older than the stored one) leaves the whole previous quote untouched.
import http.cookiejar,math
def prev_date(d):
 try:
  dd,mm=[int(x) for x in d.split('.')];y=now.year
  while True:
   try:r=datetime.date(y,mm,dd)
   except ValueError:return None
   if r<=now.date():return r
   y-=1
 except Exception:return None
def bizportal_eod(ids):
 op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));out={}
 try:op.open(urllib.request.Request('https://www.bizportal.co.il/capitalmarket/quote/generalpage/2126',headers=UA),timeout=20).read()
 except Exception as e:print('bizportal prime failed',e)
 for k,pid in ids.items():
  try:
   u=f'https://www.bizportal.co.il/ajax/biz_papers_helper.ashx?action=get_paper_yearly_graph&request_type=2&paper_id={pid}&period=6&page_number=0'
   r=op.open(urllib.request.Request(u,headers={**UA,'X-Requested-With':'XMLHttpRequest'}),timeout=20).read().decode()
   rows=json.loads(r[r.index('^')+1:]);last=max(rows,key=lambda x:x['DateObj'])
   ds=str(last['DateObj']);day=datetime.date(int(ds[:4]),int(ds[4:6]),int(ds[6:]))
   px,chg=last['Rate'],last['ChangeInPercent']
   for v in (px,chg):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('non-numeric value')
   if px<=0:raise ValueError('non-positive price')
   if day>now.date():raise ValueError('future date')
   old=prev_date(D['quotes'][k].get('d',''))
   if old and day<old:raise ValueError('source date regressed')
   out[k]=(px,chg,f'{day.day}.{day.month}')
  except Exception as e:print('bizportal',k,'failed, keeping previous quote:',e)
 return out
for k,(px,chg,dd) in bizportal_eod({'INFRA':2126,'ELEC':5143078,'KSM125K':1155365,'TAINFRA':784}).items():
 D['quotes'][k].update({'px':px,'ch':chg,'d':dd})
for t in D['theses']:
 q=D['quotes'].get(t.get('quote_id'))
 if q and isinstance(q.get('px'),(int,float)):
  t['current_price_snapshot']=q['px'];t['mock_return_pct']=round((q['px']/t['entry_price']-1)*100,2)
he=f'{now.day} ב{["ינואר","פברואר","מרץ","אפריל","מאי","יוני","יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"][now.month-1]} {now.year}, {now:%H:%M} שעון ישראל'
D['updated_he']=he;D['quotes_updated']=f'{now.day}.{now.month} · {now:%H:%M}';D['sector_quotes_updated']=D['quotes_updated']
for v in (H,I):v['updated']=now.isoformat();v['updated_he']=he
write('data.json',D);write('3-history.json',H);write('5-intraday.json',I)
# No fundamental restamp: retain last complete snapshot until all peer statistics can be verified.
