import time

import numpy as np
import matplotlib
import matplotlib.pyplot as pl

from localdate import parsedate,dumpdate,SearchName


def flattenoverlap(v,test=100,start=0):
  #Merge overlapping array of data. Expecting data in axis 1
  out=[v[0]]
  stat=[]
  print "Flatten: ...",
  for j in range(1,len(v)):
    v1=v[j-1]
    v2=v[j]
    for i in range(start,len(v2)-test):
      s=sum(v1[-test:]-v2[i:i+test])
      if s==0:
        break
    newi=i+test
    out.append(v2[newi:])
    if newi==0:
      print "Warning: no overlap for chunk %d,%d"%((j-1,j))
    stat.append(newi)
  print "average overlap %.2f samples"%np.average(stat)
  return np.hstack(out)


class rdmDateFormatter(matplotlib.ticker.Formatter):
  def __call__(self,x,pos=None):
    return dumpdate(x,fmt='%Y-%m-%d\n%H:%M:%S.SSS')

def set_xaxis_date(ax=None,bins=6):
  if ax is None:
    ax=pl.gca()
  ax.xaxis.set_major_formatter(rdmDateFormatter())
  ax.xaxis.major.locator._nbins=bins
  pl.draw()


def set_xlim_date(xa,xb):
  pl.xlim(parsedate(xa),parsedate(xb))

def get_xlim_date():
  xa,xb=pl.xlim()
  return dumpdate(xa),dumpdate(xb)


def int2keyword(n):
    n=int(n)
    s = (n==0) and "a" or ""
    while n!=0:
        s = chr(n % 26 +97) + s
        n = n / 26
    return s

def subdict(d,names):
  return dict([(k,d[k]) for k in names if k in d])

