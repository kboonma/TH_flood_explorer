import sys, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from datetime import date, timedelta
D=lambda s: date(*map(int,s.split('-')))
# per station: first x-axis date of each panel (read from the figure) and the table peak (date, Q)
CFG={
 'X.217':dict(f='fig54_severe_events_X217.png',panels={
  ('SSP2-4.5','2040s'):('2035-11-12','2035-12-10',1020.15),('SSP3-7.0','2040s'):('2046-11-13','2046-12-09',788.56),('SSP5-8.5','2040s'):('2050-10-25','2050-11-12',1151.85),
  ('SSP2-4.5','2060s'):('2065-10-19','2065-11-20',839.63),('SSP3-7.0','2060s'):('2064-11-11','2064-11-30',1108.17),('SSP5-8.5','2060s'):('2060-11-06','2060-12-04',937.15),
  ('SSP2-4.5','2080s'):('2083-12-20','2084-01-07',958.81),('SSP3-7.0','2080s'):('2080-11-23','2080-12-14',1169.24),('SSP5-8.5','2080s'):('2073-10-10','2073-11-11',1002.57)}),
 'X.36':dict(f='fig53_severe_events_X36.png',panels={
  ('SSP2-4.5','2040s'):('2047-09-06','2047-09-18',781.77),('SSP3-7.0','2040s'):('2035-08-20','2035-08-29',784.76),('SSP5-8.5','2040s'):('2039-07-23','2039-08-04',773.79),
  ('SSP2-4.5','2060s'):('2070-08-13','2070-08-21',838.28),('SSP3-7.0','2060s'):('2057-08-19','2057-09-08',974.07),('SSP5-8.5','2060s'):('2067-08-14','2067-08-24',871.38),
  ('SSP2-4.5','2080s'):('2086-09-09','2086-09-22',900.03),('SSP3-7.0','2080s'):('2073-09-19','2073-09-29',988.50),('SSP5-8.5','2080s'):('2084-08-06','2084-08-19',904.41)})}
COL={'SSP2-4.5':lambda a:(a[...,1]>140)&(a[...,0]<90)&(a[...,2]<140)&(a[...,1]-a[...,2]>40),
     'SSP3-7.0':lambda a:(a[...,2]>200)&(a[...,0]<100)&(a[...,1]<160),
     'SSP5-8.5':lambda a:(a[...,0]>200)&(a[...,1]<150)&(a[...,2]<150)&(a[...,0]-a[...,1]>80)}
src=sys.argv[1]; out={}
for st,cfg in CFG.items():
  a=np.asarray(Image.open(f"{src}/{cfg['f']}").convert('RGB')).astype(int); H,W,_=a.shape
  gray=a.mean(-1)
  for ssp,mk in COL.items():
    m=mk(a); lab,n=ndi.label(ndi.binary_dilation(m,iterations=3))
    sizes=ndi.sum(m,lab,range(1,n+1)); big=np.argsort(-sizes)[:3]+1
    comps=sorted(big,key=lambda k:ndi.find_objects((lab==k).astype(int))[0][0].start)   # top to bottom = 2040s,2060s,2080s
    for per,k in zip(['2040s','2060s','2080s'],comps):
      sl=ndi.find_objects((lab==k).astype(int))[0]; ys,xs=sl
      mm=m&(lab==k)
      cols=range(xs.start,xs.stop); yc={}
      for x in cols:
        r=np.where(mm[:,x])[0]
        if len(r): yc[x]=r.mean()
      xk=np.array(sorted(yc)); yk=np.array([yc[x] for x in xk])
      d0,dp,qp=CFG[st]['panels'][(ssp,per)]
      # x-axis line: first row below the curve where most pixels across the curve's span are dark/grey
      y0=None
      for y in range(int(yk.max())+2,min(H,int(yk.max())+600)):
        if (gray[y,xk.min():xk.max()]<215).mean()>0.85: y0=y;break
      ipk=yk.argmin(); xpk,ypk=xk[ipk],yk[ipk]
      ndays_pk=(D(dp)-D(d0)).days
      pxd=(xpk-xk[0])/ndays_pk
      n=int(round((xk[-1]-xk[0])/pxd))+1
      q=[]
      for i in range(n):
        x=xk[0]+i*pxd; y=np.interp(x,xk,yk)
        q.append(round(qp*(y0-y)/(y0-ypk),1))
      end=D(d0)+timedelta(days=n-1)
      out.setdefault(st,{})[f'{ssp}|{per}']=dict(start=d0,peak_date=dp,peak=qp,q=q)
      print(st,ssp,per,'y0',y0,'px/day %.2f'%pxd,'n',n,'end',end,'q0',q[0],'max',max(q),'argmax',(D(d0)+timedelta(days=int(np.argmax(q)))).isoformat())
json.dump(out,open('hydro_model.json','w'),separators=(',',':'))
