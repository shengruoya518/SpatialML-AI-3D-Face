"""Exercise the packaged tongue TFLite model on controlled RGB mouth crops.

These synthetic fixtures validate the actual FlatBuffer, not real-camera accuracy.
No device images are read or exported by this test.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from ai_edge_litert.interpreter import Interpreter
from PIL import Image


def validate(model: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    interpreter = Interpreter(model_path=str(model), num_threads=1)
    interpreter.allocate_tensors()
    inputs = {item['name']: item for item in interpreter.get_input_details()}
    result_tensor = interpreter.get_output_details()[0]
    fixtures = []
    for name in ('open_empty', 'teeth', 'lip_rim', 'tongue_inside_only',
                 'tongue_protruding', 'closed_with_pink', 'no_face'):
        for brightness in (.4, .7, 1.0):
            crop = np.empty((256, 256, 3), dtype=np.float32)
            crop[:] = [.70, .50, .33]
            crop[128:169, 104:153] = [.035, .025, .025]
            if name == 'teeth':
                crop[133:143, 108:149] = [.92, .91, .86]
            if name == 'lip_rim':
                crop[126:132, 100:157] = [.9, .46, .57]
                crop[164:171, 100:157] = [.9, .46, .57]
            if name in ('tongue_inside_only', 'tongue_protruding', 'closed_with_pink', 'no_face'):
                crop[135:164, 113:144] = [.9, .46, .57]
            if name in ('tongue_protruding', 'closed_with_pink', 'no_face'):
                crop[164:187, 114:143] = [.9, .46, .57]
            crop *= brightness
            raw = np.zeros(1434, dtype=np.float32)
            for index, x, y in ((61, 98, 150), (291, 158, 150), (13, 128, 132),
                                (14, 128, 133 if name == 'closed_with_pink' else 162), (17, 128, 170)):
                raw[index * 3:index * 3 + 2] = [x, y]
            values = {
                'mouth_image': crop[None],
                'raw_landmarks': raw.reshape(1, 1, 1, -1),
                'validity': np.array([0 if name == 'no_face' else 1, 1], dtype=np.float32).reshape(1, 1, 1, -1),
                'command': np.array([17001, 0, 0, 0], dtype=np.float32).reshape(1, 1, 1, -1),
            }
            for key, value in values.items():
                tensor = inputs[key]
                assert list(value.shape) == list(tensor['shape']), (key, value.shape, tensor['shape'])
                interpreter.set_tensor(tensor['index'], value)
            interpreter.invoke()
            sequence, confidence = interpreter.get_tensor(result_tensor['index']).reshape(-1)
            assert sequence == 17001 and np.isfinite(confidence)
            expected = name == 'tongue_protruding'
            assert (confidence > .9 if expected else confidence < .1), (name, brightness, confidence)
            stem = f'{name}-{brightness:.1f}'
            Image.fromarray(np.rint(crop * 255).astype(np.uint8)).save(output / f'{stem}.png')
            fixtures.append(dict(name=name, brightness=brightness, confidence=float(confidence),
                                 sequence=int(sequence), expectedTongue=expected))
    report = dict(status='PASS', model=str(model), sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                  cases=fixtures, limitation='Synthetic fixtures only; device lighting and real tongue accuracy remain unverified')
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(fixtures)} packaged-model fixtures, tongue protrusion only; sequence preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    validate(args.model, args.output)
