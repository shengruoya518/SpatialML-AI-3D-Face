"""Measure recorded-eye projections independently of the face model, then fit corrections.

observe requires a same-PTS pair from the original MV-HEVC video (decode both view_ids),
and matches the sequence/CRC drawn in the mesh against the session journal. No clock
offset or nominal recording FOV/IPD is substituted for this measurement.
"""
import argparse
import json
import struct
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

PROTOCOL = 'binocular-geometry-v1'
IDS = [33, 133, 362, 263, 1, 61, 291, 152]
LOCATIONS = [(-.34, -.25), (-.34, -.08), (-.34, .09), (-.34, .26),
             (-.16, .26), (.16, .26), (.34, .26), (.34, .09),
             (.34, -.08), (.34, -.25), (-.50, .02), (.50, .02)]
DEPTHS = [.65, 1.15, 2.05]
REFERENCE_LAYOUTS = {
    'original-v1': LOCATIONS,
    'roll-side-columns-v1': [(x, y) for x in [-.44, .44] for y in [-.25, -.15, -.05, .05, .15, .25]],
}


def corners(marker_id, reference_layout="original-v1"):
    z = DEPTHS[marker_id % 3]
    if reference_layout not in REFERENCE_LAYOUTS:
        raise ValueError(f"Unknown reference layout: {reference_layout}")
    x, y = REFERENCE_LAYOUTS[reference_layout][marker_id]
    return np.array([[x-.024, y+.024, -1], [x+.024, y+.024, -1],
                     [x+.024, y-.024, -1], [x-.024, y-.024, -1]]) * z


def apply(matrix, points):
    points = np.asarray(points, dtype=float)
    out = np.column_stack([points, np.ones(len(points))]) @ np.asarray(matrix).T
    return out[:, :-1] / out[:, -1:]


def rms(delta):
    return float(np.sqrt(np.mean(np.sum(np.asarray(delta)**2, axis=-1))))


def normalize(points):
    centre = points.mean(0)
    scale = np.sqrt(points.shape[1]) / np.linalg.norm(points-centre, axis=1).mean()
    matrix = np.eye(points.shape[1]+1)
    matrix[:-1, :-1] *= scale
    matrix[:-1, -1] = -scale*centre
    return apply(matrix, points), matrix


def fit_camera(xyz, uv):
    """Normalized DLT; reject coplanar/ill-conditioned references before fitting a camera."""
    xyz, uv = np.asarray(xyz), np.asarray(uv)
    if len(xyz) < 12 or not np.isfinite(xyz).all() or not np.isfinite(uv).all():
        raise ValueError('Need at least twelve finite 3D/2D corner correspondences')
    x, world = normalize(xyz)
    u, image = normalize(uv)
    x = np.column_stack([x, np.ones(len(x))])
    rows = []
    for point, (a, b) in zip(x, u):
        rows.extend([np.r_[point, np.zeros(4), -a*point],
                     np.r_[np.zeros(4), point, -b*point]])
    _, s, vt = np.linalg.svd(rows, full_matrices=False)
    if s[-2] / s[0] < 1e-5:
        raise ValueError('Reference geometry cannot identify a full projection (degenerate DLT)')
    p = np.linalg.inv(image) @ vt[-1].reshape(3, 4) @ world
    p /= np.linalg.norm(p[2, :3])
    if np.median(np.column_stack([xyz, np.ones(len(xyz))]) @ p[2]) < 0:
        p *= -1
    if (np.column_stack([xyz, np.ones(len(xyz))]) @ p[2] <= 0).any():
        raise ValueError('Fitted projection puts reference points behind the view')
    return p


