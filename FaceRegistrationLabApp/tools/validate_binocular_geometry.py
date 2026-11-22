"""Synthetic optical regressions using geometry and atlas exported from production Kotlin.

This verifies math, identifiers and rejection paths, not headset texture/compositor behavior.
Run validate_intrinsics.py first and pass its output directory with --production.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

import binocular_geometry as bg


def rejected(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('Invalid evidence was accepted')


def camera(x, roll=0):
    rotation = np.diag([1., -1., -1.]) @ Rotation.from_rotvec([0, 0, roll]).as_matrix()
    k = np.array([[1250., 0, 960], [0, 1248., 540], [0, 0, 1]])
    return k @ np.column_stack([rotation, -rotation @ [x, 0, 0]])


def render(production, atlas, p, face=None):
    """Sample production Bitmap rows with the renderer's measured bottom-origin mesh V."""
    image = np.full((1080, 1920, 3), 110, np.uint8)
    vertices = np.array(production['meshPositions']).reshape(-1, 3)
    uv = np.array(production['meshUv']).reshape(-1, 2)
    # Farther quads first, using +depth in this test camera.
    order = sorted(range(len(vertices)//4), key=lambda i: vertices[4*i:4*i+4, 2].mean())
    for q in order:
        points = vertices[4*q:4*q+4]
        tex = uv[4*q:4*q+4].copy()
        tex[:, 1] = 1-tex[:, 1]
        dst = bg.apply(p, points).astype(np.float32)
        if np.max(np.ptp(tex, axis=0)) < .001:
            x, y = np.rint(tex[0]*512).astype(int)
            cv2.fillConvexPoly(image, np.rint(dst).astype(int), atlas[y, x].tolist(), cv2.LINE_AA)
        else:
            # Coordinates are tile edges. Texel centres lie half a pixel inside each edge.
            src = (tex*512-.5).astype(np.float32)
            transform = cv2.getPerspectiveTransform(src, dst)
            warped = cv2.warpPerspective(atlas, transform, (1920, 1080))
            mask = np.zeros(image.shape[:2], np.uint8)
            cv2.fillConvexPoly(mask, np.rint(dst).astype(int), 255)
            image[mask > 0] = warped[mask > 0]
    if face is not None:
        u, v = production['faceMarkerUv']
        marker_color = atlas[int((1-v)*512), int(u*512)].tolist()
        for point, (x, y) in zip(face, bg.apply(p, face)):
            radius = max(2, int(round(1250*.003/-point[2])))
            cv2.circle(image, (round(x), round(y)), radius, marker_color, -1, cv2.LINE_AA)
    return image


def validate(production_dir, output):
    output.mkdir(parents=True, exist_ok=True)
    production = json.loads((production_dir/'projection-reference.json').read_text())
    atlas = cv2.imread(str(production_dir/'projection-atlas.ppm'))
    assert atlas.shape == (512, 512, 3)
    assert production['textureMapping'] == 'bitmap-rows-reversed-for-bottom-origin-mesh-v'
    for marker in production['markers']:
        np.testing.assert_allclose(np.array(marker['rigCorners']).reshape(4, 3), bg.corners(marker['id']), atol=2e-7)
    assert production['checksum'] == bg.checksum(production['sequence'])
    vertices = np.array(production['meshPositions']).reshape(-1, 3)
    np.testing.assert_allclose(vertices[48:].reshape(108, 4, 3).mean(1), bg.code_centres(), atol=1e-7)
    assert len(production['meshTriangles']) == 120*6

    left, right = camera(-.032), camera(.032, .003)
    xyz = np.concatenate([bg.corners(i) for i in range(12)])
    fitted = bg.fit_camera(xyz, bg.apply(left, xyz))
    np.testing.assert_allclose(bg.apply(fitted, xyz), bg.apply(left, xyz), atol=1e-8)
    planar = xyz.copy(); planar[:, 2] = -1
    rejected(lambda: bg.fit_camera(planar, bg.apply(left, planar)))
    # Coordinate-gauge invariance: a translated/rotated Stage must give the same pixels.
    gauge = np.eye(4); gauge[:3, :3] = Rotation.from_rotvec([.2, -.3, .1]).as_matrix()
    gauge[:3, 3] = [10, -5, 8]
    shifted = bg.apply(gauge, xyz)
    np.testing.assert_allclose(bg.apply(bg.fit_camera(shifted, bg.apply(left, xyz)), shifted), bg.apply(left, xyz), atol=1e-7)

    face = np.array([[-.060, .05, -.99], [-.025, .05, -.98], [.025, .05, -.98], [.060, .05, -.99],
                     [0, .005, -.95], [-.040, -.045, -.99], [.040, -.045, -.99], [0, -.115, -1.01]])
    optical = np.eye(4); optical[:3, 3] = [-.035, .043, -.052]
    head = np.eye(4)
    sequence = production['sequence']
    evidence = dict(production, frame=sequence, captureSeconds=100., ownerRoundTripMaxMetres=1e-7,
                    headStableAtExposure=True, exposureHistoryCovered=True, uploadSeconds=100.2,
                    cameraToHead=optical.ravel().tolist(), rigToStage=head.ravel().tolist(),
                    automatic=dict(run='synthetic', pose=0, protocol=bg.PROTOCOL, phase='MARKED'),
                    faceMarkers=[dict(landmark=i, stageMetres=p.tolist()) for i, p in zip(bg.IDS, face)])
    timeline = output/'synthetic-timeline.jsonl'
    timeline.write_text(json.dumps(dict(event='projection_reference', details=evidence))+'\n')
    images = [render(production, atlas, p, face) for p in [left, right]]
    # Reproduce the real 7271d44e failure using the former unreversed Bitmap rows. The
    # old fixture assumed top-origin V and drew face markers as green independently of UVs.
    legacy = render(production, atlas[::-1], left, face)
    cv2.imwrite(str(output/'legacy-atlas-failure.png'), legacy)
    rejected(lambda: bg.calibrate_view(legacy))
    rejected(lambda: bg.decode_sequence(legacy, left))
    rejected(lambda: bg.green_markers(legacy, bg.apply(left, face)))
    checks = []
    for i, image in enumerate(images):
        cv2.imwrite(str(output/f'synthetic-eye{i}.png'), image)
        p, check = bg.calibrate_view(image)
        checks.append(check)
        assert bg.decode_sequence(image, p) == sequence
        assert bg.rms(bg.apply(p, face)-bg.apply([left, right][i], face)) < .5
    occluded = images[0].copy()
    centre = bg.apply(left, bg.code_centres())[26]
    x, y = np.rint(centre).astype(int)
    cv2.rectangle(occluded, (x-4, y-4), (x+4, y+4), (255, 255, 255), -1)
    # Flip a payload cell regardless of its original value; CRC must reject it.
    occluded[y-4:y+5, x-4:x+5] = 255-images[0][y-4:y+5, x-4:x+5]
    rejected(lambda: bg.decode_sequence(occluded, left))
    missing = np.full_like(images[0], 110)
    rejected(lambda: bg.calibrate_view(missing))

    true_params = np.array([.003, -.039, -.008, .003, -.004, .002, np.log(1.09)])
    observation = dict(baselineRigMetres=face.tolist(), cameraToHead=optical.ravel().tolist())
    target = bg.corrected('rigid_ray_scale', true_params, observation)
    anatomy = [bg.apply(p, target) for p in [left, right]]
    anatomy_file = output/'synthetic-anatomy.json'
    anatomy_file.write_text(json.dumps(dict(landmarkIds=bg.IDS, left=anatomy[0].tolist(), right=anatomy[1].tolist())))
    args = SimpleNamespace(left=output/'synthetic-eye0.png', right=output/'synthetic-eye1.png',
                           timeline=timeline, anatomy=anatomy_file, task=None,
                           mirrored_texture=False, output=output/'synthetic-observation.json')
    bg.observe(args)
    observed = json.loads(args.output.read_text())
    assert observed['fitEligible'] and observed['irreducibleTwoViewRmsPx'] < .5
    assert min(observed['baselineRmsPx']) > 30
    # Reusing an image from a moving/incomplete head history must fail even with a valid code.
    event = dict(evidence, headStableAtExposure=False)
    timeline.write_text(json.dumps(dict(event='projection_reference', details=event))+'\n')
    rejected(lambda: bg.observe(args))
    timeline.write_text(json.dumps(dict(event='projection_reference', details=evidence))+'\n')
    np.testing.assert_allclose(bg.triangulate([left, right], anatomy), target, atol=1e-7)
    inconsistent = [anatomy[0], anatomy[1]+[0, 8]]
    impossible = bg.triangulate([left, right], inconsistent)
    assert bg.rms(np.concatenate([bg.apply(p, impossible)-a for p, a in zip([left, right], inconsistent)])) > 3

    observations = []
    for pose in range(10):
        depth = [.7, 1.2, 2., 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2][pose]
        rotation = Rotation.from_rotvec([.02*(pose % 2), (pose % 5-2)*.12, (pose % 3-1)*.1]).as_matrix()
        points = (face+[0, 0, 1]) @ rotation.T - [0, 0, depth]
        o = dict(observation, baselineRigMetres=points.tolist(), automatic=dict(pose=pose),
                 cameras=[left.tolist(), right.tolist()], protocol=bg.PROTOCOL, fitEligible=True,
                 session='synthetic', frame=pose)
        truth = bg.corrected('rigid_ray_scale', true_params, o)
        o['anatomyPixels'] = [bg.apply(p, truth).tolist() for p in [left, right]]
        observations.append(o)
    # Exercise report generation, per-pose balancing, stillness and duplicate-frame checks.
    observation_files = []
    for pose, o in enumerate(observations):
        for frame_index in range(3):
            path = output/f'fit-pose{pose}-frame{frame_index}.json'
            record = dict(o, frame=pose*3+frame_index, captureSeconds=100+pose*10+frame_index*.2,
                          rigToStage=np.eye(4).ravel().tolist(),
                          anatomyRigMetres=bg.corrected('rigid_ray_scale', true_params, o).tolist())
            path.write_text(json.dumps(record))
            observation_files.append(path)
    fit_args = SimpleNamespace(observations=observation_files, output=output/'synthetic-fit.json')
    bg.fit(fit_args)
    fit_report = json.loads(fit_args.output.read_text())
    assert fit_report['models']['rigid_ray_scale']['equalPoseMeanRmsPx'] < 1e-5
    rejected(lambda: bg.fit(SimpleNamespace(observations=observation_files+[observation_files[0]], output=fit_args.output)))
    recovered = bg.solve('rigid_ray_scale', observations)
    np.testing.assert_allclose(recovered, true_params, atol=1e-6)
    for pose in range(10):
        train = [o for o in observations if o['automatic']['pose'] != pose]
        recovered = bg.solve('rigid_ray_scale', train)
        assert bg.rms(bg.residual('rigid_ray_scale', recovered, [observations[pose]], False).reshape(-1, 2)) < 1e-5
    assert bg.rms(bg.residual('rigid', bg.solve('rigid', observations), observations, False).reshape(-1, 2)) > 1
    # Pure translation and pure ray-scale errors must select their actual independent parameters.
    for model, truth in [('translation', np.array([0, -.039, 0])), ('ray_scale', np.array([np.log(1.1)]))]:
        specific = []
        for o in observations:
            fixed = bg.corrected(model, truth, o)
            specific.append(dict(o, anatomyPixels=[bg.apply(p, fixed).tolist() for p in [left, right]]))
        np.testing.assert_allclose(bg.solve(model, specific), truth, atol=1e-7)

    # New roll sequence uses the SAME production atlas/UV path with side-column geometry.
    roll_production = json.loads((production_dir/'roll-projection-reference.json').read_text())
    layout = 'roll-side-columns-v1'
    assert roll_production['referenceLayout'] == layout
    for marker in roll_production['markers']:
        np.testing.assert_allclose(np.array(marker['rigCorners']).reshape(4,3), bg.corners(marker['id'], layout), atol=2e-7)
    roll_checks = []
    for angle in [0, 15, -15]:
        rotated_face = face @ Rotation.from_euler('z', -angle, degrees=True).as_matrix().T
        for eye, p in enumerate([camera(-.035), camera(.035)]):
            image = render(roll_production, atlas, p, rotated_face)
            fitted, check = bg.calibrate_view(image, reference_layout=layout)
            assert bg.decode_sequence(image, fitted) == sequence
            visible, _ = bg.green_markers(image, bg.apply(fitted, rotated_face))
            assert bg.rms(visible-bg.apply(p, rotated_face)) < 1
            roll_checks.append(dict(rollDegrees=angle,eye=eye,**check))
            # Check the full white panels, not only their black tag corners.
            face_pixels = bg.apply(p, rotated_face)
            for tag in roll_production['markers']:
                xyz = np.array(tag['rigCorners']).reshape(4,3)
                white = xyz.mean(0)+(xyz-xyz.mean(0))*8/6
                polygon = bg.apply(p,white).astype(np.float32)
                assert all(cv2.pointPolygonTest(polygon,tuple(point),True) < -10 for point in face_pixels)
            if angle == 15:
                cv2.imwrite(str(output/f'roll-left-ear-eye{eye}.png'),image)
    roll_event = dict(evidence, **{key:roll_production[key] for key in ['referenceLayout','markers','clearFaceRegion']})
    roll_event['automatic'] = dict(evidence['automatic'],captureSequence='roll-only-v1',rollBaselineHeadToStage=np.eye(4).ravel().tolist())
    timeline.write_text(json.dumps(dict(event='projection_reference',details=roll_event))+'\n')
    for eye,p in enumerate([left,right]):
        cv2.imwrite(str(output/f'roll-observe-eye{eye}.png'),render(roll_production,atlas,p,face))
    roll_args=SimpleNamespace(**{**vars(args),'left':output/'roll-observe-eye0.png','right':output/'roll-observe-eye1.png','reference_layout':layout,'output':output/'roll-observation.json'})
    bg.observe(roll_args)
    assert json.loads(roll_args.output.read_text())['referenceLayout']==layout
    # Corrected face markers move; independent reference geometry retains the capture head.
    shifted_face = face + [0, -.040, 0]
    shifted_event = dict(roll_event, rigToStage=gauge.ravel().tolist(),
        poseCorrection=dict(id='head-down-40mm-v1', enabled=True, revision=1,
                            headTranslationMetres=[0,-.040,0], cameraRayScale=1),
        faceMarkers=[dict(landmark=i,stageMetres=p.tolist()) for i,p in zip(bg.IDS,bg.apply(gauge,shifted_face))],
        rawFaceMarkers=[dict(landmark=i,stageMetres=p.tolist()) for i,p in zip(bg.IDS,bg.apply(gauge,face))])
    timeline.write_text(json.dumps(dict(event='projection_reference',details=shifted_event))+'\n')
    for eye,p in enumerate([left,right]):
        cv2.imwrite(str(output/f'roll-observe-eye{eye}.png'),render(roll_production,atlas,p,shifted_face))
    bg.observe(roll_args)
    shifted_observation=json.loads(roll_args.output.read_text())
    np.testing.assert_allclose(shifted_observation['baselineRigMetres'],face,atol=1e-7)
    np.testing.assert_allclose(shifted_observation['renderedRigMetres'],shifted_face,atol=1e-7)
    assert np.mean(shifted_observation['renderedRmsPx']) < np.mean(shifted_observation['baselineRmsPx'])
    assert max(shifted_observation['greenCheckRmsPx']) < 1
    invalid=dict(shifted_event);invalid.pop('rawFaceMarkers')
    timeline.write_text(json.dumps(dict(event='projection_reference',details=invalid))+'\n')
    rejected(lambda:bg.observe(roll_args))
    invalid=dict(shifted_event,poseCorrection={**shifted_event['poseCorrection'],'headTranslationMetres':[0,-.080,0]})
    timeline.write_text(json.dumps(dict(event='projection_reference',details=invalid))+'\n')
    rejected(lambda:bg.observe(roll_args))

    # A journal/image layout disagreement must never be silently accepted.
    timeline.write_text(json.dumps(dict(event='projection_reference',details=evidence))+'\n')
    rejected(lambda:bg.observe(roll_args))

    result = dict(status='PASS', boundary='Synthetic renderer uses V origin observed in real 7271d44e recording; corrected APK hardware capture still pending',
        poseCorrectionRawAndRenderedSeparation='PASS', correctedCaptureMissingRawGeometryRejected='PASS', unsupportedPoseCorrectionRejected='PASS',
        rollSideColumns=roll_checks, rollFaceReferenceClearance='PASS', rollEndToEndAssociation='PASS', wrongLayoutRejected='PASS',
        legacyAtlasFailureReproduced='PASS', faceMarkerTextureSampling='PASS',
        productionReferenceGeometry='PASS', productionAtlasArUco='PASS', fullSequenceCRC='PASS',
        allThreeDepths='PASS', fittedProjectionChecks=checks, planarRejection='PASS',
        crcCorruptionRejection='PASS', missingReferenceRejection='PASS', coordinateGauge='PASS',
        stereoTriangulation='PASS', impossibleStereoCorrespondence='PASS', endToEndJournalAssociation='PASS',
        translationAndRayScaleSeparation='PASS', recoveredParameters=recovered.tolist(),
        tenHeldOutPoseFits='PASS')
    (output/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    validate(args.production, args.output)
