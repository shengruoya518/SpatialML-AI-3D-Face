"""Exercise exported-sample coordinates and recover an independently known camera.

Synthetic tests establish analysis-tool correctness only, not headset calibration.
"""
import sys
sys.dont_write_bytecode = True

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

import registration_lab as lab


def rotation(vector):
    return cv2.Rodrigues(np.array(vector, dtype=np.float64))[0]


def validate(output):
    output.mkdir(parents=True, exist_ok=True)
    # Execute the actual shipped camera/affine operators, rather than reimplementing their output.
    project = Path(__file__).resolve().parents[2]
    operators = project / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/operators'
    runner = project / 'FaceLandmarkerApp/tools/run_operator.mjs'
    service = np.array([[2065.6, 0, 1623.5], [0, 2089.4, 1231.5], [0, 0, 1.]])
    affine = np.array([[.767, 0, 378.1755], [0, 1, 0], [0, 0, 1.]])
    trial = np.array([[1748., 0, 1623.5], [0, 1748., 1231.5], [0, 0, 1.]])
    measured = np.array([[2642.704699074891, 0, 1672.3769186460834],
                         [0, 2036.9552646219895, 1230.3375545403937], [0, 0, 1.]])
    custom = np.array([[1699.5, 0, 1612.], [0, 1720.25, 1209.], [0, 0, 1.]])
    crop = np.array([[.4, .1, -650.], [-.1, .4, -300.]])
    requests = []
    for mode in range(5):
        image_transform = np.eye(3) if mode == 0 else affine
        requests += [dict(script=str(operators / 'lab_camera.js'), tensors=dict(
            serviceIntrinsics=service.ravel().tolist(), imageTransform=image_transform.ravel().tolist(),
            trialIntrinsics=(custom if mode == 4 else measured if mode == 3 else trial).ravel().tolist(), labMode=[mode], intrinsics=[0]*9)),
            dict(script=str(operators / 'lab_affine.js'), tensors=dict(
            cropAffine=crop.ravel().tolist(), imageTransform=image_transform.ravel().tolist(), sourceToCrop=[0]*6))]
    completed = subprocess.run(['node', str(runner)], input=''.join(json.dumps(x)+'\n' for x in requests),
                               text=True, capture_output=True, check=True)
    answers = [json.loads(x)['tensors'] for x in completed.stdout.splitlines()]
    for mode in range(5):
        image_transform = np.eye(3) if mode == 0 else affine
        np.testing.assert_allclose(np.array(answers[mode*2]['intrinsics']).reshape(3, 3),
                                   custom if mode == 4 else trial if mode == 2 else image_transform @ (measured if mode == 3 else service), atol=1e-10)
        np.testing.assert_allclose(np.array(answers[mode*2+1]['sourceToCrop']).reshape(2, 3),
                                   crop @ image_transform, atol=1e-10)
    np.testing.assert_allclose(np.linalg.inv(affine @ service) @ affine, np.linalg.inv(service), atol=1e-12)
    random = np.random.default_rng(4721)
    camera = np.array([[1032.8, 0, 811.75], [0, 1044.7, 615.75], [0, 0, 1.]])
    corners = []
    for i in range(16):
        r = np.array([(-.35, -.12, .15, .4)[i % 4], (-.4, -.15, .2, .38)[i // 4], .06*(i % 3)])
        t = np.array([-.12 + .07*(i % 4), -.12 + .06*(i // 4), .45 + .06*(i % 3)])
        points, _ = cv2.projectPoints(lab.board_object_points(), r, t, camera, np.zeros(5))
        corners.append((points + random.normal(0, .02, points.shape)).astype(np.float32))
    fit = lab.fit_camera(corners, (1624, 1232))
    np.testing.assert_allclose(fit['k'], camera, atol=1)
    assert fit['rms_saved_px'] < .04
    print('Known-camera recovery maximum error (saved pixels):', np.max(np.abs(fit['k'] - camera)))

    # Construct a rendered local mesh with nonidentity camera and face poses.
    vertices_rh = random.normal(0, [.05, .07, .02], (478, 3))
    camera_to_tracking = np.eye(4)
    camera_to_tracking[:3, :3] = rotation([.1, -.2, .03])
    camera_to_tracking[:3, 3] = [.04, .02, -.08]
    metric_pose = np.eye(4)
    metric_pose[:3, :3] = rotation([-.15, .4, .02]) * 1.08
    metric_pose[:3, 3] = [.02, -.01, -1.1]
    vertices_service = lab.apply(vertices_rh, camera_to_tracking @ metric_pose)
    head_stage = np.eye(4)
    head_stage[:3, :3] = rotation([.03, -.25, -.06])
    head_stage[:3, 3] = [.4, 1.5, -.2]
    camera_head = np.eye(4)
    camera_head[:3, :3] = rotation([-.007, .002, .001])
    camera_head[:3, 3] = [-.026, .043, -.048]
    service_stage = head_stage @ camera_head @ np.linalg.inv(camera_to_tracking)
    camera_points = lab.apply(vertices_rh, metric_pose)
    native_k = np.diag([2., 2., 1.]) @ camera
    # Independent explicit perspective projection in RH camera space.
    source_xy = np.column_stack([native_k[0, 2] - native_k[0, 0]*camera_points[:, 0]/camera_points[:, 2],
                                 native_k[1, 2] + native_k[1, 1]*camera_points[:, 1]/camera_points[:, 2]])
    crop = np.eye(3)
    theta = .35
    crop[:2, :2] = .4 * np.array([[np.cos(theta), np.sin(theta)], [-np.sin(theta), np.cos(theta)]])
    crop[:2, 2] = [128, 128] - crop[:2, :2] @ [1623.5, 1231.5]
    errors = []
    for mode in range(5):
        affine = np.eye(3) if mode == 0 else np.array([[.767, 0, 378.1755], [0, 1, 0], [0, 0, 1.]])
        virtual = lab.apply(source_xy, affine)
        raw_xy = lab.apply(virtual, crop)
        raw = np.column_stack([raw_xy, np.zeros(478)])
        result = np.zeros(2994)
        result[:4] = [mode+1, 1, .95, .99]
        result[4:1438] = np.column_stack([virtual/[3248, 2464], np.zeros(478)]).ravel()
        result[1438:2872] = vertices_service.ravel()
        result[2924:2940] = (camera_to_tracking @ metric_pose).ravel()
        result[2978:2994] = camera_to_tracking.ravel()
        stage_result = result.copy()
        stage_result[1438:2872] = lab.apply(vertices_service, service_stage).ravel()
        stage_result[2924:2940] = (service_stage @ camera_to_tracking @ metric_pose).ravel()
        sample = dict(schema=2, mode=mode, modeLabel=f'TEST mode {mode}', step='SYNTHETIC', sequence=mode+1,
                      sourceWidth=1624, sourceHeight=1232, nativeWidth=3248, nativeHeight=2464, sourceScale=.5,
                      result=result.tolist(), stageResult=stage_result.tolist(), captureFrame=[100, .01*mode, .03, 1, 0, 0],
                      cameraIntrinsics=(affine @ native_k).ravel().tolist(), imageTransform=affine.ravel().tolist(),
                      cropAffine=crop[:2].ravel().tolist(), modelLandmarks=raw.ravel().tolist(),
                      cameraToTracking=camera_to_tracking.ravel().tolist(), cameraToHead=camera_head.ravel().tolist(),
                      headToStageAtCapture=head_stage.ravel().tolist(), serviceToStage=service_stage.ravel().tolist(),
                      headStableDuringReadback=True, headMovementMetres=0, headMovementDegrees=0, stereoEnabled=False)
        if mode in (3, 4):
            # Schema 3 exercises the saved native-boundary analyzer. A static exposure is
            # accepted even when the later export window moved.
            canonical = np.array(json.loads((operators.parent / 'data/face_geometry.json').read_text())['canonical']).reshape(468, 4)
            fit_indices = np.flatnonzero(canonical[:, 3] > 0)
            metric_cm = camera_points * 100
            depth_cm = -metric_cm[:, 2]
            projected = np.column_stack([metric_cm[:, :2] / depth_cm[:, None], depth_cm - 1])
            pose_cm = metric_pose.copy()
            pose_cm[:3, 3] *= 100
            producer = dict(command=[mode+1, .1, 1, 1], captureFrame=sample['captureFrame'],
                            roi=[1, .95, 1623.5, 1231.5, 500, 0], cropAffine=sample['cropAffine'],
                            cameraIntrinsics=sample['cameraIntrinsics'], serviceIntrinsics=native_k.ravel().tolist(),
                            imageTransform=sample['imageTransform'], cameraToTracking=sample['cameraToTracking'], mode=[mode])
            mesh_probe = dict(command=producer['command'], captureFrame=sample['captureFrame'],
                              roi=producer['roi'], cropAffine=sample['cropAffine'], modelLandmarks=raw.ravel().tolist(),
                              projected=projected.ravel().tolist(), firstTargets=[0]*3, secondTargets=[0]*3,
                              metricVerticesCm=metric_cm.ravel().tolist(), fitPose=pose_cm.ravel().tolist(),
                              rawWorldPose=result[2924:2940].tolist(), filteredWorldPose=result[2924:2940].tolist(),
                              firstScale=[1], secondScale=[1], depthOffset=[0],
                              cameraIntrinsics=sample['cameraIntrinsics'], cameraToTracking=sample['cameraToTracking'],
                              result=result.tolist())
            fit_probe = dict(mesh_probe, projected=projected[fit_indices].ravel().tolist(),
                             firstTargets=metric_cm[fit_indices].ravel().tolist(), secondTargets=metric_cm[fit_indices].ravel().tolist(),
                             metricVerticesCm=metric_cm[fit_indices].ravel().tolist(), result=[0])
            sample.update(schema=3, headStableAtExposure=True, headStableDuringReadback=False,
                          headMovementAtExposureMetres=.001, headMovementAtExposureDegrees=.1,
                          geometryProbe=dict(schema=1, producer=producer, fit=fit_probe, mesh=mesh_probe))
        if mode == 4:
            k = np.array(sample['cameraIntrinsics']).reshape(3, 3)
            sample.update(fingerprint='synthetic-ROM', calibrationRevision=7,
                          customCalibration=dict(schema=1, profileType='custom-virtual-camera',
                          coordinateSpace='virtual-image-pixels', fingerprint='synthetic-ROM',
                          nativeWidth=3248, nativeHeight=2464, fx=k[0,0], fy=k[1,1], cx=k[0,2], cy=k[1,2],
                          cameraIntrinsics=sample['cameraIntrinsics'], imageTransform=sample['imageTransform']))
        folder = output / 'synthetic-captures' / f'{mode+1:03}-mode{mode}'
        folder.mkdir(parents=True, exist_ok=True)
        for name, dims in [('source', (1232, 1624)), ('detector', (256, 256)), ('landmarker', (256, 256))]:
            image = np.full((*dims, 3), 60, np.uint8)
            cv2.imwrite(str(folder / f'{name}.ppm'), image)
        (folder / 'sample.json').write_text(json.dumps(sample))
        _, report = lab.read_sample(folder / 'sample.json', output / f'checked-mode{mode}')
        errors.append(report['mesh_source_rms_native_px'])
        assert report['mesh_source_rms_native_px'] < 1e-9, report
        assert report['crop_to_packed_rms_native_px'] < 1e-9, report
        np.testing.assert_allclose(report['inferred_median_face_depth_metres'], np.median(-camera_points[:468, 2]))
        if mode in (3, 4):
            assert report['head_stable'] and not report['head_stable_during_export']
            probe_report = report['geometry_probe']
            assert probe_report['pack_replay_vertex_rms_metres'] < 1e-10, probe_report
            assert probe_report['metric_to_projected_rms_virtual_px'] < 1e-10, probe_report
            assert probe_report['metric_replay_rms_cm'] < 1e-10, probe_report
            assert probe_report['fit_mesh_metric_rms_cm'] < 1e-10, probe_report
            corrupt = json.loads(json.dumps(sample))
            corrupt['geometryProbe']['mesh']['metricVerticesCm'][0] += .5
            changed = lab.inspect_geometry_probe(corrupt, result)
            assert changed['pack_replay_vertex_rms_metres'] > 1e-5, changed
            assert changed['metric_replay_rms_cm'] > .01, changed
            stale_probe = json.loads(json.dumps(sample))
            stale_probe['geometryProbe']['fit']['captureFrame'][0] += 1
            try:
                lab.inspect_geometry_probe(stale_probe, result)
            except ValueError as error:
                assert 'stale' in str(error)
            else:
                raise AssertionError('Stale fit snapshot accepted')
            # A new checkerboard view tests the fixed candidate without refitting it.
            board_sample = json.loads(json.dumps(sample))
            board_sample.update(mode=0, modeLabel='A: Service', step='Checkerboard calibration',
                                serviceIntrinsics=service.ravel().tolist())
            board_sample['result'][1] = board_sample['stageResult'][1] = 0
            board_sample['geometryProbe']['mesh']['result'][1] = 0
            board_sample['geometryProbe']['producer']['mode'] = [0]
            board = np.full((1400, 1800, 3), 255, np.uint8)
            for row in range(7):
                for col in range(9):
                    if (row+col) % 2 == 0:
                        board[row*200:(row+1)*200, col*200:(col+1)*200] = 0
            outer = np.array([[-.02,-.02,0], [.16,-.02,0], [.16,.12,0], [-.02,.12,0]])
            board_xy, _ = cv2.projectPoints(outer, np.array([.3,-.4,.02]), np.array([-.05,-.04,.6]),
                                            np.diag([.5,.5,1]) @ measured, np.zeros(5))
            board_image = cv2.warpPerspective(board, cv2.getPerspectiveTransform(
                np.float32([[0,0],[1800,0],[1800,1400],[0,1400]]), board_xy.astype(np.float32)),
                (1624,1232), borderValue=(245,245,245))
            board_folder = output / 'board-candidate-fixture'
            board_folder.mkdir(exist_ok=True)
            cv2.imwrite(str(board_folder / 'source.ppm'), board_image)
            for name in ('detector', 'landmarker'):
                cv2.imwrite(str(board_folder / f'{name}.ppm'), np.full((256,256,3),60,np.uint8))
            (board_folder / 'sample.json').write_text(json.dumps(board_sample))
            _, board_report = lab.read_sample(board_folder / 'sample.json', output / 'board-candidate-checked')
            candidate_check = board_report['board_candidate_check']
            assert candidate_check['corners_found'] and candidate_check['measured_rms_saved_px'] < .5, candidate_check
            assert candidate_check['service_rms_saved_px'] > candidate_check['measured_rms_saved_px'], candidate_check
        if mode == 4:
            for key, value in [('fx', 0), ('cy', sample['customCalibration']['cy'] + 1),
                               ('coordinateSpace', 'source'), ('fingerprint', 'another-ROM')]:
                invalid = json.loads(json.dumps(sample))
                invalid['customCalibration'][key] = value
                bad = folder / 'invalid-custom.json'
                bad.write_text(json.dumps(invalid))
                try:
                    lab.read_sample(bad, output / 'invalid-custom')
                except ValueError as error:
                    assert 'custom calibration' in str(error).lower(), error
                else:
                    raise AssertionError('Invalid custom profile accepted')
        sample['sequence'] += 10
        stale = folder / 'stale.json'
        stale.write_text(json.dumps(sample))
        try:
            lab.read_sample(stale, output / 'invalid')
        except ValueError as error:
            assert 'stale' in str(error)
        else:
            raise AssertionError('Stale sequence accepted')
    lab.analyze(output / 'synthetic-captures', output / 'synthetic-analysis', False)
    lab.target(output)
    report = dict(boundary='Synthetic host checks only; no device capture was used.',
                  known_k_saved=camera.tolist(), recovered_k_saved=fit['k'].tolist(),
                  calibration_rms_saved_px=fit['rms_saved_px'], mesh_projection_errors_native_px=errors,
                  stale_samples_rejected=5, shipped_camera_affine_operator_checks=10, custom_profile_rejection_checks=4,
                  schema3_boundary_replay_and_corruption_checks='PASS')
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: five affine/mesh export conversions and stale-sequence rejection')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    validate(parser.parse_args().output)