def calibrate_view(image, mirrored_texture=False, reference_layout="original-v1"):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)
    source = cv2.flip(image, 0) if mirrored_texture else image
    found, ids, _ = detector.detectMarkers(source)
    markers = {}
    if ids is not None:
        for marker_id, points in zip(ids.ravel(), found):
            if 0 <= marker_id < 12:
                if int(marker_id) in markers:
                    raise ValueError('Duplicate reference ID in one view')
                points = points.reshape(4, 2).astype(float)
                if mirrored_texture:
                    points[:, 1] = image.shape[0]-1-points[:, 1]
                    points = points[[3, 2, 1, 0]]
                markers[int(marker_id)] = points
    ids = sorted(markers)
    if len(ids) < 9 or any(sum(i % 3 == depth for i in ids) < 2 for depth in range(3)):
        raise ValueError(f'Need >=9 reference IDs and >=2 at each of 3 depths; found {ids}')
    xyz = np.concatenate([corners(i, reference_layout) for i in ids])
    uv = np.concatenate([markers[i] for i in ids])
    camera = fit_camera(xyz, uv)
    # Hold out whole tags; holding out one corner from the same planar tag is too easy.
    held = []
    for marker_id in ids:
        training = [i for i in ids if i != marker_id]
        candidate = fit_camera(np.concatenate([corners(i, reference_layout) for i in training]),
                               np.concatenate([markers[i] for i in training]))
        held.append(rms(apply(candidate, corners(marker_id, reference_layout)) - markers[marker_id]))
    fit_rms = rms(apply(camera, xyz)-uv)
    if max(held) > 2 or fit_rms > 1.5:
        raise ValueError(f'Renderer projection does not generalize: fit={fit_rms:.3f}, held={max(held):.3f}px')
    return camera, dict(markerIds=ids, fittedRmsPx=fit_rms,
                        leaveOneTagOutRmsPx=held, maxHeldOutRmsPx=max(held))


def checksum(sequence):
    crc = 0
    for byte in sequence.to_bytes(4, 'big'):
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (7 if crc & 128 else 0)) & 255
    return crc


def code_centres():
    return np.array([[(c-5.5)*.013*1.1, (.33+(4-r)*.013)*1.1, -1.1]
                     for r in range(9) for c in range(12)])


def decode_sequence(image, camera):
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    values = []
    for x, y in apply(camera, code_centres()):
        x, y = int(round(x)), int(round(y))
        if not (2 <= x < image.shape[1]-2 and 2 <= y < image.shape[0]-2):
            raise ValueError('Frame code outside the recorded view')
        values.append(np.median(grey[y-1:y+2, x-1:x+2]))
    values = np.array(values).reshape(9, 12)
    r, c = np.indices(values.shape)
    quiet = (r == 0) | (r == 8) | (c == 0) | (c == 11)
    border = ~quiet & ((r == 1) | (r == 7) | (c == 1) | (c == 10))
    white, black = np.median(values[quiet]), np.median(values[border])
    if white-black < 80:
        raise ValueError('Frame code has insufficient contrast')
    bits = values > (white+black)/2
    if not bits[quiet].all() or bits[border].any():
        raise ValueError('Frame code border is occluded or incorrectly projected')
    payload = bits[2:7, 2:10].ravel()
    number = 0
    for bit in payload:
        number = (number << 1) | int(bit)
    sequence, crc = number >> 8, number & 255
    if checksum(sequence) != crc:
        raise ValueError('Frame code checksum mismatch')
    return sequence


def triangulate(cameras, observations):
    result = []
    for point in range(len(observations[0])):
        rows = []
        for p, uv in zip(cameras, observations):
            u, v = uv[point]
            rows.extend([u*p[2]-p[0], v*p[2]-p[1]])
        _, _, vt = np.linalg.svd(rows)
        xyz = vt[-1, :3]/vt[-1, 3]
        fit = least_squares(lambda x: np.concatenate([
            apply(p, [x])[0]-uv[point] for p, uv in zip(cameras, observations)]), xyz)
        if not fit.success or not np.isfinite(fit.x).all():
            raise ValueError('Stereo triangulation failed')
        if any(np.r_[fit.x, 1] @ p[2] <= 0 for p in cameras):
            raise ValueError('Triangulated face is behind one eye')
        result.append(fit.x)
    return np.array(result)


def green_markers(image, projected):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (40, 90, 80), (85, 255, 255))
    count, _, stats, centres = cv2.connectedComponentsWithStats(mask)
    candidates = [centres[i] for i in range(1, count) if 3 <= stats[i, cv2.CC_STAT_AREA] <= 250]
    if len(candidates) < len(projected):
        raise ValueError('Not all face markers are visible')
    distance = np.linalg.norm(np.array(candidates)[None, :, :]-projected[:, None, :], axis=2)
    indices = distance.argmin(1)
    if len(set(indices)) != len(projected) or distance[np.arange(len(indices)), indices].max() > 3:
        raise ValueError('Face marker pixels disagree with the coded geometry (or are occluded)')
    return np.array(candidates)[indices], mask


