"""Make the printed target or analyze local Face Registration Lab captures.

Requires numpy and opencv-python-headless. No device connection or calibration changes.
Source images are half-resolution, uncorrected RGB exports; all reported face pixel
errors use native 3248x2464 coordinates. Calibration errors use saved-image pixels.
"""
import sys
sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

PATTERN = (8, 6)
SQUARE_METRES = 0.02
CV_TO_CAMERA = np.diag([1., -1., -1., 1.])
CALIB_FLAGS = (cv2.CALIB_ZERO_TANGENT_DIST | cv2.CALIB_FIX_K1 |
               cv2.CALIB_FIX_K2 | cv2.CALIB_FIX_K3)


def target(output):
    """One vector PDF page, exactly A4. Coordinates below are millimetres."""
    output.mkdir(parents=True, exist_ok=True)
    pt = 72 / 25.4
    commands = [f'1 g 0 0 {210*pt:.5f} {297*pt:.5f} re f', '0 g']

    def rect(x, y, w, h):
        commands.append(f'{x*pt:.5f} {(297-y-h)*pt:.5f} {w*pt:.5f} {h*pt:.5f} re f')

    def label(x, y, text, size=11):
        escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        commands.append(f'BT /F1 {size} Tf {x*pt:.5f} {(297-y)*pt:.5f} Td ({escaped}) Tj ET')

    label(15, 18, 'Face Registration Lab - camera calibration', 16)
    label(15, 28, 'A4 portrait. Print at 100% / Actual Size. Disable Fit to Page.')
    label(15, 36, '9 x 7 squares; 8 x 6 internal corners; each square is 20 mm.')
    label(15, 44, 'Keep this sheet flat and stationary throughout the capture session.')
    for row in range(7):
        for col in range(9):
            if (row + col) % 2 == 0:
                rect(15 + col * 20, 55 + row * 20, 20, 20)
    label(15, 209, 'Printed board extent: 180 x 140 mm. Measure before use.')
    rect(15, 223, 100, .2)
    for tick in range(11):
        rect(15 + tick * 10, 221, .2, 4 if tick % 5 else 6)
    label(15, 234, 'This ruler must measure exactly 100 mm.')
    label(15, 247, 'Use Mode A and the Checkerboard calibration test step.')
    label(15, 255, 'Collect at least 12 views, with the board in different image regions.')
    label(15, 263, 'Vary headset yaw and pitch. Stop moving before saving a sample.')
    label(15, 271, 'Keep still until Saved appears. Keep all corners visible.')
    payload = ('\n'.join(commands) + '\n').encode('ascii')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {210*pt:.5f} {297*pt:.5f}] '
                '/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>').encode(),
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               f'<< /Length {len(payload)} >>\nstream\n'.encode() + payload + b'endstream']
    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(pdf)
    pdf.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010} 00000 n \n'.encode())
    pdf.extend((f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n').encode())
    path = output / 'checkerboard-A4-20mm.pdf'
    path.write_bytes(pdf)
    (output / 'checkerboard.json').write_text(json.dumps(dict(
        inner_corners=PATTERN, square_metres=SQUARE_METRES, paper_mm=[210, 297],
        board_mm=[180, 140], pdf_sha256=hashlib.sha256(pdf).hexdigest()), indent=2) + '\n')
    print(path)


def array(sample, name, shape):
    value = np.asarray(sample[name], dtype=np.float64).reshape(shape)
    if not np.isfinite(value).all():
        raise ValueError(f'{name} contains non-finite values')
    return value


def apply(points, transform):
    points = np.asarray(points)
    homogeneous = np.column_stack([points, np.ones(len(points))]) @ transform.T
    return homogeneous[:, :-1] / homogeneous[:, -1:]


def rms(delta):
    return float(np.sqrt(np.mean(np.sum(np.square(delta), axis=-1))))


def draw_points(image, points, color, radius=2):
    for x, y in points:
        if np.isfinite([x, y]).all() and 0 <= x < image.shape[1] and 0 <= y < image.shape[0]:
            cv2.circle(image, (round(float(x)), round(float(y))), radius, color, -1, cv2.LINE_AA)


def pose_correction_matrix(sample):
    value = sample.get('poseCorrection')
    transform = np.eye(4)
    if value is None:
        return transform
    enabled = value.get('id') == 'head-down-40mm-v1'
    if value.get('id') not in ('current', 'head-down-40mm-v1') or value.get('enabled') != enabled:
        raise ValueError('Unknown or inconsistent lab pose correction')
    expected = np.array([0, -.040 if enabled else 0, 0])
    offset = value.get('headTranslationMetres')
    if not isinstance(offset, list) or len(offset) != 3 or value.get('cameraRayScale') != 1 or not np.allclose(offset, expected, atol=1e-7, rtol=0):
        raise ValueError('Unsupported lab pose correction')
    transform[:3, 3] = expected
    return transform


def read_sample(path, output):
    sample = json.loads(path.read_text())
    if sample['schema'] not in (2, 3) or sample['mode'] not in (0, 1, 2, 3, 4):
        raise ValueError('Unsupported capture schema or mode')
    if (sample['sourceWidth'], sample['sourceHeight'], sample['nativeWidth'], sample['nativeHeight'],
            sample['sourceScale']) != (1624, 1232, 3248, 2464, .5):
        raise ValueError('Unexpected source image geometry')
    result = array(sample, 'result', (2994,))
    stage_result = array(sample, 'stageResult', (2994,))
    frame = array(sample, 'captureFrame', (6,))
    if result[0] != sample['sequence'] or stage_result[0] != sample['sequence'] or frame[3] <= 0 or frame[4] != 0:
        raise ValueError('Capture is stale or not from the requested detector frame')
    camera = array(sample, 'cameraIntrinsics', (3, 3))
    image_affine = array(sample, 'imageTransform', (3, 3))
    if sample['mode'] == 4:
        profile = sample['customCalibration']
        if (sample['schema'] != 3 or profile['schema'] != 1 or
                profile['profileType'] != 'custom-virtual-camera' or
                profile['coordinateSpace'] != 'virtual-image-pixels' or
                profile['fingerprint'] != sample['fingerprint'] or
                (profile['nativeWidth'], profile['nativeHeight']) != (3248, 2464) or
                type(sample['calibrationRevision']) is not int or sample['calibrationRevision'] < 0):
            raise ValueError('Invalid custom calibration profile metadata')
        requested = array(profile, 'cameraIntrinsics', (3, 3))
        fx, fy, cx, cy = (profile[key] for key in ('fx', 'fy', 'cx', 'cy'))
        if not (250 <= fx <= 6000 and 250 <= fy <= 6000 and 0 <= cx <= 3248 and 0 <= cy <= 2464):
            raise ValueError('Invalid custom calibration values')
        if not np.allclose(requested, [[fx, 0, cx], [0, fy, cy], [0, 0, 1]], atol=.001, rtol=0):
            raise ValueError('Custom calibration scalar/matrix mismatch')
        if not np.allclose(camera, requested, atol=.001, rtol=0):
            raise ValueError('Custom calibration disagrees with captured camera intrinsics')
        if not np.allclose(array(profile, 'imageTransform', (3, 3)), image_affine, atol=1e-6, rtol=0):
            raise ValueError('Custom calibration image transform mismatch')
    crop = np.vstack([array(sample, 'cropAffine', (2, 3)), [0, 0, 1]])
    model = array(sample, 'modelLandmarks', (478, 3))
    # Crop maps virtual pixels to model pixels; A maps native pixels to virtual pixels.
    source_points = apply(model[:, :2], np.linalg.inv(crop @ image_affine))
    images = {}
    for name, dimensions in [('source', (1232, 1624)), ('detector', (256, 256)), ('landmarker', (256, 256))]:
        value = cv2.imread(str(path.parent / f'{name}.ppm'))
        if value is None or value.shape != (*dimensions, 3):
            raise ValueError(f'Missing or incomplete {name}.ppm')
        images[name] = value
    output.mkdir(parents=True, exist_ok=True)
    for name, value in images.items():
        cv2.imwrite(str(output / f'{name}.png'), value)
    report = dict(sample=str(path.parent), mode=sample['modeLabel'], step=sample['step'],
                  sequence=sample['sequence'], face_measured=bool(result[1] > 0),
                  head_stable=sample.get('headStableAtExposure', sample['headStableDuringReadback']),
                  head_movement_metres=sample['headMovementMetres'],
                  head_movement_degrees=sample['headMovementDegrees'],
                  source_k=(np.linalg.inv(image_affine) @ camera).tolist())
    report['pose_correction'] = sample.get('poseCorrection', {'id':'current'})
    report['motion_gate'] = 'exposure +/-50 ms' if sample['schema'] == 3 else 'full export window'
    report['head_stable_during_export'] = sample['headStableDuringReadback']
    if sample['schema'] == 3:
        report['head_movement_at_exposure_metres'] = sample['headMovementAtExposureMetres']
        report['head_movement_at_exposure_degrees'] = sample['headMovementAtExposureDegrees']
        report['geometry_probe'] = inspect_geometry_probe(sample, result)
        if sample['mode'] == 0 and sample['step'] == 'Checkerboard calibration':
            found, corners = cv2.findChessboardCornersSB(cv2.cvtColor(images['source'], cv2.COLOR_BGR2GRAY),
                PATTERN, flags=cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY)
            check = dict(corners_found=bool(found), boundary='Fixed candidate validation on new views; not a camera refit or accepted Stage calibration')
            if found:
                profile = json.loads((Path(__file__).resolve().parents[1] /
                    'calibration/measured-profile-2026-10-28.json').read_text())
                measured_k = np.diag([.5, .5, 1]) @ np.array(profile['source_intrinsics'])
                service_k = np.diag([.5, .5, 1]) @ array(sample, 'serviceIntrinsics', (3, 3))
                _, check['measured_rms_saved_px'] = pose_for_board(corners, measured_k)
                _, check['service_rms_saved_px'] = pose_for_board(corners, service_k)
            report['board_candidate_check'] = check
    if result[1] > 0:
        vertices = result[1438:2872].reshape(478, 3)
        pose = result[2924:2940].reshape(4, 4)
        camera_to_tracking = array(sample, 'cameraToTracking', (4, 4))
        # Kotlin packet vertices are already service-Local metres. No extra face pose or Z reflection.
        camera_points = apply(vertices, np.linalg.inv(camera_to_tracking))
        service_to_stage = array(sample, 'serviceToStage', (4, 4))
        stage_vertices = stage_result[1438:2872].reshape(478, 3)
        stage_expected = apply(vertices, service_to_stage)
        registration = (array(sample, 'headToStageAtCapture', (4, 4)) @ pose_correction_matrix(sample) @
                        array(sample, 'cameraToHead', (4, 4)) @ np.linalg.inv(camera_to_tracking))
        if 'rawServiceToStage' in sample:
            raw_registration = array(sample, 'headToStageAtCapture', (4, 4)) @ array(sample, 'cameraToHead', (4, 4)) @ np.linalg.inv(camera_to_tracking)
            if not np.allclose(array(sample, 'rawServiceToStage', (4, 4)), raw_registration, atol=2e-5):
                raise ValueError('Raw registration disagrees with uncorrected capture chain')
        if not np.allclose(service_to_stage, registration, atol=2e-5):
            raise ValueError('Saved Stage registration disagrees with capture head/optical camera chain')
        if rms(stage_vertices - stage_expected) > 2e-5:
            raise ValueError('Saved Stage mesh disagrees with service mesh transform')
        report['stage_transform_rms_metres'] = rms(stage_vertices - stage_expected)
        report['stage_mesh_center_metres'] = np.mean(stage_vertices[:468], axis=0).tolist()
        report['head_relative_face_center_metres'] = np.mean(apply(stage_vertices[:468], np.linalg.inv(array(sample, 'headToStageAtCapture', (4, 4)))), axis=0).tolist()
        depth = -camera_points[:, 2]
        if (depth <= 0).any():
            raise ValueError('Measured mesh contains vertices behind the camera')
        virtual = np.column_stack([camera[0, 2] + camera[0, 0] * camera_points[:, 0] / depth,
                                   camera[1, 2] - camera[1, 1] * camera_points[:, 1] / depth])
        reprojection = apply(virtual, np.linalg.inv(image_affine))
        packed = result[4:1438].reshape(478, 3)[:, :2] * [3248, 2464]
        packed_source = apply(packed, np.linalg.inv(image_affine))
        report.update(mesh_source_rms_native_px=rms(reprojection[:468] - source_points[:468]),
                      mesh_to_packed_rms_native_px=rms(reprojection - packed_source),
                      crop_to_packed_rms_native_px=rms(packed_source - source_points),
                      inferred_median_face_depth_metres=float(np.median(depth[:468])),
                      model_relative_z_range_px=float(np.ptp(model[:468, 2])),
                      mesh_minus_landmarks_mean_native_px=np.mean(reprojection[:468] - source_points[:468], axis=0).tolist())
        draw_points(images['landmarker'], model[:, :2], (0, 255, 0), 1)
        draw_points(images['source'], source_points * .5, (0, 255, 0), 3)
        draw_points(images['source'], reprojection[:468] * .5, (255, 0, 255), 1)
        report['eye_projection_status'] = sample.get('eyeProjectionStatus', 'UNAVAILABLE')
        cv2.imwrite(str(output / 'landmarker-overlay.png'), images['landmarker'])
        cv2.imwrite(str(output / 'source-overlay.png'), images['source'])
    return sample, report


def inspect_geometry_probe(sample, result):
    """Replay the shipped operators at saved native boundaries; retain mismatches as evidence."""
    probe = sample['geometryProbe']
    if probe['schema'] != 1:
        raise ValueError('Unsupported geometry probe')
    producer, fit, mesh = (probe[key] for key in ('producer', 'fit', 'mesh'))
    for boundary in (producer, fit, mesh):
        if (array(boundary, 'command', (4,))[0] != sample['sequence'] or
                not np.array_equal(array(boundary, 'captureFrame', (6,)), sample['captureFrame'])):
            raise ValueError('Geometry probe has stale sequence or camera timestamp')
    if producer['mode'][0] != sample['mode']:
        raise ValueError('Geometry probe mode mismatch')
    packet = array(mesh, 'result', (2994,))
    if packet[0] != sample['sequence']:
        raise ValueError('Geometry probe packet is stale')
    report = dict(result_matches_readback=bool(np.array_equal(packet, result)),
                  raw_fit_mesh_rms_model_px=rms(array(fit, 'modelLandmarks', (478, 3)) -
                                                array(mesh, 'modelLandmarks', (478, 3))),
                  roi_matches_fit=bool(np.array_equal(mesh['roi'], fit['roi'])),
                  fit_pose_matches_mesh=bool(np.array_equal(mesh['fitPose'], fit['fitPose'])))
    if result[1] <= 0:
        return report
    project = Path(__file__).resolve().parents[2]
    assets = project / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker'
    geometry = json.loads((assets / 'data/face_geometry.json').read_text())
    canonical = np.array(geometry['canonical']).reshape(468, 4)
    indices = np.flatnonzero(canonical[:, 3] > 0)
    if len(indices) != 33:
        raise ValueError('Changed canonical fit subset')
    canonical_fit = canonical[indices]
    process = subprocess.Popen(['node', str(project / 'FaceLandmarkerApp/tools/run_operator.mjs')],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def op(name, **tensors):
        process.stdin.write(json.dumps(dict(script=str(assets / 'operators' / f'{name}.js'),
            tensors={k: np.asarray(v).ravel().tolist() for k, v in tensors.items()}))+'\n')
        process.stdin.flush()
        answer = json.loads(process.stdout.readline())
        if 'error' in answer:
            raise ValueError(answer['error'])
        return {k: np.array(v) for k, v in answer['tensors'].items()}

    def solve(targets):
        prepared = op('geometry_covariance', canonical=canonical_fit, targets=targets,
                      covariance=np.zeros(9), centers=np.zeros(6))
        u, _, vt = np.linalg.svd(prepared['covariance'].reshape(3, 3))
        return op('geometry_solve', canonical=canonical_fit, targets=targets,
                  centers=prepared['centers'], u=u, vt=vt, pose=np.zeros(16), scale=[0])

    try:
        for label, target_key, native_key in [('first', 'firstTargets', 'firstScale'),
                                               ('second', 'secondTargets', 'secondScale')]:
            replay = solve(array(fit, target_key, (33, 3)))
            report[f'{label}_scale_host_minus_native'] = float(replay['scale'][0] - fit[native_key][0])
        replay = solve(array(fit, 'metricVerticesCm', (33, 3)))
        native_pose = array(fit, 'fitPose', (4, 4))
        pose_delta = replay['pose'].reshape(4, 4) - native_pose
        report['fit_pose_translation_host_minus_native_cm'] = pose_delta[:3, 3].tolist()
        report['fit_pose_linear_max_difference'] = float(np.max(np.abs(pose_delta[:3, :3])))
        metric = array(mesh, 'metricVerticesCm', (478, 3))
        report['fit_mesh_metric_rms_cm'] = rms(metric[indices] - array(fit, 'metricVerticesCm', (33, 3)))
        camera = array(mesh, 'cameraIntrinsics', (3, 3))
        projected = array(mesh, 'projected', (478, 3))
        expected_rays = metric[:, :2] / -metric[:, 2:3]
        report['metric_to_projected_rms_virtual_px'] = rms((expected_rays - projected[:, :2]) *
                                                          [camera[0, 0], camera[1, 1]])
        full_canonical = np.vstack((canonical, np.zeros((10, 4))))
        replay_metric = op('geometry_unproject', projected=projected,
                          canonical=full_canonical, depthOffset=mesh['depthOffset'],
                          firstScale=mesh['firstScale'], secondScale=mesh['secondScale'],
                          validity=[1, result[3]], targets=np.zeros(1434))['targets'].reshape(478, 3)
        report['metric_replay_rms_cm'] = rms(replay_metric - metric)
        packed = op('pack_service_result', command=mesh['command'], validity=[1, result[3]],
                    roi=mesh['roi'], landmarks=result[4:1438], metric=metric,
                    pose=mesh['fitPose'], worldPose=mesh['rawWorldPose'],
                    blendshapes=result[2872:2924], detectorInfo=result[2940:2943],
                    diagnostics=result[2946:2978], leftCameraToXr=mesh['cameraToTracking'],
                    result=np.zeros(2994))['result']
        report['pack_replay_vertex_rms_metres'] = rms(packed[1438:2872].reshape(478, 3) -
                                                     packet[1438:2872].reshape(478, 3))
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    return report


def board_object_points():
    points = np.zeros((PATTERN[0] * PATTERN[1], 3), np.float32)
    points[:, :2] = np.mgrid[:PATTERN[0], :PATTERN[1]].T.reshape(-1, 2) * SQUARE_METRES
    return points


def fit_camera(corners, image_size):
    objects = [board_object_points() for _ in corners]
    fit = cv2.calibrateCameraExtended(objects, corners, image_size, None, None, flags=CALIB_FLAGS)
    error, camera, distortion, rvecs, tvecs, deviations, _, errors = fit
    if not np.isfinite(camera).all() or not np.isfinite(deviations).all():
        raise ValueError('Calibration is degenerate; collect more varied views')
    return dict(rms_saved_px=float(error), k=camera, distortion=distortion,
                rvecs=rvecs, tvecs=tvecs, std_fx_fy_cx_cy=deviations[:4].reshape(-1).tolist(),
                per_view_rms_saved_px=errors.reshape(-1).tolist())


def pose_for_board(corners, camera):
    ok, rotation, translation = cv2.solvePnP(board_object_points(), corners, camera, np.zeros(5))
    if not ok or translation[2, 0] <= 0:
        raise ValueError('Checkerboard pose could not be recovered')
    matrix = np.eye(4)
    matrix[:3, :3] = cv2.Rodrigues(rotation)[0]
    matrix[:3, 3] = translation[:, 0]
    projected, _ = cv2.projectPoints(board_object_points(), rotation, translation, camera, np.zeros(5))
    return matrix, rms(projected.reshape(-1, 2) - corners.reshape(-1, 2))


def rotation_distance(a, b):
    return float(np.rad2deg(np.arccos(np.clip((np.trace(a.T @ b)-1)/2, -1, 1))))


def calibrate(rows, output):
    usable, skipped = [], []
    for sample, report in rows:
        if sample['mode'] != 0 or sample['step'] != 'Checkerboard calibration':
            continue
        if not report['head_stable']:
            skipped.append(dict(sample=report['sample'], reason='Head motion/history failed '+report['motion_gate']))
            continue
        image = cv2.imread(str(Path(report['sample']) / 'source.ppm'))
        found, corners = cv2.findChessboardCornersSB(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), PATTERN,
            flags=cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY)
        if not found:
            skipped.append(dict(sample=report['sample'], reason='All 8 x 6 internal corners not found'))
            continue
        cv2.drawChessboardCorners(image, PATTERN, corners, True)
        view_name = f'board-{len(usable)+1:02}.png'
        cv2.imwrite(str(output / view_name), image)
        usable.append((sample, report, corners))
    result = dict(usable_views=len(usable), skipped=skipped,
                  distortion_model='Rectified pinhole: all radial/tangential distortion fixed to zero',
                  square_metres=SQUARE_METRES, inner_corners=PATTERN,
                  status='NEED_MORE_VIEWS', warnings=[])
    if len(usable) < 12:
        result['warnings'].append('Need at least 12 stable Mode A checkerboard views; 16 recommended.')
        return result
    if len({Path(report['sample']).parent for _, report, _ in usable}) != 1:
        raise ValueError('Calibrate one stationary-board session at a time; do not mix app restarts')
    corners = [item[2] for item in usable]
    fit = fit_camera(corners, (1624, 1232))
    native = np.diag([2., 2., 1.]) @ fit['k']
    result.update(status='CANDIDATE_REQUIRES_REVIEW', k_saved=fit['k'].tolist(), k_native=native.tolist(),
                  rms_saved_px=fit['rms_saved_px'], per_view_rms_saved_px=fit['per_view_rms_saved_px'],
                  std_fx_fy_cx_cy_saved_px=fit['std_fx_fy_cx_cy'],
                  fx_over_fy=float(native[0, 0]/native[1, 1]))
    # Every fourth view is held out: do not score a calibration solely on its training images.
    training = [value for i, value in enumerate(corners) if i % 4 != 0]
    held_out = [value for i, value in enumerate(corners) if i % 4 == 0]
    training_fit = fit_camera(training, (1624, 1232))
    held_errors = [pose_for_board(value, training_fit['k'])[1] for value in held_out]
    service_k = array(usable[0][0], 'cameraIntrinsics', (3, 3))
    result['held_out_rms_saved_px'] = held_errors
    result['service_k_native'] = service_k.tolist()
    result['service_fixed_k_rms_saved_px'] = [pose_for_board(value, np.diag([.5, .5, 1.]) @ service_k)[1]
                                             for value in corners]
    result['native_k_minus_service'] = (native - service_k).tolist()
    result['training_only_k_native'] = (np.diag([2., 2., 1.]) @ training_fit['k']).tolist()
    positions, rotations, board_tilts, centers = [], [], [], []
    reference = None
    for sample, report, observed in usable:
        # A symmetric board permits a 180-degree corner-order flip. Resolve only that
        # ambiguity using proximity to the first world orientation; never refit extrinsics.
        world_from_camera = array(sample, 'headToStageAtCapture', (4, 4)) @ array(sample, 'cameraToHead', (4, 4))
        candidates = []
        for ordered in (observed, observed[::-1].copy()):
            camera_from_board, _ = pose_for_board(ordered, fit['k'])
            candidates.append((world_from_camera @ CV_TO_CAMERA @ camera_from_board, camera_from_board))
        if reference is None:
            chosen, camera_from_board = candidates[0]
            reference = chosen[:3, :3]
        else:
            chosen, camera_from_board = min(candidates, key=lambda pair: rotation_distance(reference, pair[0][:3, :3]))
        positions.append(chosen[:3, 3])
        rotations.append(chosen[:3, :3])
        board_tilts.append(float(np.rad2deg(np.arccos(np.clip(abs(camera_from_board[2, 2]), 0, 1)))))
        centers.append(np.mean(observed.reshape(-1, 2), axis=0))
    positions = np.array(positions)
    result['stationary_board_world_repeatability'] = dict(
        position_rms_about_mean_metres=rms(positions - positions.mean(axis=0)),
        position_peak_to_peak_metres=np.ptp(positions, axis=0).tolist(),
        max_rotation_from_first_degrees=max(rotation_distance(reference, r) for r in rotations),
        boundary='Requires a stationary board and unchanged tracking origin. Includes K, extrinsics, localization and pose-timing error; it does not isolate an extrinsic correction.')
    result['coverage'] = dict(board_center_span_saved_px=np.ptp(centers, axis=0).tolist(),
                              board_tilt_range_degrees=[min(board_tilts), max(board_tilts)])
    if fit['rms_saved_px'] > 1 or max(held_errors) > 1.5:
        result['warnings'].append('High reprojection residual: inspect corners/blur/flatness and the fixed-pinhole assumption.')
    if max(board_tilts) < 20 or min(np.ptp(centers, axis=0)) < 150:
        result['warnings'].append('Weak view diversity: add tilted views and move the board image across both axes.')
    if max(fit['std_fx_fy_cx_cy'][:2]) > .02 * min(fit['k'][0, 0], fit['k'][1, 1]):
        result['warnings'].append('Focal-length uncertainty exceeds 2%; collect more diverse views.')
    return result


def analyze(captures, output, do_calibrate):
    output.mkdir(parents=True, exist_ok=True)
    rows, rejected = [], []
    files = sorted(path for path in captures.rglob('sample.json') if not path.parent.name.endswith('.pending'))
    if not files:
        raise ValueError(f'No completed samples found in {captures}')
    for index, path in enumerate(files, 1):
        try:
            rows.append(read_sample(path, output / f'{index:03}-{path.parent.name}'))
        except (ValueError, KeyError, OSError, cv2.error, np.linalg.LinAlgError) as error:
            rejected.append(dict(sample=str(path), reason=str(error)))
    report = dict(schema=1, accepted=len(rows), rejected=rejected,
                  boundary='Internal crop/mesh consistency does not establish physical depth or VST alignment. Stage poses use public tracking callback arrival times; eye render matrices are unavailable. Board world repeatability includes intrinsics, extrinsics, tracking and timing.',
                  samples=[row[1] for row in rows])
    if do_calibrate:
        report['calibration'] = calibrate(rows, output)
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    lines = ['# Face Registration Lab capture report', '', report['boundary'], '',
             '| Sample | Mode / step | Stable | Face | Mesh RMS (native px) | Inferred depth (m) |',
             '|---|---|---|---|---:|---:|']
    for _, row in rows:
        error = row.get('mesh_source_rms_native_px')
        depth = row.get('inferred_median_face_depth_metres')
        lines.append(f"| {Path(row['sample']).name} | {row['mode']} / {row['step']} | {row['head_stable']} | "
                     f"{row['face_measured']} | {f'{error:.4f}' if error is not None else '-'} | "
                     f"{f'{depth:.3f}' if depth is not None else '-'} |")
    if do_calibrate:
        calibration = report['calibration']
        lines += ['', f"Calibration: **{calibration['status']}**, {calibration['usable_views']} usable views.", '',
                  '```json', json.dumps(calibration, indent=2), '```']
    lines += ['', 'Green source points: raw model landmarks mapped through the inverse crop. '
              'Magenta: the actual rendered mesh projected back into the source camera. '
              'Check the overlay visually; a small numerical round trip does not validate the camera.', '',
              f'Rejected samples: {len(rejected)}. Details and Stage-registration checks are in report.json.']
    (output / 'report.md').write_text('\n'.join(lines) + '\n')
    print(f"Accepted {len(rows)}, rejected {len(rejected)}. {output / 'report.md'}")
    if not rows:
        raise ValueError('No valid completed samples')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    make = actions.add_parser('target', help='Create an exact-size vector PDF checkerboard')
    make.add_argument('--output', type=Path, required=True)
    inspect = actions.add_parser('analyze', help='Convert PPMs, check geometry, optionally fit camera intrinsics')
    inspect.add_argument('captures', type=Path)
    inspect.add_argument('--output', type=Path, required=True)
    inspect.add_argument('--calibrate', action='store_true')
    args = parser.parse_args()
    if args.action == 'target':
        target(args.output)
    else:
        analyze(args.captures, args.output, args.calibrate)


if __name__ == '__main__':
    main()
