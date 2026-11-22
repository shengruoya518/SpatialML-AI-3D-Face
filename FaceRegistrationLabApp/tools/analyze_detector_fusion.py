"""Compare fixed-shape detector math with the exact shipped JS decode/ROI logic.

This is an executable fusion feasibility study, not a deployed accelerator model.
It includes finite-value behavior, stable best-rank selection, weighted suppression,
identity lock, both resize contracts, and no-face defaults.
"""
import argparse
import json
from pathlib import Path
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/operators/decode_detection.js'


def tensor_decode(t):
    width,height=t['settings'][:2];letterbox=t['settings'][9]>0
    sx=256/max(width,height) if letterbox else 256/width;sy=sx if letterbox else 256/height
    px=(256-width*sx)/2;py=(256-height*sy)/2
    scores=np.r_[t['scoresFine'],t['scoresCoarse']].astype(float)
    finite=np.isfinite(scores);anchor=int(np.argmax(np.where(finite,scores,-np.inf))) if finite.any() else -1
    best_raw=float(scores[anchor]) if anchor>=0 else 0
    info=[best_raw,1/(1+np.exp(-np.clip(best_raw,-100,100))) if anchor>=0 else 0,anchor]
    boxes=np.vstack([np.array(t['boxesFine']).reshape(512,16),np.array(t['boxesCoarse']).reshape(384,16)])
    cell_f=np.arange(512)//2;cell_c=np.arange(384)//6
    ax=np.r_[(cell_f%16+.5)*16,(cell_c%8+.5)*32];ay=np.r_[(cell_f//16+.5)*16,(cell_c//8+.5)*32]
    score=1/(1+np.exp(-np.clip(scores,-100,100)))
    decoded=np.empty_like(boxes)
    cx=boxes[:,0]+ax;cy=boxes[:,1]+ay;w=boxes[:,2];h=boxes[:,3]
    decoded[:,:4]=np.stack([cx-w/2,cy-h/2,cx+w/2,cy+h/2],axis=1)
    decoded[:,4::2]=boxes[:,4::2]+ax[:,None];decoded[:,5::2]=boxes[:,5::2]+ay[:,None]
    valid=np.isfinite(score)&(score>=t['settings'][2])&(w>0)&(h>0)&np.isfinite(decoded).all(axis=1)
    timestamp=t['timestamp'];now=timestamp[0]*4294967296+timestamp[1]+(timestamp[2]*4294967296+timestamp[3])*1e-9
    state=t['trackState'];age=now-state[1]-state[2];locked=state[11]>0 and age>=0 and age<t['settings'][10]
    distance=np.hypot((cx-px)/sx-state[3],(cy-py)/sy-state[4])/max(32,state[5]) if locked else np.zeros(896)
    valid &= (distance<=.8) if locked else True
    rank=np.where(valid,score-.35*distance,-np.inf)
    side=min(width,height);outcx=width/2;outcy=height/2;angle=0;present=0;bestscore=0
    if valid.any():
        best=int(np.argmax(rank));a=decoded[best]
        overlap=np.maximum(0,np.minimum(a[2],decoded[:,2])-np.maximum(a[0],decoded[:,0]))*np.maximum(0,np.minimum(a[3],decoded[:,3])-np.maximum(a[1],decoded[:,1]))
        union=(a[2]-a[0])*(a[3]-a[1])+(decoded[:,2]-decoded[:,0])*(decoded[:,3]-decoded[:,1])-overlap
        with np.errstate(divide='ignore',invalid='ignore'):same=valid & ((overlap/union)>.3)
        same[best]=True
        weights=np.where(same,score,0);total=np.sum(weights)
        # Invalid candidates must be sanitized before multiplication: NaN*0 is still NaN.
        weighted=np.sum(np.where(same[:,None],decoded,0)*weights[:,None],axis=0)/total
        outcx=((weighted[0]+weighted[2])/2-px)/sx;outcy=((weighted[1]+weighted[3])/2-py)/sy
        side=1.5*max((weighted[2]-weighted[0])/sx,(weighted[3]-weighted[1])/sy)
        angle=np.arctan2((weighted[7]-weighted[5])/sy,(weighted[6]-weighted[4])/sx);present=1;bestscore=score[best]
    a=256*np.cos(angle)/side;b=256*np.sin(angle)/side
    return {'roi':[present,bestscore,outcx,outcy,side,angle], 'affine':[a,b,128-a*outcx-b*outcy,-b,a,128+b*outcx-a*outcy],'detectorInfo':info}


def validate(output):
    rng=np.random.default_rng(944);cases=[]
    for letterbox in [0,1]:
      for active in [False,True]:
       for variant in range(10):
        settings=[3248,2464,.25,.5,1,.35,.45,.1,.25,letterbox,.75]
        state=[0]*24;state[1]=100;state[2]=.1;state[3]=1624;state[4]=1232;state[5]=800;state[11]=1 if active else 0
        boxes=rng.normal(0,20,(896,16));boxes[:,2:4]=rng.uniform(5,60,(896,2));scores=np.full(896,-100.)
        if variant:
            ids=rng.choice(896,10+variant*3,replace=False);scores[ids]=rng.normal(1,2,len(ids))
        if variant==2:scores[[0,1]]=2;boxes[1]=boxes[0]
        if variant==3:scores[2]=np.inf;scores[3]=np.nan;boxes[4,0]=np.nan;scores[4]=10
        if variant==4:boxes[:,2]=-5
        if variant==5:scores[32:35]=9;boxes[32:35,2:4]=50
        if variant==6:state[1]=80
        t={'boxesFine':boxes[:512].ravel().tolist(),'boxesCoarse':boxes[512:].ravel().tolist(),'scoresFine':scores[:512].tolist(),'scoresCoarse':scores[512:].tolist(),'settings':settings,'trackState':state,'timestamp':[0,100,0,150000000],'roi':[0]*6,'affine':[0]*6,'detectorInfo':[0]*3}
        cases.append(t)
    requests=[]
    for t in cases:
        def convert(v):return 'NaN' if np.isnan(v) else 'Infinity' if v==np.inf else '-Infinity' if v==-np.inf else v
        clean={k:[convert(v) for v in values] for k,values in t.items()}
        requests.append(json.dumps({'script':str(SCRIPT),'tensors':clean}))
    p=subprocess.run(['node',str(ROOT/'FaceLandmarkerApp/tools/run_operator.mjs')],input='\n'.join(requests)+'\n',capture_output=True,text=True,check=True)
    observed=[json.loads(line) for line in p.stdout.splitlines()];errors=[]
    for i,(t,got) in enumerate(zip(cases,observed)):
        assert 'error' not in got,got
        reference=got['tensors'];candidate=tensor_decode(t)
        for name in ['roi','affine','detectorInfo']:
            np.testing.assert_allclose(candidate[name],reference[name],atol=1e-8,rtol=1e-10)
            errors.append(float(np.max(np.abs(np.array(candidate[name])-reference[name]))))
    out={'cases':len(cases),'productionJsComparison':'PASS','maximumAbsDifference':max(errors),'covered':['no face','multi-candidate weighted suppression','stable equal-score winner','NaN/Inf scores/boxes','invalid width','active identity lock','expired identity lock','letterboxed and stretched detector coordinates'],'boundary':'Double-precision tensor algorithm feasibility only. GPU/NPU float32, finite tests, argmax/gather/reduce partitioning and state/timestamp precision are not validated.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    validate(p.parse_args().output)