def infer_anatomy(images, masks, task):
    import mediapipe as mp
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(task)), num_faces=1)
    result = []
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as model:
        for image, mask in zip(images, masks):
            clean = cv2.inpaint(image, cv2.dilate(mask, np.ones((3, 3), np.uint8)), 3, cv2.INPAINT_TELEA)
            faces = model.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                         data=cv2.cvtColor(clean, cv2.COLOR_BGR2RGB)))
            if len(faces.face_landmarks) != 1:
                raise ValueError('Expected exactly one independently detected face in each eye')
            points = faces.face_landmarks[0]
            result.append(np.array([[points[i].x*image.shape[1], points[i].y*image.shape[0]] for i in IDS]))
    return result


def board_check(images, cameras, square_metres):
    """Independent metric control; checkerboard is optional and never silently assumed present."""
    points = []
    for image in images:
        found, grid = cv2.findChessboardCornersSB(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (8, 6))
        if not found:
            return dict(status='NOT_FOUND', squareMetres=square_metres)
        points.append(grid.reshape(-1, 2))
    choices = []
    for right in (points[1], points[1][::-1]):
        try:
            xyz = triangulate(cameras, [points[0], right])
            error = rms(np.concatenate([apply(p, xyz)-uv for p, uv in zip(cameras, [points[0], right])]))
            choices.append((error, xyz))
        except ValueError:
            continue
    if not choices:
        return dict(status='INCONSISTENT', squareMetres=square_metres)
    error, xyz = min(choices, key=lambda pair: pair[0])
    grid = xyz.reshape(6, 8, 3)
    lengths = np.r_[np.linalg.norm(np.diff(grid, axis=0), axis=2).ravel(),
                    np.linalg.norm(np.diff(grid, axis=1), axis=2).ravel()]
    _, _, vh = np.linalg.svd(xyz-xyz.mean(0))
    return dict(status='MEASURED', squareMetres=square_metres, twoViewRmsPx=error,
        medianRecoveredSquareMetres=float(np.median(lengths)),
        squareLengthRmsErrorMetres=float(np.sqrt(np.mean((lengths-square_metres)**2))),
        planeRmsMetres=float(np.sqrt(np.mean(((xyz-xyz.mean(0)) @ vh[-1])**2))),
        limitation='Confirm 8x6 corner identities, printed square size and flatness; this checks recording-layer metric consistency.')


