"""Generate a weightless full sparse fit with an inline proper-rotation solver.

The fit needs R, not U/S/V. Horn's symmetric quaternion problem gives the same
SO(3) optimum as reflection-corrected SVD. Fixed cyclic Jacobi sweeps diagonalize
that 4x4 problem using portable FP32 builtins. No custom op or service change.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from generate_face_geometry import ASSETS, FitGraph


def horn_matrix(c):
    a, b, c0, d, e, f, g, h, i = np.asarray(c).reshape(-1)
    return np.array([[a+e+i, h-f, c0-g, d-b],
                     [h-f, a-e-i, b+d, c0+g],
                     [c0-g, b+d, e-a-i, f+h],
                     [d-b, c0+g, f+h, i-a-e]])


def quaternion_rotation(outer):
    q = np.asarray(outer).reshape(4, 4)
    return np.array([[q[0,0]+q[1,1]-q[2,2]-q[3,3], 2*(q[1,2]-q[0,3]), 2*(q[1,3]+q[0,2])],
                     [2*(q[1,2]+q[0,3]), q[0,0]-q[1,1]+q[2,2]-q[3,3], 2*(q[2,3]-q[0,1])],
                     [2*(q[1,3]-q[0,2]), 2*(q[2,3]+q[0,1]), q[0,0]-q[1,1]-q[2,2]+q[3,3]]])


class InlineFitGraph(FitGraph):
    def __init__(self, canonical, sweeps=5):
        super().__init__(canonical)
        self.sweeps = sweeps

    def matmul(self, a, b, adj_x=False, adj_y=False):
        sa, sb = self.tensors[a].shape, self.tensors[b].shape
        return self.op('BATCH_MATMUL', [a, b], [1, 1, sa[-1] if adj_x else sa[-2], sb[-2] if adj_y else sb[-1]],
                       options={'adj_x': adj_x, 'adj_y': adj_y})

    def rotation(self, covariance):
        flat = self.reshape(covariance, [1, 1, 1, 9])
        # Normalize before squaring. Zero covariance deterministically returns I;
        # its rotation is mathematically unidentifiable, as with rank-one input.
        absolute = self.op('ABS', [flat], [1, 1, 1, 9])
        magnitude = self.component(absolute, 0)
        for index in range(1, 9):
            magnitude = self.binary('MAXIMUM', magnitude, self.component(absolute, index))
        divisor = self.choose(self.compare('GREATER', magnitude, self.zero), magnitude, self.one)
        normalized = self.binary('DIV', flat, divisor)
        horn = self.tensor('horn_linear_map', [1, 1, 9, 16],
                           values=[horn_matrix(row).flatten() for row in np.eye(9)])
        matrix = self.reshape(self.matmul(normalized, horn), [1, 1, 4, 4])
        vectors = self.tensor('eigenvectors_identity', [1, 1, 4, 4], values=np.eye(4))
        two = self.constant('two', 2)
        floor = self.constant('jacobi_divisor_floor', 1e-20)
        minus_one = self.constant('minus_one', -1)
        schedules = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
        maps = []
        for pairs in schedules:
            coeffs = np.zeros((4, 4, 4), np.float32)
            for k, (p, q) in enumerate(pairs):
                coeffs[k,p,p] = coeffs[k,q,q] = 1
                coeffs[k+2,p,q] = 1; coeffs[k+2,q,p] = -1
            maps.append(self.tensor('jacobi_rotation_map', [1, 1, 4, 16], values=coeffs))
        for _ in range(self.sweeps):
            for pairs, mapping in zip(schedules, maps):
                flat_matrix = self.reshape(matrix, [1, 1, 1, 16])
                a = self.gather(flat_matrix, [p*4+p for p, q in pairs])
                d = self.gather(flat_matrix, [q*4+q for p, q in pairs])
                b = self.gather(flat_matrix, [p*4+q for p, q in pairs])
                delta = self.binary('SUB', d, a)
                twice_b = self.binary('MUL', b, two)
                norm = self.op('SQRT', [self.binary('ADD', self.binary('MUL', delta, delta),
                                                   self.binary('MUL', twice_b, twice_b))], [1, 1, 1, 2])
                denominator = self.binary('MAXIMUM', self.binary('ADD', self.op('ABS', [delta], [1, 1, 1, 2]), norm), floor)
                sign = self.choose(self.compare('LESS', delta, self.zero), minus_one, self.one)
                tangent = self.binary('MUL', sign, self.binary('DIV', twice_b, denominator))
                cosine = self.op('RSQRT', [self.binary('ADD', self.one, self.binary('MUL', tangent, tangent))], [1, 1, 1, 2])
                sine = self.binary('MUL', tangent, cosine)
                jacobi = self.reshape(self.matmul(self.concat([cosine, sine]), mapping), [1, 1, 4, 4])
                matrix = self.matmul(self.matmul(jacobi, matrix, adj_x=True), jacobi)
                vectors = self.matmul(vectors, jacobi)
        flat_matrix = self.reshape(matrix, [1, 1, 1, 16])
        largest = self.component(flat_matrix, 0)
        quaternion = self.gather(vectors, [0])
        for index in range(1, 4):
            value = self.component(flat_matrix, index*5)
            wins = self.compare('GREATER', value, largest)
            largest = self.choose(wins, value, largest)
            quaternion = self.choose(wins, self.gather(vectors, [index]), quaternion)
        norm2 = self.sum(self.binary('MUL', quaternion, quaternion), [2])
        quaternion = self.binary('MUL', quaternion, self.op('RSQRT', [norm2], [1, 1, 1, 1]))
        outer = self.reshape(self.matmul(quaternion, quaternion, adj_y=True), [1, 1, 1, 16])
        rot_map = self.tensor('quaternion_rotation_map', [1, 1, 16, 9],
                              values=[quaternion_rotation(row).flatten() for row in np.eye(16)])
        return self.reshape(self.matmul(outer, rot_map), [1, 1, 3, 3], 'rotation')


def full_fit(canonical, sweeps=5):
    graph = InlineFitGraph(canonical, sweeps)
    targets = graph.input('first_targets', len(canonical), 3)
    projected = graph.input('projected', len(canonical), 3)
    depth = graph.input('depth', 1, 1)
    validity = graph.input('validity', 1, 2)
    scales, stages = [], []
    for step in range(3):
        covariance, centers = graph.covariance(targets)
        rotation = graph.rotation(covariance)
        if step == 2:
            pose = graph.solve_rotation(targets, centers, rotation, pose=True)
            break
        scale = graph.solve_rotation(targets, centers, rotation)
        scales.append(scale)
        targets = graph.unproject(projected, depth, graph.one if step == 0 else scales[0], scale, validity)
        stages.append(targets)
    graph.outputs = [scales[0], scales[1], stages[0], stages[1], pose]
    for index, name in zip(graph.outputs, ['first_scale', 'second_scale', 'second_targets', 'metric', 'pose']):
        graph.tensors[index].name = name
    return graph


def write_model(output, sweeps=5, probes=None):
    geometry = ASSETS / 'data/face_geometry.json'
    canonical = np.asarray(json.loads(geometry.read_text())['canonical'], np.float32).reshape(468, 4)
    canonical = canonical[canonical[:, 3] > 0]
    graph = full_fit(canonical, sweeps)
    data = graph.serialize('Weightless sparse face fitting; inline quaternion Jacobi proper rotation; FP32 CPU')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'face_fit_inline.tflite').write_bytes(data)
    manifest = dict(name='face_fit_inline', sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
                    operators=len(graph.operators), operatorKinds=sorted(set(o[0] for o in graph.operators)),
                    backend='CPU', jacobiSweeps=sweeps, canonicalAssetSha256=hashlib.sha256(geometry.read_bytes()).hexdigest(),
                    solver='Horn quaternion largest eigenvector; paired cyclic Jacobi; SO(3)',
                    inputs=[dict(name=graph.tensors[i].name, shape=graph.tensors[i].shape) for i in graph.inputs],
                    outputs=[dict(name=graph.tensors[i].name, shape=graph.tensors[i].shape) for i in graph.outputs])
    (output / 'face_fit_inline.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if probes:
        probes.mkdir(parents=True, exist_ok=True)
        rotation = InlineFitGraph(canonical, sweeps)
        rotation.outputs = [rotation.rotation(rotation.input('covariance', 3, 3))]
        (probes / 'rotation.tflite').write_bytes(rotation.serialize('Inline proper-rotation validation probe'))
        solve = InlineFitGraph(canonical, sweeps)
        targets = solve.input('targets', len(canonical), 3)
        covariance, centers = solve.covariance(targets)
        solve.outputs = [solve.solve_rotation(targets, centers, solve.rotation(covariance), pose=True)]
        (probes / 'solve.tflite').write_bytes(solve.serialize('Inline final-solve validation probe'))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ASSETS / 'model')
    parser.add_argument('--sweeps', type=int, default=5)
    parser.add_argument('--probes', type=Path)
    args = parser.parse_args()
    if args.sweeps < 1: parser.error('--sweeps must be positive')
    write_model(args.output, args.sweeps, args.probes)
