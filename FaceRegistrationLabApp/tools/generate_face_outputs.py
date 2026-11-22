"""Weightless service-side blend input and compact final-output models.

CPU LiteRT is intentional: these small FP32 graphs avoid JS marshaling and an
extra accelerator transfer. Publication must preserve sequence/clock bits.
The larger image preprocessing models remain independently GPU-selectable.
"""
import hashlib
import json
from pathlib import Path

import tflite as fb
from generate_face_preprocessing import Graph

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker'


def publication(mask):
    g = Graph()
    # Sequence is first, matching the completion reader. Schema and mask follow
    # command, validity, ROI, diagnostics and capture-time camera transform.
    fields = [('command', 4), ('validity', 2), ('roi', 6),
              ('diagnostics', 32), ('camera', 16)]
    if mask & 3:
        fields += [('world_pose', 16)]
    if mask & 2:
        fields += [('raw_landmarks', 1434), ('fit_pose', 16),
                   ('first_scale', 1), ('second_scale', 1), ('depth', 1)]
    if mask & 4:
        fields += [('blendshapes', 52)]
    g.inputs = [g.tensor(name, [1, 1, 1, size]) for name, size in fields]
    contract = g.tensor('contract', [1, 1, 1, 2], values=[2, mask])
    g.outputs = [g.op('CONCATENATION', g.inputs + [contract],
                       [1, 1, 1, sum(n for _, n in fields) + 2], 'result')]
    return g


def blend_input(indices):
    g = Graph()
    raw = g.tensor('raw_landmarks', [1, 1, 1, 1434])
    roi = g.tensor('roi', [1, 1, 1, 6])
    g.inputs = [raw, roi]
    def gathered(axis):
        ids = g.tensor('indices_' + str(axis), [292], fb.TensorType.INT32,
                       [i * 3 + axis for i in indices for _ in range(2)])
        v = g.op('GATHER', [raw, ids], [1, 1, 1, 292])
        return g.binary('SUB', g.binary('DIV', v, g.constant('crop_size_' + str(axis), 256)),
                        g.constant('center_' + str(axis), .5))
    x, y = gathered(0), gathered(1)
    angle = g.component(roi, 5)
    c = g.op('COS', [angle], [1, 1, 1, 1])
    s = g.op('SIN', [angle], [1, 1, 1, 1])
    even = g.tensor('x_channel', [1, 1, 1, 292], values=[1, 0] * 146)
    odd = g.tensor('y_channel', [1, 1, 1, 292], values=[0, 1] * 146)
    # Interleaved XY, inverse ROI crop followed by the trained head's /1024.
    a = g.binary('ADD', g.binary('MUL', c, even), g.binary('MUL', s, odd))
    b = g.binary('SUB', g.binary('MUL', c, odd), g.binary('MUL', s, even))
    xy = g.binary('ADD', g.binary('MUL', x, a), g.binary('MUL', y, b))
    origin = g.binary('ADD', g.binary('MUL', g.component(roi, 2), even),
                      g.binary('MUL', g.component(roi, 3), odd))
    pixels = g.binary('ADD', origin, g.binary('MUL', g.component(roi, 4), xy))
    g.outputs = [g.binary('DIV', pixels, g.constant('normalization', 1024), 'blend_input')]
    return g


def main():
    geometry = json.loads((ASSETS / 'data/face_geometry.json').read_text())
    graphs = [(f'face_output_{mask}', publication(mask)) for mask in range(1, 8)]
    graphs += [('face_blend_input', blend_input(geometry['blendshapeIndices']))]
    manifest = []
    for name, graph in graphs:
        data = graph.serialize('Weightless FP32 face final-output pipeline; CPU LiteRT')
        (ASSETS / 'model' / (name + '.tflite')).write_bytes(data)
        manifest.append(dict(name=name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
                             operators=len(graph.operators), backend='CPU',
                             inputs=[dict(name=graph.tensors[i].name, shape=graph.tensors[i].shape)
                                     for i in graph.inputs],
                             outputs=[dict(name=graph.tensors[i].name, shape=graph.tensors[i].shape)
                                      for i in graph.outputs]))
    (ASSETS / 'model/face_output_models.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