def observe(args):
    images = [cv2.imread(str(p)) for p in [args.left, args.right]]
    if any(image is None for image in images):
        raise ValueError('Cannot read both eye images')
    layout = getattr(args, "reference_layout", "original-v1")
    calibrated = [calibrate_view(image, args.mirrored_texture, layout) for image in images]
    cameras = [pair[0] for pair in calibrated]
    sequences = [decode_sequence(image, p) for image, p in zip(images, cameras)]
    if sequences[0] != sequences[1]:
        raise ValueError(f'Eye views show different mesh uploads: {sequences}')
    events = []
    for line in args.timeline.read_text().splitlines():
        event = json.loads(line)
        if event.get('event') == 'projection_reference' and event['details']['frame'] == sequences[0]:
            events.append(event['details'])
    if len(events) != 1 or events[0].get('protocol') != PROTOCOL:
        raise ValueError('Need exactly one matching geometry upload in the selected session')
    event = events[0]
    if event.get("referenceLayout", "original-v1") != layout:
        raise ValueError("Selected reference layout differs from the matching journal upload")
    if not event.get('headStableAtExposure') or not event.get('exposureHistoryCovered'):
        raise ValueError('Capture-time head history was moving or incomplete')
    if not 0 <= event['uploadSeconds']-event['captureSeconds'] <= .9:
        raise ValueError('Displayed geometry was too old at upload')
    if event['ownerRoundTripMaxMetres'] >= .0001:
        raise ValueError('Mesh owner/Stage conversion failed')
    head = np.array(event['rigToStage']).reshape(4, 4)
    stage = np.array([m['stageMetres'] for m in event['faceMarkers']])
    if [m['landmark'] for m in event['faceMarkers']] != IDS:
        raise ValueError('Face marker identity differs from the capture protocol')
    rendered = apply(np.linalg.inv(head), stage)
    correction = event.get('poseCorrection', {'id': 'current', 'enabled': False})
    if correction.get('id') not in ('current', 'head-down-40mm-v1'):
        raise ValueError('Unknown pose correction in matching journal upload')
    if correction.get('id') == 'head-down-40mm-v1':
        if not correction.get('enabled') or correction.get('cameraRayScale') != 1 or not np.allclose(correction.get('headTranslationMetres', [0,0,0]), [0,-.040,0], atol=1e-7, rtol=0):
            raise ValueError('Inconsistent pose correction')
        raw_markers = event.get('rawFaceMarkers', [])
        if [m['landmark'] for m in raw_markers] != IDS:
            raise ValueError('Corrected capture requires raw marker geometry')
        baseline = apply(np.linalg.inv(head), [m['stageMetres'] for m in raw_markers])
        if np.max(np.abs(rendered-baseline-[0, -.040, 0])) > .0001:
            raise ValueError('Raw and corrected geometry disagree with head offset')
    else:
        if correction.get('enabled'):
            raise ValueError('Inconsistent current pose correction')
        baseline = rendered
    green, masks = [], []
    for image, camera in zip(images, cameras):
        points, mask = green_markers(image, apply(camera, rendered))
        green.append(points); masks.append(mask)
    if args.anatomy:
        data = json.loads(args.anatomy.read_text())
        if data['landmarkIds'] != IDS:
            raise ValueError('Anatomy landmark order differs')
        anatomy = [np.array(data[k], dtype=float) for k in ['left', 'right']]
        source = 'provided 2D correspondences; verify manual/source provenance'
    else:
        anatomy = infer_anatomy(images, masks, args.task)
        source = 'MediaPipe on recorded views after marker inpainting; not physical ground truth'
    if any(p.shape != (8, 2) or not np.isfinite(p).all() for p in anatomy):
        raise ValueError('Need eight finite anatomical points per eye')
    xyz = triangulate(cameras, anatomy)
    irreducible = [apply(p, xyz)-uv for p, uv in zip(cameras, anatomy)]
    report = dict(schema=1, protocol=PROTOCOL, frame=sequences[0],
        session=str(args.timeline.resolve().parent), sourceImages=[str(p.resolve()) for p in [args.left, args.right]],
        automatic=event['automatic'], referenceLayout=layout, rollCapture=event.get("rollCapture"), captureSeconds=event['captureSeconds'],
        anatomySource=source, landmarkIds=IDS, baselineRigMetres=baseline.tolist(),
        renderedRigMetres=rendered.tolist(), poseCorrection=correction,
        anatomyRigMetres=xyz.tolist(), anatomyPixels=[a.tolist() for a in anatomy],
        cameraToHead=event['cameraToHead'], rigToStage=event['rigToStage'],
        cameras=[p.tolist() for p in cameras], projectionChecks=[c[1] for c in calibrated],
        greenCheckRmsPx=[rms(apply(p, rendered)-g) for p, g in zip(cameras, green)],
        baselineRmsPx=[rms(apply(p, baseline)-a) for p, a in zip(cameras, anatomy)],
        renderedRmsPx=[rms(g-a) for g, a in zip(green, anatomy)],
        perPointTwoViewResidualPx=np.sqrt(sum(np.sum(e*e, axis=1) for e in irreducible)/2).tolist(),
        irreducibleTwoViewRmsPx=rms(np.concatenate(irreducible)),
        fitEligible=rms(np.concatenate(irreducible)) <= 2,
        limitation='Recording compositor only. Verify timestamp pairing and anatomy independently; no physical calibration is applied.')
    if getattr(args, 'board_square_metres', None) is not None:
        if not 0 < args.board_square_metres < 1:
            raise ValueError('Invalid measured checkerboard square size')
        report['metricBoard'] = board_check(images, cameras, args.board_square_metres)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['frame', 'baselineRmsPx', 'irreducibleTwoViewRmsPx', 'fitEligible']}))


