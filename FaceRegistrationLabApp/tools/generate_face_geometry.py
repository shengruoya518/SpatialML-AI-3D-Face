"""Fuse sparse fitting arithmetic into CPU LiteRT models, retaining native 3x3 SVD.

No learned weights. Canonical 33-point geometry is fixed asset data. Four model
calls (three assets, with the bridge reused) replace eight JavaScript calls.
All intermediates remain inside SpatialML; the final-output contract is unchanged.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import tflite as fb
from generate_face_preprocessing import Graph

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker'


class FitGraph(Graph):
    def __init__(self, canonical):
        super().__init__()
        canonical = np.asarray(canonical, np.float64)
        self.count = len(canonical)
        self.points = self.tensor('canonical_points', [1, 1, self.count, 3], values=canonical[:, :3])
        self.weights = self.tensor('canonical_weights', [1, 1, self.count, 1], values=canonical[:, 3])
        total = canonical[:, 3].sum()
        center = (canonical[:, :3] * canonical[:, 3, None]).sum(0) / total
        centered = canonical[:, :3] - center
        self.center = self.tensor('canonical_center', [1, 1, 1, 3], values=center)
        self.centered = self.tensor('canonical_centered', [1, 1, self.count, 3], values=centered)
        self.total = self.constant('total_weight', total)
        self.denominator = self.constant('canonical_variance', (centered**2 * canonical[:, 3, None]).sum())
        self.zero = self.constant('zero', 0)
        self.one = self.constant('one', 1)

    def input(self, name, rows, columns):
        t = self.tensor(name, [1, 1, rows, columns]); self.inputs.append(t)
        return t

    def gather(self, tensor, indices, axis=3, name=None):
        ids = self.tensor('indices_' + str(len(self.tensors)), [len(indices)], fb.TensorType.INT32, indices)
        shape = self.tensors[tensor].shape.copy(); shape[axis] = len(indices)
        return self.op('GATHER', [tensor, ids], shape, name, {'axis': axis})

    def sum(self, tensor, axes, name=None):
        ids = self.tensor('sum_axes_' + str(len(self.tensors)), [len(axes)], fb.TensorType.INT32, axes)
        shape = self.tensors[tensor].shape.copy()
        for axis in axes: shape[axis] = 1
        return self.op('SUM', [tensor, ids], shape, name)

    def concat(self, tensors, axis=3, name=None):
        shape = self.tensors[tensors[0]].shape.copy()
        shape[axis] = sum(self.tensors[t].shape[axis] for t in tensors)
        return self.op('CONCATENATION', tensors, shape, name, {'axis': axis})

    def reshape(self, tensor, shape, name=None):
        target = self.tensor('shape_' + str(len(self.tensors)), [len(shape)], fb.TensorType.INT32, shape)
        return self.op('RESHAPE', [tensor, target], shape, name)

    def compare(self, kind, left, right):
        shape = np.broadcast_shapes(self.tensors[left].shape, self.tensors[right].shape)
        return self.op(kind, [left, right], shape, dtype=fb.TensorType.BOOL)

    def choose(self, condition, yes, no, name=None):
        shape = np.broadcast_shapes(self.tensors[condition].shape, self.tensors[yes].shape, self.tensors[no].shape)
        return self.op('SELECT_V2', [condition, yes, no], shape, name)

    def covariance(self, targets):
        target_center = self.binary('DIV', self.sum(self.binary('MUL', targets, self.weights), [2]), self.total)
        centered = self.binary('SUB', targets, target_center)
        rows = [self.sum(self.binary('MUL', self.binary('MUL', self.gather(centered, [r]), self.weights), self.centered), [2]) for r in range(3)]
        return self.concat(rows, 2, 'covariance'), self.concat([self.center, target_center], name='centers')

    def solve(self, targets, centers, u, vt, pose=False):
        flat_u = self.reshape(u, [1, 1, 1, 9]); flat_vt = self.reshape(vt, [1, 1, 1, 9])
        def determinant(t):
            parts = [self.component(t, i) for i in range(9)]
            def p(i): return parts[i]
            a = self.binary('MUL', p(0), self.binary('SUB', self.binary('MUL', p(4), p(8)), self.binary('MUL', p(5), p(7))))
            b = self.binary('MUL', p(1), self.binary('SUB', self.binary('MUL', p(3), p(8)), self.binary('MUL', p(5), p(6))))
            c = self.binary('MUL', p(2), self.binary('SUB', self.binary('MUL', p(3), p(7)), self.binary('MUL', p(4), p(6))))
            return self.binary('ADD', self.binary('SUB', a, b), c)
        reflected = self.compare('LESS', self.binary('MUL', determinant(flat_u), determinant(flat_vt)), self.zero)
        sign = self.choose(reflected, self.constant('negative_one', -1), self.one)
        sign_vector = self.concat([self.one, self.one, sign])
        corrected_u = self.binary('MUL', u, sign_vector)
        rotation = self.op('BATCH_MATMUL', [corrected_u, vt], [1, 1, 3, 3])
        return self.solve_rotation(targets, centers, rotation, pose)

    def solve_rotation(self, targets, centers, rotation, pose=False):
        source_center = self.gather(centers, [0, 1, 2])
        centered = self.binary('SUB', self.points, source_center)
        rotated = self.op('BATCH_MATMUL', [centered, rotation], [1, 1, self.count, 3], options={'adj_y': True})
        target_center = self.gather(centers, [3, 4, 5])
        numerator = self.sum(self.binary('MUL', self.binary('MUL', rotated, self.binary('SUB', targets, target_center)), self.weights), [2, 3])
        scale = self.binary('DIV', numerator, self.denominator)
        positive = self.compare('GREATER', scale, self.constant('minimum_scale', 1e-9))
        finite = self.compare('LESS_EQUAL', self.op('ABS', [scale], [1, 1, 1, 1]), self.constant('maximum_finite', np.finfo(np.float32).max))
        good = self.op('LOGICAL_AND', [positive, finite], [1, 1, 1, 1], dtype=fb.TensorType.BOOL)
        scale = self.choose(good, scale, self.one, 'scale')
        if not pose: return scale
        scaled = self.binary('MUL', rotation, scale)
        translation = self.binary('SUB', self.reshape(target_center, [1, 1, 3, 1]),
                                  self.sum(self.binary('MUL', scaled, source_center), [3]))
        upper = self.concat([scaled, translation])
        bottom = self.tensor('homogeneous_row', [1, 1, 1, 4], values=[0, 0, 0, 1])
        return self.concat([upper, bottom], 2, 'pose')

    def unproject(self, projected, depth, previous_scale, current_scale, validity):
        z = self.binary('DIV', self.binary('ADD', self.binary('SUB', self.gather(projected, [2]), depth), self.one), self.binary('MUL', previous_scale, current_scale))
        xy = self.binary('MUL', self.gather(projected, [0, 1]), z)
        targets = self.concat([xy, self.binary('SUB', self.zero, z)])
        good = self.compare('GREATER', self.component(validity, 0), self.zero)
        return self.choose(good, targets, self.points, 'next_targets')


def graphs(canonical):
    prepare = FitGraph(canonical)
    targets = prepare.input('targets', len(canonical), 3)
    prepare.outputs = list(prepare.covariance(targets))

    bridge = FitGraph(canonical)
    targets = bridge.input('targets', len(canonical), 3)
    centers = bridge.input('centers', 1, 6)
    u = bridge.input('u', 3, 3); vt = bridge.input('vt', 3, 3)
    projected = bridge.input('projected', len(canonical), 3)
    depth = bridge.input('depth', 1, 1)
    previous = bridge.input('previous_scale', 1, 1)
    validity = bridge.input('validity', 1, 2)
    scale = bridge.solve(targets, centers, u, vt)
    next_targets = bridge.unproject(projected, depth, previous, scale, validity)
    covariance, next_centers = bridge.covariance(next_targets)
    # Names must be unique for input and output signature bindings.
    bridge.tensors[next_centers].name = 'next_centers'
    bridge.outputs = [scale, next_targets, covariance, next_centers]

    finish = FitGraph(canonical)
    targets = finish.input('targets', len(canonical), 3)
    centers = finish.input('centers', 1, 6)
    u = finish.input('u', 3, 3); vt = finish.input('vt', 3, 3)
    finish.outputs = [finish.solve(targets, centers, u, vt, pose=True)]
    return [('face_fit_prepare', prepare), ('face_fit_bridge', bridge), ('face_fit_finish', finish)]


def main():
    geometry_path = ASSETS / 'data/face_geometry.json'
    canonical = np.asarray(json.loads(geometry_path.read_text())['canonical'], np.float32).reshape(468, 4)
    canonical = canonical[canonical[:, 3] > 0]
    assert len(canonical) == 33
    manifest = []
    for name, graph in graphs(canonical):
        data = graph.serialize('Weightless sparse face fitting; FP32 CPU; native SVD between models')
        (ASSETS / 'model' / (name + '.tflite')).write_bytes(data)
        manifest.append(dict(name=name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
                             operators=len(graph.operators), operatorKinds=sorted(set(o[0] for o in graph.operators)),
                             backend='CPU', canonicalAssetSha256=hashlib.sha256(geometry_path.read_bytes()).hexdigest(),
                             inputs=[dict(name=graph.tensors[i].name, shape=graph.tensors[i].shape) for i in graph.inputs],
                             outputs=[dict(name=graph.tensors[i].name, shape=graph.tensors[i].shape) for i in graph.outputs]))
    (ASSETS / 'model/face_fit_models.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps([{k: m[k] for k in ('name','bytes','operators')} for m in manifest], indent=2))


if __name__ == '__main__':
    main()
