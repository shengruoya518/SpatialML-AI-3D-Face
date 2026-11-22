"""Execute fused models with host CPU LiteRT and compare shipped JS at FP32 boundaries.

Native SVD is represented by NumPy SVD for both paths; this does not validate
installed SpatialML SVD, model transport, delegate selection or headset latency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import numpy as np
from ai_edge_litert.interpreter import Interpreter

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker'


def validate(output, inline_root=None, opencv_svd=False):
    output.mkdir(parents=True, exist_ok=True)
    geometry = json.loads((ASSETS / 'data/face_geometry.json').read_text())
    full = np.asarray(geometry['canonical'], np.float32).reshape(468, 4)
    indices = np.flatnonzero(full[:, 3] > 0)
    canonical = full[indices]
    models = {}
    for item in json.loads((ASSETS / 'model/face_fit_models.json').read_text()):
        path = ASSETS / 'model' / (item['name'] + '.tflite')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
        assert hashlib.sha256((ASSETS / 'data/face_geometry.json').read_bytes()).hexdigest() == item['canonicalAssetSha256']
        interpreter = Interpreter(model_path=str(path), num_threads=1)
        interpreter.allocate_tensors(); models[item['name']] = interpreter
    if inline_root:
        for name, path in [('face_fit_inline', inline_root/'models/face_fit_inline.tflite'),
                           ('inline_solve', inline_root/'probes/solve.tflite')]:
            interpreter = Interpreter(model_path=str(path), num_threads=1)
            interpreter.allocate_tensors(); models[name] = interpreter
    timings = {name: [] for name in models}
    def infer(name, **tensors):
        m = models[name]
        for d in m.get_input_details():
            m.set_tensor(d['index'], np.asarray(tensors[d['name']], np.float32).reshape(d['shape']))
        start = time.perf_counter(); m.invoke(); timings[name].append((time.perf_counter() - start) * 1000)
        return {d['name']: m.get_tensor(d['index']).flatten() for d in m.get_output_details()}

    node = subprocess.Popen(['node', str(ROOT / 'FaceLandmarkerApp/tools/run_operator.mjs')],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    def op(name, **tensors):
        node.stdin.write(json.dumps(dict(script=str(ASSETS / 'operators' / (name + '.js')),
                         tensors={k: np.asarray(v).flatten().tolist() for k, v in tensors.items()})) + '\n')
        node.stdin.flush(); r = json.loads(node.stdout.readline()); assert 'error' not in r, r
        return {k: np.asarray(v, np.float32) for k, v in r['tensors'].items()}

    def svd(covariance):
        if opencv_svd:
            import cv2
            _, u, vt = cv2.SVDecomp(covariance.reshape(3, 3))
        else:
            u, _, vt = np.linalg.svd(covariance.reshape(3, 3))
        return u.astype(np.float32), vt.astype(np.float32)

    def reference(first, projected, depth, validity):
        scales = []; targets = first; stages = []
        for step in range(3):
            cov = op('geometry_covariance', canonical=canonical, targets=targets, covariance=np.zeros(9), centers=np.zeros(6))
            u, vt = svd(cov['covariance'])
            fit = op('geometry_solve', canonical=canonical, targets=targets, centers=cov['centers'], u=u, vt=vt, pose=np.zeros(16), scale=[0])
            if step == 2: return dict(pose=fit['pose'], first_scale=scales[0], second_scale=scales[1], second_targets=stages[0], metric=stages[1])
            scales.append(fit['scale'])
            targets = op('geometry_unproject', projected=projected, depthOffset=depth, firstScale=scales[0],
                         secondScale=scales[1] if step else [1], canonical=canonical, validity=validity,
                         targets=np.zeros((33, 3)))['targets']
            stages.append(targets)

    def candidate(first, projected, depth, validity):
        if inline_root:
            return infer('face_fit_inline', first_targets=first, projected=projected, depth=depth, validity=validity)
        cov = infer('face_fit_prepare', targets=first); targets=first; scales=[]; stages=[]
        for step in range(2):
            u, vt = svd(cov['covariance'])
            b = infer('face_fit_bridge', targets=targets, centers=cov['centers'], u=u, vt=vt,
                      projected=projected, depth=depth, previous_scale=scales[0] if step else [1], validity=validity)
            scales.append(b['scale']); targets=b['next_targets']; stages.append(targets)
            cov=dict(covariance=b['covariance'], centers=b['next_centers'])
        u, vt = svd(cov['covariance'])
        pose = infer('face_fit_finish', targets=targets, centers=cov['centers'], u=u, vt=vt)['pose']
        return dict(pose=pose, first_scale=scales[0], second_scale=scales[1], second_targets=stages[0], metric=stages[1])

    cases=[]; rng=np.random.default_rng(72348)
    try:
        # Different cameras, positions, scale, rotations and nonrigid perturbations.
        for case in range(120):
            angles=rng.uniform(-.65,.65,3)
            cx,sx=np.cos(angles[0]),np.sin(angles[0]);cy,sy=np.cos(angles[1]),np.sin(angles[1]);cz,sz=np.cos(angles[2]),np.sin(angles[2])
            rot=np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]]) @ np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]) @ np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
            points=(full[:,:3]+rng.normal(0,.08,(468,3))) @ rot.T * rng.uniform(.65,1.4) + [rng.uniform(-15,15),rng.uniform(-12,12),-rng.uniform(35,250)]
            fx,fy=rng.uniform(1200,3000,2);principal=rng.uniform([1400,1050],[1800,1350])
            depth=-points[:,2];mean_depth=depth.mean()
            landmarks=np.column_stack(((principal[0]+fx*points[:,0]/depth)/3248,(principal[1]-fy*points[:,1]/depth)/2464,(depth-mean_depth)/mean_depth*fx/3248)).astype(np.float32)
            valid=[0 if case%20==0 else 1,.99]
            p=op('geometry_project', landmarks=landmarks,intrinsics=[fx,0,principal[0],0,fy,principal[1],0,0,1],settings=[3248,2464],canonical=full,validity=valid,projected=np.zeros(1404),targets=np.zeros(1404),depthOffset=[0])
            cases.append(dict(label='synthetic-'+str(case),first=p['targets'].reshape(-1,3)[indices],projected=p['projected'].reshape(-1,3)[indices],depth=p['depthOffset'],validity=valid))
        # Preserve original files; consume only previously accepted saved native tensors.
        folder=ROOT/'artifacts/facelandmarker/registration-lab/packet-check-2026-10-31/capture-session'
        for path in sorted(folder.glob('*/sample.json')):
            d=json.loads(path.read_text());f=d['geometryProbe']['fit']
            cases.append(dict(label=str(path.relative_to(ROOT)),first=np.asarray(f['firstTargets'],np.float32),projected=np.asarray(f['projected'],np.float32),depth=f['depthOffset'],validity=[1,1]))
        rows=[]; maxima={k:0. for k in ['pose','first_scale','second_scale','second_targets','metric']}
        for case in cases:
            args=[case[k] for k in ['first','projected','depth','validity']]
            expected=reference(*args);actual=candidate(*args)
            errors={k:float(np.max(np.abs(actual[k]-expected[k]))) for k in expected}
            for key,error in errors.items():
                maxima[key]=max(maxima[key],error)
                np.testing.assert_allclose(actual[key],expected[key],rtol=2e-5,atol=2e-4,err_msg=case['label']+' '+key)
                assert np.isfinite(actual[key]).all()
            # Centimetre pose/metric outputs: tolerance above is 2 micrometres absolute,
            # plus relative FP32 reduction error; no physical accuracy is inferred.
            rows.append(dict(case=case['label'],errors=errors))
        # Direct final solve: reflection correction and zero-scale fallback.
        for label,targets in [('reflected',canonical[:,:3]*[-1,1,1]),('zero',np.zeros((33,3))),('tiny',canonical[:,:3]*1e-12)]:
            prep=op('geometry_covariance',canonical=canonical,targets=targets,covariance=np.zeros(9),centers=np.zeros(6));u,vt=svd(prep['covariance'])
            expected=op('geometry_solve',canonical=canonical,targets=targets,centers=prep['centers'],u=u,vt=vt,pose=np.zeros(16),scale=[0])
            actual=(infer('inline_solve',targets=targets) if inline_root else
                    infer('face_fit_finish',targets=targets,centers=prep['centers'],u=u,vt=vt))['pose']
            # Zero covariance has no unique optimum. Inline uses identity; OpenCV
            # can return a different orthogonal basis. Check its objective below.
            if not (inline_root and label == 'zero'):
                np.testing.assert_allclose(actual,expected['pose'],rtol=2e-5,atol=2e-4,err_msg=label)
            else:
                upper=actual.reshape(4,4)[:3,:3]
                np.testing.assert_allclose(upper,np.eye(3),atol=1e-6)
                predicted=canonical[:,:3]@upper.T+actual.reshape(4,4)[:3,3]
                baseline=canonical[:,:3]@expected['pose'].reshape(4,4)[:3,:3].T+expected['pose'].reshape(4,4)[:3,3]
                np.testing.assert_allclose(np.sum(predicted**2*canonical[:,3,None]),np.sum(baseline**2*canonical[:,3,None]),rtol=1e-6)
            assert np.linalg.det(actual.reshape(4,4)[:3,:3])>0,label
            rows.append(dict(case=label,poseMaxAbsError=float(np.max(np.abs(actual-expected['pose'])))))
    finally:
        node.stdin.close();node.wait(timeout=10)
    result=dict(cases=len(rows),maxAbsError=maxima,hostInvokeMeanMs={k:float(np.mean(v[5:] if len(v)>5 else v)) for k,v in timings.items() if v},
                referenceSvd='OpenCV FP32' if opencv_svd else 'NumPy',candidate='inline' if inline_root else 'split',
                boundary='Host CPU LiteRT; 120 synthetic cases, three recorded-input replays, reflection and scale fallbacks. Zero covariance compares fit objective when inline. Not installed-device parity/latency or physical accuracy.',results=rows)
    (output/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--inline-root',type=Path);p.add_argument('--opencv-svd',action='store_true')
    args=p.parse_args();validate(args.output,args.inline_root,args.opencv_svd)