#from objdebug import ObjDebug as object
class DataQuery(SearchName,object):
  def __init__(self,source,names,t1,t2,data,**options):
    self.source=source
    self.names=names
    self.t1=t1
    self.t2=t2
    self.options=options
    self.data=data
    self._setshortcuts()
    self._emptycache()
  def _emptycache(self):
    self._cachedflatten={}
  def _getcache(self,names):
    return [subdict(self._cachedflatten,names)]
  def _setcache(self,lst):
    self._cachedflatten,=lst
  def _setshortcuts(self):
    if self.data:
      for i,name in  enumerate(self.names):
        s=int2keyword(i)
        idx,val=self.data[name]
        setattr(self,s+'0',idx)
        setattr(self,s+'1',val)
  def __repr__(self):
    out=[]
    out.append("DataQuery %s"%str(self.source))
    out.append("  '%s' <--> '%s'" % (dumpdate(self.t1),dumpdate(self.t2)))
    for i,name in enumerate(self.names):
      idx,val=self.data[name]
      typ="  %s: %s%s"%(int2keyword(i),name,val.shape)
      if len(idx)>0:
        typ+=" <%gs|%gs>"%(idx[0]-self.t1,self.t2-idx[-1])
      out.append(typ)
    return '\n'.join(out)
  def get_names(self):
    return self.names
  def reload(self,t1=None,t2=None):
    """reload data"""
    if t1 is None:
      t1=self.t1
    if t2 is None:
      t2=self.t2
    dq=self.source.get(self.names,t1,t2,**self.options)
    self.data=dq.data
    return self
  def trim(self,strict=False):
    """trim t1 and t2 such that all data is contained in [t1,t2]
       if strict is True all data is strictly contained
    """
    t1,t2=[],[]
    for name in self.names:
      idx,val=self.data[name]
      t1.append(idx[0])
      t2.append(idx[-1])
    if strict:
      self.t1=max(t1)
      self.t2=min(t2)
    else:
      self.t1=min(t1)
      self.t2=max(t2)
    return self
  def append(self,t1,t2):
    dq=self.source.get(self.names,t1,t2,**self.options)
    for name in self.names:
      idx,val=self.data[name]
      nidx,nval=dq.data[name]
      ridx=np.concatenate([idx,nidx],axis=0)
      rval=np.concatenate([val,nval],axis=0)
      self.data[name]=ridx,rval
  def extend(self,before=None,after=None,absolute=False,eps=1e-6):
    """Extend dataset by <before> sec and <after> secs"""
    if after is not None:
      if type(after) is str or absolute is True:
        after=parsedate(after)-self.t2
      if after<0:
        self.t2+=after
        for name in self.names:
          idx,val=self.data[name]
          mask=idx<(self.t2)
          self.data[name]=idx[mask],val[mask]
      else:
        dq=self.source.get(self.names,self.t2,self.t2+after,**self.options)
        self.t2+=after
        for name in self.names:
          idx,val=self.data[name]
          nidx,nval=dq.data[name]
          ridx=np.concatenate([idx,nidx],axis=0)
          rval=np.concatenate([val,nval],axis=0)
          self.data[name]=ridx,rval
    if before is not None:
      if type(before) is str or absolute is True:
        before=self.t1-parsedate(before)
      if before<0:
        self.t1-=before
        for name in self.names:
          idx,val=self.data[name]
          mask=idx>(self.t1)
          self.data[name]=idx[mask],val[mask]
      else:
        dq=self.source.get(self.names,self.t1-before,self.t1-eps,
                           **self.options)
        self.t1-=before
        for name in self.names:
          idx,val=self.data[name]
          nidx,nval=dq.data[name]
          ridx=np.concatenate([nidx,idx],axis=0)
          rval=np.concatenate([nval,val],axis=0)
          self.data[name]=ridx,rval
    self._emptycache()
    return self
  def add_sets(self,names):
    """Query for more names in the same interval"""
    dq=self.source.get(names,self.t1,self.t2,**self.options)
    for name in names:
      self.data[name]=dq.data[name]
      self.names.append(name)
    self._setshortcuts()
    return self
  def add_ext_set(self,name,tvec,vec):
    """Add data set from an external source"""
    self.data[name]=(tvec,vec)
    self.names.append(name)
    self._setshortcuts()
    return self
  def del_sets(self,names):
    """Delete names in the same interval"""
    names=self._parsenames(names)
    for name in names:
      del self.data[name]
      self.names.remove(name)
    self._setshortcuts()
    return self
  def sub(self,names):
    """Return a sub set of the object"""
    names=self._parsenames(names)
    newdata={}
    for name in names:
      newdata[name]=self.data[name]
    dq=DataQuery(self.source,names,self.t1,self.t2,newdata,**self.options)
    dq._setcache(self._getcache(names))
    return dq
  def store(self,source):
    for name in self.names:
      idx,val=self.data[name]
      source.store(name,idx,val)
  def flatten(self,name):
    if name in self._cachedflatten:
      return self._cachedflatten[name]
    else:
      idx,val=self.data[name]
      val=flattenoverlap(val)
      self._cachedflatten[name]=val
      return val
  def interpolate(self,tnew):
    datanew={}
    for vn in self.names:
      t,v=self.data[vn]
      vnew=np.interp(tnew,t,v)
      datanew[vn]=tnew,vnew
    t1=tnew[0]
    t2=tnew[-1]
    dq=DataQuery(self.source,self.names,t1,t2,datanew,**self.options)
    return dq
  def copy(self,**argsn):
    """copy source including data"""
    dq=DataQuery(self.source,self.names,self.t1,self.t2,
                 self.data,**self.options)
    dq.__dict__.update(argsn)
    return dq
  def new(self,**argsn):
    """copy source and reloading data"""
    dq=self.copy(**argsn)
    dq.reload()
    return dq
  def plot_2d(self,vscale='auto',rel_time=False,date_axes=True):
    for i,name in enumerate(self.names):
      t,v=self.data[name]
      if rel_time==True:
        t=t-t[0]
      if vscale=='auto':
        vmax=np.max(abs(v))
        vexp=np.floor(np.log10(vmax))
        if abs(vexp)>50:
          lbl=name
          vvscale=1
        else:
          lbl='$10^{%d}$ %s'%(int(vexp),name)
          vvscale=10**-vexp
      elif float(vscale)==1.0:
        lbl=name
        vvscale=1
      else:
        lbl='$%g$ %s'%(vscale,name)
        vvscale=vscale
      pl.plot(t,v*vvscale,'-',label=lbl)
      if date_axes==True:
        set_xaxis_date()
      else:
        pl.xlabel("time [sec]")
      pl.legend(loc=0)
      pl.grid(True)
  subplotchoices={
    1:(1,1),2:(2,1),3:(3,1),
    4:(2,2),5:(2,3),6:(2,3),
    7:(3,3),8:(3,3),9:(3,3)}
  def plot_specgramflat(self,NFFT=1024,Fs=1,noverlap=0,fmt='%H:%M:%S',
                       realtime=False):
    row,col=self.subplotchoices[len(self.names)]
    for i,name in enumerate(self.names):
      pl.subplot(row,col,i+1)
      t,val=self.data[name]
      val=self.flatten(name)
      print "dq.flatten('%s')"%name
      im=pl.specgram(val,NFFT=NFFT,Fs=Fs,noverlap=noverlap)[-1]
      pl.title(name)
      if realtime:
        im.set_extent([t[0],t[0]+len(val)/float(Fs),0,float(Fs)/2])
      else:
        im.set_extent([t[0],t[-1],0,0.5])
      set_xaxis_date()
  def plot_specgramflat_simple(self,name,NFFT=1024,Fs=1,noverlap=0,
      fmt='%H:%M:%S', realtime=False):
    t,val=self.data[name]
    val=self.flatten(name)
    print "dq.flatten('%s')"%name
    im=pl.specgram(val,NFFT=NFFT,Fs=Fs,noverlap=noverlap)[-1]
    pl.title(name)
    if realtime:
      im.set_extent([t[0],t[0]+len(val)/float(Fs),0,float(Fs)/2])
    else:
      im.set_extent([t[0],t[-1],0,0.5])
    set_xaxis_date()









