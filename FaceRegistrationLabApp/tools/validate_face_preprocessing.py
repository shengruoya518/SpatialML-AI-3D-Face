"""Execute the serialized model math and compare OpenCV crop/normalization contracts.

This reference evaluator implements the GPU Resampler's zero-border bilinear math.
It is not proof of device delegation, floating-point precision or service timings.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import tflite

NAMES={v:k for k,v in vars(tflite.BuiltinOperator).items() if isinstance(v,int)}
DTYPES={tflite.TensorType.FLOAT32:'<f4',tflite.TensorType.INT32:'<i4',tflite.TensorType.UINT8:'u1'}


def execute(path,image,affine):
    model=tflite.Model.GetRootAsModel(path.read_bytes(),0);graph=model.Subgraphs(0);values={}
    for i in range(graph.TensorsLength()):
        t=graph.Tensors(i);buf=model.Buffers(t.Buffer());shape=tuple(t.ShapeAsNumpy())
        if buf.DataLength():values[i]=np.frombuffer(buf.DataAsNumpy().tobytes(),dtype=DTYPES[t.Type()]).reshape(shape)
    values[int(graph.Inputs(0))]=image[None].astype(DTYPES[graph.Tensors(int(graph.Inputs(0))).Type()])
    values[int(graph.Inputs(1))]=np.asarray(affine,dtype=np.float32).reshape(1,1,1,6)
    for i in range(graph.OperatorsLength()):
        op=graph.Operators(i);code=model.OperatorCodes(op.OpcodeIndex());name=NAMES[code.BuiltinCode()];args=[values[int(k)] for k in op.InputsAsNumpy()]
        if name=='CAST':out=args[0].astype(np.float32)
        elif name=='SLICE':out=args[0][tuple(slice(int(b),int(b)+int(s)) for b,s in zip(args[1],args[2]))]
        elif name=='ADD':out=args[0]+args[1]
        elif name=='SUB':out=args[0]-args[1]
        elif name=='MUL':out=args[0]*args[1]
        elif name=='DIV':out=args[0]/args[1]
        elif name=='FLOOR':out=np.floor(args[0])
        elif name=='CONCATENATION':out=np.concatenate(args,axis=3)
        elif name=='CUSTOM' and code.CustomCode()==b'Resampler':
            source,xy=args;source=source[0];xy=xy[0];h,w=source.shape[:2]
            x0=np.floor(xy[...,0]).astype(int);y0=np.floor(xy[...,1]).astype(int)
            dx=(xy[...,0]-x0).astype(np.float32)[...,None];dy=(xy[...,1]-y0).astype(np.float32)[...,None]
            def read(x,y):
                valid=((x>=0)&(x<w)&(y>=0)&(y<h))[...,None]
                return np.where(valid,source[np.clip(y,0,h-1),np.clip(x,0,w-1)],np.float32(0))
            top=read(x0,y0)*(1-dx)+read(x0+1,y0)*dx
            bottom=read(x0,y0+1)*(1-dx)+read(x0+1,y0+1)*dx
            out=(top*(1-dy)+bottom*dy)[None]
        else:raise AssertionError('Unexpected operator '+name)
        out=np.asarray(out,dtype=np.float32);index=int(op.Outputs(0));expected=tuple(graph.Tensors(index).ShapeAsNumpy())
        assert out.shape==expected,(name,out.shape,expected)
        assert np.isfinite(out).all(),name
        values[index]=out
    return {graph.Tensors(int(graph.Outputs(i))).Name().decode():values[int(graph.Outputs(i))][0] for i in range(graph.OutputsLength())}


def validate(folder,output,sample_bytes=False,tile=False):
    size=256
    h=w=768 if tile else 0
    if not tile:h,w=2464,3248
    rng=np.random.default_rng(8128)
    # Different RGB channels expose unintended channel permutation; noise exposes sampling shifts.
    yy,xx=np.indices((h,w));gradient=np.stack([(xx%256),(yy%256),((xx//13+yy//17)%256)],axis=-1).astype(np.uint8)
    noise=rng.integers(0,256,(h,w,3),dtype=np.uint8)
    cases=[]
    if not tile:
        for sx,tx in [(1,0),(.7673501372337341,377.70703125)]:
            scale=256/w;a=np.array([[scale*sx,0,scale*tx],[0,scale,(256-scale*h)/2]],dtype=np.float32)
            cases.append(('detector',a))
    tile_cases=[(0,384,384,700),(.3,384,384,700),(-.6,260,300,500),(1.0,500,450,600),(-1.2,350,420,740)]
    full_cases=[(0,1624,1232,700),(.3,1624,1232,900),(-.6,100,120,500),(1.0,3050,2300,600),(-1.2,1500,1400,1100)]
    for angle,cx,cy,side in tile_cases if tile else full_cases:
        a=256*np.cos(angle)/side;b=256*np.sin(angle)/side
        matrix=np.array([[a,b,128-a*cx-b*cy],[-b,a,128+b*cx-a*cy]],dtype=np.float32)
        transforms=[(1,0)] if tile else [(1,0),(.7673501372337341,377.70703125)]
        for sx,tx in transforms:
            transform=np.array([[sx,0,tx],[0,1,0],[0,0,1]],dtype=np.float32)
            cases.append(('landmark',matrix@transform))
    if tile:cases.append(('landmark',np.array([[1,0,0],[0,1,0]],dtype=np.float32)))
    results=[]
    for n,(kind,affine) in enumerate(cases):
        path=folder/('landmark_preprocess_tile_rgb_gpu.tflite' if tile else kind+('_preprocess_rgb_gpu.tflite' if sample_bytes else '_preprocess_gpu.tflite'))
        for label,image in [('rgb_gradient',gradient),('rgb_noise',noise)]:
            out=execute(path,image,affine);normal=out['model_input']
            crop=np.floor(normal*np.float32(255)+np.float32(.5))
            assert np.all(crop==np.floor(crop)) and crop.min()>=0 and crop.max()<=255
            np.testing.assert_array_equal(normal,crop/np.float32(255))
            reference=cv2.warpAffine(image,affine,(size,size),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
            diff=crop-reference.astype(np.float32)
            result={'case':n,'kind':kind,'image':label,'maximumByteError':float(np.abs(diff).max()),'rmsByteError':float(np.sqrt(np.mean(diff*diff))),'differentValues':int(np.count_nonzero(diff)),'values':diff.size}
            # OpenCV and delegated sampling need not be bit-identical. This bound detects a
            # displaced crop, channel swap or normalization error in the host math reference;
            # device pixels and downstream landmark accuracy still need separate checks.
            assert result['maximumByteError'] <= 8 and result['rmsByteError'] < .5, result
            results.append(result)
    manifest=json.loads((folder/('landmark_tile_preprocessing_rgb_model.json' if tile else ('preprocessing_rgb_models.json' if sample_bytes else 'preprocessing_models.json'))).read_text())
    for item in manifest:
        data=(folder/(item['name']+'.tflite')).read_bytes();assert hashlib.sha256(data).hexdigest()==item['sha256']
    report={'cases':results,'modelHashes':'PASS','normalizedMatchesExportCrop':'PASS','finiteBoundedIntegerCrop':'PASS','opencvVersion':cv2.__version__,'referenceErrorBound':f'maximum <=8 byte levels and RMS <0.5 on these {len(results)} synthetic cases','maximumByteError':max(r['maximumByteError'] for r in results),'boundary':'Serialized model math reference versus OpenCV. GPU FP32/FP16 and service execution remain unverified; small inverse-affine rounding differences are measured, not assumed away.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models',type=Path,default=Path(__file__).resolve().parents[2]/'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/model')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sample-bytes',action='store_true')
    p.add_argument('--tile',action='store_true')
    a=p.parse_args();validate(a.models,a.output,a.sample_bytes,a.tile)