MODELS = {'identity': (False, False, False), 'translation': (True, False, False),
          'rigid': (True, True, False), 'ray_scale': (False, False, True),
          'rigid_ray_scale': (True, True, True)}


def corrected(model, params, observation):
    translation, rotation, scale = MODELS[model]
    index = 0
    offset = params[index:index+3] if translation else np.zeros(3)
    index += 3 if translation else 0
    rot = Rotation.from_rotvec(params[index:index+3]).as_matrix() if rotation else np.eye(3)
    index += 3 if rotation else 0
    factor = np.exp(params[index]) if scale else 1.0
    optical = np.array(observation['cameraToHead']).reshape(4, 4)
    camera = apply(np.linalg.inv(optical), observation['baselineRigMetres'])
    return apply(optical, camera*factor) @ rot.T + offset


def residual(model, params, observations, weighted=True):
    poses = [o['automatic']['pose'] for o in observations]
    result = []
    for observation in observations:
        xyz = corrected(model, params, observation)
        delta = np.concatenate([apply(p, xyz)-uv for p, uv in zip(observation['cameras'], observation['anatomyPixels'])])
        if weighted:
            delta /= np.sqrt(poses.count(observation['automatic']['pose']))
        result.extend(delta.ravel())
    return np.array(result)


def solve(model, observations):
    t, r, s = MODELS[model]
    limits = ([.15]*3 if t else []) + ([.35]*3 if r else []) + ([.4] if s else [])
    if not limits:
        return np.array([])
    result = least_squares(lambda x: residual(model, x, observations), np.zeros(len(limits)),
                           bounds=(-np.array(limits), limits), loss='soft_l1', f_scale=1)
    if not result.success or np.any(np.abs(result.x)/np.array(limits) > .99):
        raise ValueError(f'{model} failed or reached its diagnostic parameter bound')
    if np.linalg.svd(result.jac, compute_uv=False)[-1] < 1e-5:
        raise ValueError(f'{model} is unidentifiable in these observations')
    return result.x


