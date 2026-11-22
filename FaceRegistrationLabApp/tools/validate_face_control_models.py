"""Compare fused control models with the shipped JavaScript at FP32 boundaries.

Run with:
  uv run --no-project --with ai-edge-litert python ... --models <folder> --output <folder>

This is host CPU parity. It does not establish Android model transport, GPU
delegation, VST pixel equivalence, optical accuracy, or headset latency.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

import numpy as np
from ai_edge_litert.interpreter import Interpreter


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker'


class Models:
    def __init__(self, folder):
        self.models = {}
        self.inputs = {}
        self.timings = {}
        for name in ('face_detector_control', 'face_roi_control',
                     'face_landmark_control', 'face_landmark_control_lab',
                     'detector_compact_preprocess_gpu', 'face_completion_marker'):
            model = Interpreter(model_path=str(folder / (name + '.tflite')), num_threads=1)
            model.allocate_tensors()
            self.models[name] = model.get_signature_runner('serving_default')
            self.inputs[name] = {detail['name']: detail for detail in model.get_input_details()}
            self.timings[name] = []

    def run(self, name, **values):
        start = time.perf_counter()
        tensors = {}
        for key, value in values.items():
            detail = self.inputs[name][key]
            tensors[key] = np.asarray(value, detail['dtype']).reshape(detail['shape'])
        output = self.models[name](**tensors)
        self.timings[name].append((time.perf_counter() - start) * 1000)
        return {key: np.asarray(value, np.float32).reshape(-1) for key, value in output.items()}


class JavaScript:
    def __init__(self):
        self.process = subprocess.Popen(
            ['node', str(ROOT / 'FaceLandmarkerApp/tools/run_operator.mjs')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def run(self, name, **tensors):
        def values(value):
            result = []
            for item in np.asarray(value).reshape(-1):
                number = float(item)
                result.append(number if np.isfinite(number) else
                              ('NaN' if np.isnan(number) else ('Infinity' if number > 0 else '-Infinity')))
            return result
        request = dict(script=str(ASSETS / 'operators' / (name + '.js')),
                       tensors={key: values(value) for key, value in tensors.items()})
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        response = json.loads(self.process.stdout.readline())
        assert 'error' not in response, (name, response)
        # Every SpatialML operator boundary stores FP32, while Node evaluates JS in double.
        return {key: np.asarray(value, np.float32).reshape(-1) for key, value in response['tensors'].items()}

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=10)


def assert_close(label, actual, expected, maxima, atol=5e-4, rtol=3e-5):
    actual = np.asarray(actual, np.float32).reshape(-1)
    expected = np.asarray(expected, np.float32).reshape(-1)
    assert actual.shape == expected.shape, (label, actual.shape, expected.shape)
    error = float(np.nanmax(np.abs(actual - expected))) if actual.size else 0.0
    maxima[label] = max(maxima.get(label, 0.0), error)
    np.testing.assert_allclose(actual, expected, atol=atol, rtol=rtol, equal_nan=True,
                               err_msg=label)


def detector_reference(js, case, detection=True):
    camera = js.run('lab_camera', serviceIntrinsics=case['service_intrinsics'],
                    imageTransform=case['image_transform'], trialIntrinsics=case['trial_intrinsics'],
                    labMode=case['lab_mode'], intrinsics=np.zeros(9, np.float32))['intrinsics']
    state = case['track_state'].copy()
    if detection:
        decoded = js.run('decode_detection', boxesFine=case['boxes_fine'], boxesCoarse=case['boxes_coarse'],
                         scoresFine=case['scores_fine'], scoresCoarse=case['scores_coarse'],
                         settings=case['settings'], timestamp=case['timestamp'], trackState=state,
                         roi=np.zeros(6), affine=np.zeros(6), detectorInfo=np.zeros(3))
        roi, affine, detector_info = decoded['roi'], decoded['affine'], decoded['detectorInfo']
        state = decoded['trackState']
    else:
        roi, affine, detector_info = np.zeros(6, np.float32), np.zeros(6, np.float32), None
    prepared = js.run('prepare_roi', timestamp=case['timestamp'], settings=case['settings'],
                      command=case['command'], trackState=state, roi=roi, affine=affine,
                      frame=np.zeros(6, np.float32))
    composed = js.run('lab_affine', cropAffine=prepared['affine'],
                      imageTransform=case['image_transform'], sourceToCrop=np.zeros(6))['sourceToCrop']
    snapshot = js.run('lab_frame_snapshot', command=case['command'], frame=prepared['frame'],
                      roi=prepared['roi'], affine=prepared['affine'], intrinsics=camera,
                      serviceIntrinsics=case['service_intrinsics'], imageTransform=case['image_transform'],
                      leftCameraToXr=case['left_camera_to_xr'], labMode=case['lab_mode'],
                      snapshot=np.zeros(66))['snapshot']
    result = dict(intrinsics=camera, roi=prepared['roi'], affine=prepared['affine'],
                  sample_affine=composed, frame=prepared['frame'],
                  next_track_state=prepared['trackState'], producer_snapshot=snapshot)
    if detection:
        result['detector_info'] = detector_info
    return result


def detector_cases():
    rng = np.random.default_rng(944)
    cases = []
    for index in range(20):
        width, height = 3248.0, 2464.0
        settings = np.asarray([width, height, .25, .5, 1, .35, .45, .1, .25, 1, .75], np.float32)
        state = np.zeros(24, np.float32)
        state[[0, 1, 2, 3, 4, 5, 11, 13, 14, 18]] = [1, 100, .05, 1624, 1232, 800,
                                                         1 if index % 3 else 0, 100, .08, 1]
        boxes = rng.normal(0, 20, (896, 16)).astype(np.float32)
        boxes[:, 2:4] = rng.uniform(5, 60, (896, 2))
        scores = np.full(896, -100, np.float32)
        if index % 5:
            ids = rng.choice(896, 10 + index, replace=False)
            scores[ids] = rng.normal(1, 2, len(ids))
        if index == 2:
            scores[[0, 1]] = 2; boxes[1] = boxes[0]
        if index == 3:
            scores[2] = np.inf; scores[3] = np.nan; boxes[4, 0] = np.nan; scores[4] = 10
        transform = np.asarray([[1, 0, 0], [0, 1, 0], [0, 0, 1]], np.float32)
        if index % 4 == 1:
            transform = np.asarray([[.98, 0, 24], [0, 1.02, -11], [0, 0, 1]], np.float32)
        service = np.asarray([1800, 0, 1624, 0, 1780, 1232, 0, 0, 1], np.float32)
        trial = np.asarray([1750, 0, 1600, 0, 1760, 1210, 0, 0, 1], np.float32)
        sx = 256 / width; pad_y = (256 - height * sx) / 2
        cases.append(dict(boxes_fine=boxes[:512], boxes_coarse=boxes[512:],
                          scores_fine=scores[:512, None], scores_coarse=scores[512:, None],
                          settings=settings, timestamp=np.asarray([0, 100, 0, 120000000 + index * 1000000], np.float32),
                          command=np.asarray([index + 1, 0, 1, 1], np.float32), track_state=state,
                          service_intrinsics=service, image_transform=transform, trial_intrinsics=trial,
                          lab_mode=np.asarray([index % 6], np.float32), left_camera_to_xr=np.eye(4, dtype=np.float32),
                          detector_to_source=np.asarray([1/sx, 1/sx, 0, -pad_y/sx], np.float32)))
    return cases


def validate_detector(models, js, maxima):
    for name in ('face_detector_control', 'face_roi_control'):
        assert models.inputs[name]['timestamp']['dtype'] == np.int32
    cases = detector_cases()
    for index, case in enumerate(cases):
        expected = detector_reference(js, case, True)
        actual = models.run('face_detector_control', **case)
        for name in expected:
            assert_close(f'detector/{name}', actual[name], expected[name], maxima)
    for index, source in enumerate(cases[:8]):
        case = {key: np.copy(value) if isinstance(value, np.ndarray) else value for key, value in source.items()
                if not key.startswith(('boxes_', 'scores_')) and key != 'detector_to_source'}
        case['command'][3] = 0
        expected = detector_reference(js, case, False)
        actual = models.run('face_roi_control', **case)
        for name in expected:
            assert_close(f'roi/{name}', actual[name], expected[name], maxima)
    profile = json.loads((ROOT / 'FaceRegistrationLabApp/calibration/stereo-face-existing-data-2026-11-06.json').read_text())
    stereo = {key: np.copy(value) for key, value in cases[0].items()}
    stereo['lab_mode'] = np.asarray([5], np.float32)
    stereo['trial_intrinsics'] = np.asarray(profile['sourceIntrinsicsNativePixels'], np.float32)
    stereo['image_transform'] = np.asarray(profile['currentPreservedAffine'], np.float32).reshape(3, 3)
    expected_stereo = np.asarray(profile['currentAffineWorkingIntrinsics'], np.float32).ravel()
    for model in ('face_detector_control', 'face_roi_control'):
        inputs = stereo if model == 'face_detector_control' else {
            key: value for key, value in stereo.items()
            if not key.startswith(('boxes_', 'scores_')) and key != 'detector_to_source'}
        actual = models.run(model, **inputs)
        assert_close(model + '/frozen_stereo_camera', actual['intrinsics'], expected_stereo, maxima, atol=.001, rtol=0)
    assert_close('js/frozen_stereo_camera', detector_reference(js, stereo)['intrinsics'], expected_stereo, maxima, atol=.001, rtol=0)
    image = np.arange(336 * 336 * 3, dtype=np.uint8).reshape(1, 336, 336, 3)
    crop = models.run('detector_compact_preprocess_gpu', image=image)['model_input']
    # Exercise every row index and both crop edges against OpenCV's nearest resize.
    # Keep the reference independent of the LiteRT resize implementation.
    import cv2
    expected_crop = cv2.resize(image[0], (336, 256), interpolation=cv2.INTER_NEAREST)[:, 40:296]
    np.testing.assert_array_equal(crop.reshape(256, 256, 3), expected_crop.astype(np.float32) / 255)
    marker = models.run('face_completion_marker', command=np.asarray([12345, .1, 1, 1], np.float32).reshape(1, 1, 1, 4))
    np.testing.assert_array_equal(marker['sequence'], np.asarray([12345], np.float32))
    # The actual fused model must sample the raw face center after mapping a compact detection
    # into virtual image pixels and composing the crop with the calibration affine.
    compact_cases = 0
    for sx_image, sy_image, tx_image, ty_image in [(1, 1, 0, 0),
            (.7673501372337341, 1, 377.70703125, 0), (.98, 1.02, 24, -11)]:
        for cx, cy in [(72, 96), (136, 120), (208, 160)]:
            case = {key: np.copy(value) for key, value in cases[0].items()}
            case['track_state'][11] = 0
            case['image_transform'] = np.asarray([[sx_image, 0, tx_image],
                [0, sy_image, ty_image], [0, 0, 1]], np.float32)
            case['boxes_fine'][:] = 0
            case['boxes_coarse'][:] = 0
            case['scores_fine'][:] = -100
            case['scores_coarse'][:] = -100
            # Anchor 0 is at (8,8); a single rotated-eye candidate has an exact center.
            case['boxes_fine'][0] = np.asarray([cx-8, cy-8, 40, 48,
                cx-20-8, cy-8-8, cx+20-8, cy+8-8,
                cx-8, cy-8, cx-8, cy+16-8, cx-24-8, cy-8, cx+24-8, cy-8], np.float32)
            case['scores_fine'][0] = 2
            source_scale_x, source_scale_y = 3248/336, 2464/256
            case['detector_to_source'] = np.asarray([sx_image*source_scale_x,
                sy_image*source_scale_y, sx_image*40*source_scale_x+tx_image, ty_image], np.float32)
            actual = models.run('face_detector_control', **case)
            assert actual['roi'][0] == 1
            inverse_crop = cv2.invertAffineTransform(actual['sample_affine'].reshape(2, 3))
            sampled_center = inverse_crop @ np.asarray([128, 128, 1], np.float32)
            expected_center = np.asarray([(cx+40)*source_scale_x, cy*source_scale_y], np.float32)
            assert_close('compact/source_crop_center', sampled_center, expected_center, maxima,
                         atol=.01, rtol=0)
            compact_cases += 1
    return len(cases) + 8 + 2 + compact_cases + 3


def landmark_reference(js, fit, case):
    tracked = js.run('track_landmarks', rawLandmarks=case['raw_landmarks'],
                     presenceLogit=case['presence_logit'], roi=case['roi'], settings=case['settings'],
                     frame=case['frame'], intrinsics=case['intrinsics'], indices=case['indices'],
                     canonical=case['canonical'], subset=np.zeros(1), trackState=case['track_state'],
                     landmarks=np.zeros(1), blendInput=np.zeros(1), projected=np.zeros(99),
                     targets=np.zeros(99), depthOffset=np.zeros(1), validity=np.zeros(2))
    fitted = fit(first_targets=tracked['targets'].reshape(1, 1, 33, 3),
                 projected=tracked['projected'].reshape(1, 1, 33, 3),
                 depth=tracked['depthOffset'].reshape(1, 1, 1, 1),
                 validity=tracked['validity'].reshape(1, 1, 1, 2))
    fitted = {key: np.asarray(value, np.float32).reshape(-1) for key, value in fitted.items()}
    posed = js.run('face_pose', pose=fitted['pose'], validity=tracked['validity'],
                   leftCameraToXr=case['left_camera_to_xr'], command=case['command'],
                   settings=case['settings'], frame=case['frame'], trackState=tracked['trackState'],
                   poseState=case['pose_state'], worldPose=np.zeros(16), rawWorldPose=np.zeros(16),
                   poseStatus=np.zeros(1))
    diagnosed = js.run('registration_diagnostics', projected=tracked['projected'], metric=fitted['metric'],
                       canonical=case['canonical'], pose=fitted['pose'], validity=posed['validity'],
                       roi=case['roi'], intrinsics=case['intrinsics'], frame=case['frame'],
                       command=case['command'], trackState=posed['trackState'],
                       poseStatus=posed['poseStatus'], diagnostics=np.zeros(32))
    snapshot = js.run('lab_geometry_snapshot', command=case['command'], frame=case['frame'], roi=case['roi'],
                      affine=case['affine'], rawLandmarks=case['raw_landmarks'], projected=tracked['projected'],
                      firstTargets=tracked['targets'], secondTargets=fitted['second_targets'], metric=fitted['metric'],
                      pose=fitted['pose'], rawWorldPose=posed['rawWorldPose'], worldPose=posed['worldPose'],
                      firstScale=fitted['first_scale'], secondScale=fitted['second_scale'],
                      depthOffset=tracked['depthOffset'], intrinsics=case['intrinsics'],
                      leftCameraToXr=case['left_camera_to_xr'], result=np.zeros(1),
                      upstream=case['producer_snapshot'], snapshot=np.zeros(1995))['snapshot']
    return dict(next_track_state=diagnosed['trackState'], validity=diagnosed['validity'],
                depth_offset=tracked['depthOffset'], first_scale=fitted['first_scale'],
                second_scale=fitted['second_scale'], pose=fitted['pose'],
                next_pose_state=posed['poseState'], world_pose=posed['worldPose'],
                raw_world_pose=posed['rawWorldPose'], pose_status=posed['poseStatus'],
                diagnostics=diagnosed['diagnostics'], fit_snapshot=snapshot)


def landmark_cases():
    geometry = json.loads((ASSETS / 'data/face_geometry.json').read_text())
    full = np.asarray(geometry['canonical'], np.float32).reshape(468, 4)
    indices = np.flatnonzero(full[:, 3] > 0).astype(np.float32)
    canonical = full[indices.astype(np.int32)]
    rng = np.random.default_rng(7721)
    cases = []
    for index in range(18):
        angles = np.linspace(0, 2*np.pi, 468, endpoint=False)
        raw = np.zeros((478, 3), np.float32)
        raw[:468, 0] = 128 + (65 + index) * np.cos(angles)
        raw[:468, 1] = 128 + 82 * np.sin(angles)
        raw[:468, 2] = 8 * np.sin(angles * 3) + rng.normal(0, .3, 468)
        raw[468:] = raw[:10]
        raw[33, :2] = [91, 118]; raw[263, :2] = [165, 120]
        state = np.zeros(24, np.float32)
        state[[0, 1, 2, 3, 4, 5, 6, 11, 13, 14, 18]] = [1, 100, .07, 1624, 1232, 800, 0, 2, 100, .07, 1]
        roi = np.asarray([1, .95, 1624, 1232, 800, .03], np.float32)
        frame = np.asarray([100, .1 + index * .001, .03, 1, 0, .03], np.float32)
        presence = np.asarray([8], np.float32)
        intrinsics = np.asarray([1800, 0, 1624, 0, 1780, 1232, 0, 0, 1], np.float32)
        if index == 1: presence[0] = -10
        if index == 2: frame[3] = 0
        if index == 3: intrinsics[0] = 0
        if index == 4: raw[20, 0] = np.nan
        if index == 5: roi[0] = 0
        cases.append(dict(raw_landmarks=raw, presence_logit=presence, roi=roi,
                          affine=np.asarray([.32, 0, -390, 0, .32, -266], np.float32),
                          settings=np.asarray([3248,2464,.25,.5,1,.35,.45,.1,.25,1,.75], np.float32),
                          frame=frame, intrinsics=intrinsics, track_state=state,
                          left_camera_to_xr=np.eye(4, dtype=np.float32),
                          command=np.asarray([index + 1, 0, 1, 1], np.float32),
                          pose_state=np.zeros(24, np.float32), producer_snapshot=np.arange(66, dtype=np.float32),
                          indices=indices, canonical=canonical))
    return cases


def validate_landmark(models, js, maxima):
    fit_model = Interpreter(model_path=str(ASSETS / 'model/face_fit_inline.tflite'), num_threads=1)
    fit_model.allocate_tensors(); fit = fit_model.get_signature_runner('serving_default')
    cases = landmark_cases()
    for index, case in enumerate(cases):
        expected = landmark_reference(js, fit, case)
        inputs = {key: value for key, value in case.items() if key not in ('indices', 'canonical')}
        actual = models.run('face_landmark_control_lab', **inputs)
        for name in expected:
            tolerance = 2e-3 if name in ('pose', 'world_pose', 'raw_world_pose', 'fit_snapshot') else 8e-4
            assert_close(f'landmark/{name}', actual[name], expected[name], maxima, atol=tolerance, rtol=8e-5)
        if index == 0:
            production = models.run('face_landmark_control', **inputs)
            for name in production:
                assert_close(f'landmark-production/{name}', production[name], actual[name], maxima,
                             atol=2e-6, rtol=2e-6)
    return len(cases)


def validate(models_folder, output):
    output.mkdir(parents=True, exist_ok=True)
    models = Models(models_folder)
    js = JavaScript()
    maxima = {}
    try:
        detector_count = validate_detector(models, js, maxima)
        landmark_count = validate_landmark(models, js, maxima)
    finally:
        js.close()
    result = dict(status='PASS', detectorAndUtilityCases=detector_count,
                  landmarkCases=landmark_count, maximumAbsoluteErrors=maxima,
                  hostMeanMilliseconds={name: float(np.mean(values)) for name, values in models.timings.items() if values},
                  boundary='Host CPU LiteRT parity at FP32 operator boundaries. GPU target, Android transport, VST pixels, optical accuracy and headset latency are unverified.')
    (output / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    validate(args.models, args.output)
