"""Exercise the serialized inline rotation on full-rank and degenerate matrices.

For nonunique optima compare the SO(3) objective, not arbitrary SVD bases.
All execution is host CPU LiteRT, not installed headset validation.
"""
import argparse
import json
from pathlib import Path
import time

import cv2
import numpy as np
from ai_edge_litert.interpreter import Interpreter


def validate(root):
    interpreter = Interpreter(model_path=str(root/'probes/rotation.tflite'), num_threads=1)
    interpreter.allocate_tensors()
    inp, out = interpreter.get_input_details()[0], interpreter.get_output_details()[0]
    rng = np.random.default_rng(422390)
    rows, timings = [], []
    def orthogonal():
        q, _ = np.linalg.qr(rng.normal(size=(3,3)))
        return q
    cases = [('zero', np.zeros((3,3)))]
    for index in range(1000):
        u, v = orthogonal(), orthogonal()
        spectrum = np.sort(10**rng.uniform(-4, 0, 3))[::-1]
        for name, singular in [('regular',spectrum),('reflected',spectrum*[1,1,-1]),
                               ('rank_two',[1,.1,0]),('rank_one',[1,0,0]),
                               ('near_rank_one',[1,1e-7,1e-9]),
                               ('isotropic',[1,1,1]),('reflected_tie',[1,1,-1])]:
            # Uniform scaling exercises normalization without changing optimum.
            factor = 10**rng.uniform(-25,25)
            cases.append((name+'-'+str(index), ((u*np.asarray(singular))@v.T)*factor))
    for label, value in cases:
        covariance = value.astype(np.float32)
        interpreter.set_tensor(inp['index'], covariance.reshape(inp['shape']))
        start=time.perf_counter();interpreter.invoke();timings.append((time.perf_counter()-start)*1000)
        rotation = interpreter.get_tensor(out['index']).reshape(3,3).astype(np.float64)
        assert np.isfinite(rotation).all(),label
        orthogonality=float(np.max(np.abs(rotation.T@rotation-np.eye(3))))
        determinant=float(np.linalg.det(rotation))
        assert orthogonality < 3e-6 and abs(determinant-1) < 3e-6,(label,orthogonality,determinant)
        magnitude=max(float(np.max(np.abs(covariance))),1e-30)
        normalized=(covariance.astype(np.float64)/magnitude).astype(np.float32)
        singular, u, vt=cv2.SVDecomp(normalized)
        baseline=(u@np.diag([1,1,np.linalg.det(u@vt)])@vt).astype(np.float64)
        loss=float(np.sum((baseline-rotation)*normalized))
        assert abs(loss) < 6e-6,(label,loss)
        # For well-separated optima, compare orientation against double precision
        # SVD too. The actual normalized FP32 input defines the reference problem.
        du, ds, dvt=np.linalg.svd(normalized.astype(np.float64))
        dr=(du*np.array([1,1,np.linalg.det(du@dvt)]))@dvt
        signed=ds*np.array([1,1,np.linalg.det(du@dvt)])
        gap=2*(signed[1]+signed[2])
        rot_error=float(np.max(np.abs(rotation-dr)))
        if gap > .01:
            assert rot_error < 8e-5,(label,gap,rot_error)
        rows.append(dict(case=label,orthogonality=orthogonality,determinant=determinant,
                         objectiveLoss=loss,rotationError=rot_error,eigenGap=float(gap)))
    result=dict(cases=len(rows),maxOrthogonality=max(r['orthogonality'] for r in rows),
                maxDeterminantError=max(abs(r['determinant']-1) for r in rows),
                maxAbsObjectiveLoss=max(abs(r['objectiveLoss']) for r in rows),
                maxSeparatedRotationError=max(r['rotationError'] for r in rows if r['eigenGap']>.01),
                hostRotationInvokeMeanMs=float(np.mean(timings[20:])),
                boundary='Host CPU LiteRT against OpenCV FP32 objective and NumPy FP64 rotation. Degenerate rotation is not unique. No headset latency or installed service equivalence.',results=rows)
    (root/'rotation-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    validate(parser.parse_args().root)