def fit(args):
    observations = [json.loads(path.read_text()) for path in args.observations]
    if any(o.get('protocol') != PROTOCOL or not o.get('fitEligible') for o in observations):
        raise ValueError('All observations must pass projection, frame-code and two-view consistency checks')
    keys = [(o['session'], o['frame']) for o in observations]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate displayed frames must not receive extra fit weight')
    poses = sorted({o['automatic']['pose'] for o in observations})
    if len(poses) < 5 or not {0, 1, 2}.issubset(poses):
        raise ValueError('Need near/mid/far and at least two orientation holds for held-out-pose validation')
    stability = {}
    for pose in poses:
        group = [o for o in observations if o['automatic']['pose'] == pose]
        times = [o['captureSeconds'] for o in group]
        if len(group) < 3 or max(times)-min(times) < .3:
            raise ValueError('Each pose needs >=3 distinct exposures spanning >=0.3 s to test subject stillness')
        centres = np.array([apply(np.array(o['rigToStage']).reshape(4, 4), o['anatomyRigMetres']).mean(0) for o in group])
        motion = float(np.linalg.norm(centres[:, None]-centres[None, :], axis=2).max())
        if motion > .015:
            raise ValueError(f'Subject/triangulation changed by {motion:.4f} m in pose {pose}; choose a still window')
        stability[str(pose)] = dict(exposures=len(group), spanSeconds=max(times)-min(times), anatomyCentreRangeMetres=motion)
    optical = np.array(observations[0]['cameraToHead'])
    if any(not np.allclose(optical, o['cameraToHead'], atol=1e-6, rtol=0) for o in observations):
        raise ValueError('Do not mix optical calibration profiles in one fit')
    models = {}
    for model in MODELS:
        try:
            params = solve(model, observations)
            by_pose, cv = {}, {}
            for pose in poses:
                held = [o for o in observations if o['automatic']['pose'] == pose]
                training = [o for o in observations if o['automatic']['pose'] != pose]
                by_pose[str(pose)] = rms(residual(model, params, held, False).reshape(-1, 2))
                cv_params = solve(model, training)
                cv[str(pose)] = rms(residual(model, cv_params, held, False).reshape(-1, 2))
            models[model] = dict(parameters=params.tolist(), byPoseRmsPx=by_pose,
                                 heldOutPoseRmsPx=cv, equalPoseMeanRmsPx=float(np.mean(list(cv.values()))))
        except ValueError as error:
            models[model] = dict(rejected=str(error))
    report = dict(protocol=PROTOCOL, status='DIAGNOSTIC_ONLY_NOT_APPLIED', observationCount=len(observations),
        poses=poses, models=models, stillnessChecks=stability,
        equation='headCorrected = R_head * (E_cameraToHead * (s * cameraPoint)) + t_head; then H_capture to Stage',
        parameterOrder='translation xyz metres, rotation xyz axis-angle radians, log(ray scale); omit absent groups',
        limitations=['No nominal IPD/FOV or face anthropometry used to fit recording projections.',
                     'Observed anatomy is an estimate; validate landmarks manually and on a second subject.',
                     'Head-frame fit is an effective correction, not proof of which factory transform is wrong.',
                     'Anatomy motion since exposure remains a confound. Use stationary holds and repeat controls.',
                     'Do not apply a fit unless held-out poses, both eyes, and a new recording improve.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(models, indent=2))


def extract(args):
    import av
    if args.seconds < 0:
        raise ValueError('Recording time must be nonnegative')
    with av.open(str(args.video)) as reader:
        video = reader.streams.video[0]
        video.codec_context.options = {'view_ids': '-1'}
        reader.seek(int(args.seconds/video.time_base), stream=video, backward=True)
        pending = {}
        for frame in reader.decode(video):
            if frame.pts is None or float(frame.pts*video.time_base) < args.seconds:
                continue
            sides = {str(d.type): bytes(d) for d in frame.side_data.values()}
            if 'Type.VIEW_ID' not in sides:
                raise ValueError('Decoder did not expose stereo view IDs; do not analyze mono fallback')
            view = struct.unpack('=i', sides['Type.VIEW_ID'])[0]
            if view not in (0, 1):
                raise ValueError(f'Unexpected view ID {view}')
            pair = pending.setdefault(frame.pts, {})
            pair[view] = frame
            if len(pending) > 30:
                raise ValueError('No matched stereo presentation timestamps')
            if len(pair) == 2:
                args.output.mkdir(parents=True, exist_ok=True)
                for eye in (0, 1):
                    pair[eye].to_image().save(args.output/f'eye{eye}.png')
                (args.output/'pair.json').write_text(json.dumps(dict(video=str(args.video.resolve()),
                    pts=frame.pts, timeBase=str(video.time_base), seconds=float(frame.pts*video.time_base),
                    viewIds=[0, 1], dimensions=[video.width, video.height]), indent=2)+'\n')
                print(args.output)
                return
    raise ValueError('No paired stereo frame at or after the requested time')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    observe_parser = sub.add_parser('observe')
    for name in ['left', 'right', 'timeline', 'output']:
        observe_parser.add_argument('--'+name, type=Path, required=True)
    source = observe_parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--task', type=Path)
    source.add_argument('--anatomy', type=Path)
    observe_parser.add_argument("--reference-layout", choices=REFERENCE_LAYOUTS, default="original-v1")
    observe_parser.add_argument('--mirrored-texture', action='store_true', help='Explicitly diagnose vertically mirrored atlas UVs')
    observe_parser.add_argument('--board-square-metres', type=float, help='Optional measured 8x6-inner-corner physical board control')
    fit_parser = sub.add_parser('fit')
    fit_parser.add_argument('--observations', type=Path, nargs='+', required=True)
    fit_parser.add_argument('--output', type=Path, required=True)
    extract_parser = sub.add_parser('extract')
    extract_parser.add_argument('--video', type=Path, required=True)
    extract_parser.add_argument('--seconds', type=float, required=True)
    extract_parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        {'observe': observe, 'fit': fit, 'extract': extract}[args.command](args)
    except ValueError as error:
        parser.exit(2, f'Rejected: {error}\n')


if __name__ == '__main__':
    main()
