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
existing={x.get('title') for x in D.get('updates',[])}
D['updates']=[x for x in extra if x['title'] not in existing]+D['updates']

maphist={'NASDAQ:CIFR':'CIFR','NASDAQ:IREN':'IREN','NYSE:CLS':'CLS','NASDAQ:ACMR':'ACMR','NASDAQ:META':'META','NASDAQ:ADEA':'ADEA','TASE:ENLT':'ENLT.TA','SP:SPX':'^GSPC','NASDAQ:NDX':'^NDX','DJ:DJI':'^DJI','TVC:GOLD':'GC=F','TVC:USOIL':'CL=F','TVC:US10Y':'^TNX','COINBASE:BTCUSD':'BTC-USD','TASE:TA35':'TA35.TA','TASE:TA125':'^TA125.TA','TVC:US30Y':'^TYX','NYSE:NVO':'NVO','AMEX:XLF':'XLF'}
assert set(I['series'])==set(maphist)
qq={'SPX':'^GSPC','NDX':'^NDX','DJI':'^DJI','CIFR':'CIFR','IREN':'IREN','CLS':'CLS','ACMR':'ACMR','META':'META','ADEA':'ADEA','ENLT':'ENLT.TA','GOLD':'GC=F','WTI':'CL=F','BRENT':'BZ=F','US10Y':'^TNX','US30Y':'^TYX','BTC':'BTC-USD','TA125':'^TA125.TA','TA35':'TA35.TA','PWR':'PWR','NVO':'NVO','XLF':'XLF'}
sector=list(D['sector_quotes']);jobs={}
for k,s in maphist.items():
 for range_key,rng,interval in [('1d','1d','5m'),('1w','5d','15m')]:jobs[('i',k,range_key)]=(s,rng,interval,True)
 for range_key,rng,interval in [('6m','6mo','1d'),('1y','1y','1d'),('5y','5y','1wk'),('max','max','1wk')]:jobs[('h',k,range_key)]=(s,rng,interval,False)
for k,s in qq.items():jobs[('q',k,'1d')]=(s,'1d','1d',False)
for k in sector:jobs[('s',k,'1d')]=(k,'1d','1d',False)
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
 if typ in 'ih':
  out=rows(z,typ=='h')
  if typ=='h' and not out:continue
  (I if typ=='i' else H)['series'][k]['ranges'][r]['rows']=out
 elif typ in 'qs':
  meta=z.get('meta',{});px=meta.get('regularMarketPrice');prev=meta.get('chartPreviousClose') or meta.get('regularMarketPreviousClose') or meta.get('previousClose')
  if px is None:continue
  if typ=='q' and k=='ENLT' and px<1000:px*=100;prev=prev*100 if prev else prev
  d=(D['quotes'] if typ=='q' else D['sector_quotes'])[k];d['px']=round(px,4)
  if prev:d['ch']=round(100*(px/prev-1),3)
for t in D['theses']:
 q=D['quotes'].get(t.get('quote_id'))
 if q and isinstance(q.get('px'),(int,float)):
  t['current_price_snapshot']=q['px'];t['mock_return_pct']=round((q['px']/t['entry_price']-1)*100,2)
he=f'{now.day} ב{["ינואר","פברואר","מרץ","אפריל","מאי","יוני","יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"][now.month-1]} {now.year}, {now:%H:%M} שעון ישראל'
D['updated_he']=he;D['quotes_updated']=f'{now.day}.{now.month} · {now:%H:%M} · Yahoo Finance';D['sector_quotes_updated']=D['quotes_updated']
for v in (H,I):v['updated']=now.isoformat();v['updated_he']=he
write('data.json',D);write('3-history.json',H);write('5-intraday.json',I)
# No fundamental restamp: retain last complete snapshot until all peer statistics can be verified.
