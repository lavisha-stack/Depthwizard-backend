#!/usr/bin/env python3
"""Convert a 2-D NumPy DSM into compact, browser-friendly JSON (NumPy only)."""
import argparse, json
from pathlib import Path
import numpy as np

def resize_bilinear(a, out_h, out_w):
    """Aspect-safe bilinear sampling implemented with NumPy; no SciPy dependency."""
    ys=np.linspace(0,a.shape[0]-1,out_h); xs=np.linspace(0,a.shape[1]-1,out_w)
    y0=np.floor(ys).astype(int); x0=np.floor(xs).astype(int); y1=np.minimum(y0+1,a.shape[0]-1); x1=np.minimum(x0+1,a.shape[1]-1)
    wy=(ys-y0)[:,None]; wx=(xs-x0)[None,:]
    return (a[y0[:,None],x0[None,:]]*(1-wy)*(1-wx)+a[y1[:,None],x0[None,:]]*wy*(1-wx)+a[y0[:,None],x1[None,:]]*(1-wy)*wx+a[y1[:,None],x1[None,:]]*wy*wx)

def fill_nan(a):
    if not np.isfinite(a).any(): raise ValueError('DSM has no finite values')
    out=a.copy(); fallback=float(np.nanmedian(np.where(np.isfinite(out),out,np.nan)))
    for _ in range(sum(out.shape)):
        missing=~np.isfinite(out)
        if not missing.any(): break
        sums=np.zeros_like(out); counts=np.zeros_like(out,dtype=np.uint8)
        valid=~missing
        sums[1:]+=np.where(valid[:-1],out[:-1],0); counts[1:]+=valid[:-1]
        sums[:-1]+=np.where(valid[1:],out[1:],0); counts[:-1]+=valid[1:]
        sums[:,1:]+=np.where(valid[:,:-1],out[:,:-1],0); counts[:,1:]+=valid[:,:-1]
        sums[:,:-1]+=np.where(valid[:,1:],out[:,1:],0); counts[:,:-1]+=valid[:,1:]
        can=missing&(counts>0); out[can]=sums[can]/counts[can]
    out[~np.isfinite(out)]=fallback
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');p.add_argument('output');p.add_argument('--max-size',type=int,default=512);p.add_argument('--decimals',type=int,default=3);p.add_argument('--units',default='metres');args=p.parse_args()
    if args.max_size < 2: raise ValueError('--max-size must be at least 2')
    if args.decimals < 0: raise ValueError('--decimals must be non-negative')
    a=np.asarray(np.load(args.input,allow_pickle=False),dtype=np.float64).squeeze()
    if a.ndim!=2: raise ValueError(f'Expected a 2-D DSM, got {a.shape}')
    valid=np.isfinite(a);a=fill_nan(a); scale=min(1,args.max_size/max(a.shape)); h=max(2,round(a.shape[0]*scale));w=max(2,round(a.shape[1]*scale));
    y=np.linspace(0,valid.shape[0]-1,h).round().astype(int);x=np.linspace(0,valid.shape[1]-1,w).round().astype(int);valid=valid[np.ix_(y,x)];a=resize_bilinear(a,h,w)
    payload={'width':w,'height':h,'elevation_min':round(float(a.min()),args.decimals),'elevation_max':round(float(a.max()),args.decimals),'heights':np.round(a,args.decimals).ravel().tolist(),'valid':valid.ravel().tolist(),'nodata':None,'units':args.units}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8');print(f'Wrote {w}x{h} ({w*h:,} samples) to {args.output}')
if __name__=='__main__': main()
