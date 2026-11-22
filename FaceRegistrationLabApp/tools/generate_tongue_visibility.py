"""Portable CPU mouth-image tongue-appearance detector; no protected pixels leave SpatialML.

This is a color/geometry heuristic, not a trained tongue classifier. It samples the central
open-mouth cavity and rejects neutral teeth, dark cavity, ordinary skin and the lip rim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from generate_face_control_models import ControlGraph


def build():
    g = ControlGraph()
    image = g.input_tensor('mouth_image', [1, 256, 256, 3])
    raw = g.input_flat('raw_landmarks', 1434)
    valid = g.input_flat('validity', 2)
    command = g.input_flat('command', 4)
    def point(index, axis): return g.component(raw, index * 3 + axis)
    def constant(value): return g.constant('c_' + str(len(g.tensors)), value)
    def mul(value, factor): return g.binary('MUL', value, constant(factor))
    x1, x2 = point(61, 0), point(291, 0)
    center_x = mul(g.binary('ADD', x1, x2), .5)
    width = g.op('ABS', [g.binary('SUB', x2, x1)], [1, 1, 1, 1])
    top, bottom = point(13, 1), point(14, 1)
    opening = g.binary('SUB', bottom, top)
    center_y = mul(g.binary('ADD', top, bottom), .5)
    gx = g.tensor('pixel_x', [1, 1, 256, 1], values=np.arange(256, dtype=np.float32) + .5)
    gy = g.tensor('pixel_y', [1, 256, 1, 1], values=np.arange(256, dtype=np.float32) + .5)
    dx = g.binary('DIV', g.binary('SUB', gx, center_x), g.binary('MAXIMUM', mul(width, .23), constant(1)))
    dy = g.binary('DIV', g.binary('SUB', gy, center_y), g.binary('MAXIMUM', mul(opening, .34), constant(1)))
    region = g.compare('LESS', g.binary('ADD', g.square(dx), g.square(dy)), g.one)
    red, green, blue = [g.gather(image, [axis], axis=3) for axis in range(3)]
    pink = g.logical('LOGICAL_AND', g.compare('GREATER', red, constant(.15)),
                     g.compare('GREATER', red, mul(green, 1.18)))
    for condition in [g.compare('GREATER', red, mul(blue, 1.05)),
                      g.compare('GREATER', green, mul(red, .32)),
                      g.compare('GREATER', blue, mul(green, .85)),
                      g.compare('GREATER', g.binary('SUB', red, g.binary('MINIMUM', green, blue)), constant(.075))]:
        pink = g.logical('LOGICAL_AND', pink, condition)
    candidates = g.logical('LOGICAL_AND', region, pink)
    count = g.reduce('SUM', g.op('CAST', [candidates], [1, 256, 256, 1]), [1, 2])
    area = g.reduce('SUM', g.op('CAST', [region], [1, 256, 256, 1]), [1, 2])
    fraction = g.binary('DIV', count, g.binary('MAXIMUM', area, g.one))
    score = g.clip(g.binary('DIV', g.binary('SUB', fraction, constant(.20)), constant(.30)), g.zero, g.one)
    # Tongue inside an ordinary open mouth is insufficient: require pink tissue extending
    # below the lower outer lip, with more tongue-like chroma than adjacent skin at that row.
    outer_lip = point(17, 1)
    below = g.logical('LOGICAL_AND',
        g.compare('GREATER', gy, g.binary('ADD', outer_lip, mul(width, .03))),
        g.compare('LESS', gy, g.binary('ADD', outer_lip, mul(width, .20))))
    horizontal = g.op('ABS', [g.binary('SUB', gx, center_x)], [1, 1, 256, 1])
    extension = g.logical('LOGICAL_AND', below, g.compare('LESS', horizontal, mul(width, .18)))
    skin = g.logical('LOGICAL_AND', below, g.compare('GREATER', horizontal, mul(width, .32)))
    skin = g.logical('LOGICAL_AND', skin, g.compare('LESS', horizontal, mul(width, .48)))
    def mean_mask(mask, values):
        total = g.reduce('SUM', g.choose(mask, values, g.zero), [1, 2])
        count = g.reduce('SUM', g.op('CAST', [mask], g.tensors[mask].shape), [1, 2])
        return g.binary('DIV', total, g.binary('MAXIMUM', count, g.one))
    extension_fraction = mean_mask(extension, g.op('CAST', [pink], [1, 256, 256, 1]))
    chroma = g.binary('DIV', g.binary('SUB', blue, mul(green, .85)), g.binary('MAXIMUM', red, constant(.05)))
    contrast = g.binary('SUB', mean_mask(extension, chroma), mean_mask(skin, chroma))
    extension_score = g.clip(g.binary('DIV', g.binary('SUB', extension_fraction, constant(.25)), constant(.40)), g.zero, g.one)
    contrast_score = g.clip(g.binary('DIV', g.binary('SUB', contrast, constant(.025)), constant(.075)), g.zero, g.one)
    score = g.binary('MINIMUM', score, g.binary('MINIMUM', extension_score, contrast_score))
    usable = g.logical('LOGICAL_AND', g.compare('GREATER', g.component(valid, 0), g.zero),
                       g.compare('GREATER', opening, g.binary('MAXIMUM', constant(2), mul(width, .08))))
    usable = g.logical('LOGICAL_AND', usable, g.compare('GREATER', width, constant(12)))
    usable = g.logical('LOGICAL_AND', usable, g.compare('LESS', width, constant(230)))
    confidence = g.choose(usable, score, g.zero)
    output = g.concat([g.component(command, 0), confidence], name='tongue_result')
    g.outputs = [output]
    return g


def write(output):
    graph = build()
    data = graph.serialize('CPU tongue appearance from same-capture mouth image and landmarks; heuristic confidence')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'tongue_visibility.tflite').write_bytes(data)
    metadata = dict(name='tongue_visibility', bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                    backend='CPU', learned=False, operators=len(graph.operators),
                    inputs=[dict(name=graph.tensors[i].name, shape=graph.tensors[i].shape) for i in graph.inputs],
                    output='sequence, tongue appearance confidence',
                    limitation='Color/geometry heuristic needs real tongue/no-tongue validation under device lighting')
    (output / 'tongue_visibility.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    write(parser.parse_args().output)
