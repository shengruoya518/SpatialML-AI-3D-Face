"""Face-independent source calibration and recorded-eye board registration.

All dimensions are measured, K is frozen before observation, and eye projection is
fit ONLY from virtual references. Never writes device calibration or original captures.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

import binocular_geometry as stereo

# Offline measurement should be reproducible across hosts and independent of OpenCL caches.
cv2.ocl.setUseOpenCL(False)

PATTERN = (8, 6)
CV_TO_CAMERA = np.diag([1., -1., -1., 1.])
KINDS = ('board-check-v1', 'board-source-views-v1', 'board-registration-v1')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def read_board(path):
    board = json.loads(Path(path).read_text())
    if board.get('innerCorners') != list(PATTERN):
        raise ValueError('Board must have 8 x 6 inner corners')
    spans = np.array([board['fiveSquareHorizontalMm'], board['fiveSquareVerticalMm']], dtype=float)
    if not np.isfinite(spans).all() or (spans < 25).any() or (spans > 1000).any():
        raise ValueError('Enter measured five-square spans in millimetres')
    if not board.get('boardId') or not board.get('orientationLabel'):
        raise ValueError('Give the measured board an ID and describe its physical orientation label')
    # Support measured anisotropic printing explicitly instead of hiding it in camera focal length.
    board['spacingMetresXY'] = (spans / 5000).tolist()
    return board


def object_points(board):
    grid = np.mgrid[0:8, 0:6].T.reshape(-1, 2).astype(float)
    return np.column_stack([grid * board['spacingMetresXY'], np.zeros(48)])


def read_regions(args):
    path = getattr(args, 'regions', None)
    if path is None:
        return {}
    regions = json.loads(Path(path).read_text())
    if not isinstance(regions, dict) or set(regions) - {'source', 'eye0', 'eye1'}:
        raise ValueError('Regions must map source, eye0 or eye1 to [x0, y0, x1, y1] pixels')
    return regions


def detect(image, identity=None, roi=None):
    if image is None:
        raise ValueError('Missing board image')
    offset = np.zeros(2)
    search = image
    if roi is not None:
        bounds = np.asarray(roi, dtype=float)
        height, width = image.shape[:2]
        if (bounds.shape != (4,) or not np.isfinite(bounds).all()
                or not np.equal(bounds, np.floor(bounds)).all()):
            raise ValueError('Board ROI must be four finite integer pixel bounds [x0, y0, x1, y1]')
        x0, y0, x1, y1 = bounds.astype(int)
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError('Board ROI must lie inside the original image with positive width and height')
        search = image[y0:y1, x0:x1]
        offset = np.array([x0, y0])
    ok, found = cv2.findChessboardCornersSB(cv2.cvtColor(search, cv2.COLOR_BGR2GRAY), PATTERN,
        flags=cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY)
    if not ok:
        raise ValueError('All 48 board corners were not detected')
    # ROI selection uses the visible physical board only, never predicted registration.
    # Detection, identity anchors, overlays and residuals all use original image pixels.
    points = found.reshape(6, 8, 2).astype(float) + offset
    if identity is None:
        return points.reshape(-1, 2)
    anchors = np.asarray([identity['origin'], identity['rowEnd']], dtype=float)
    if anchors.shape != (2, 2) or not np.isfinite(anchors).all():
        raise ValueError('Identity needs pixel origin and rowEnd, beside the physical top-left/top-right labels')
    options = [points, points[::-1, ::-1], points[:, ::-1], points[::-1]]
    scores = [np.linalg.norm(g[0, [0, 7]] - anchors, axis=1).max() for g in options]
    selected = options[int(np.argmin(scores))]
    spacing = np.median(np.linalg.norm(np.diff(selected, axis=1), axis=2))
    if min(scores) > spacing * .45:
        raise ValueError('Identity anchors do not match the two physical row endpoints')
    return selected.reshape(-1, 2)


def draw(image, observed, predicted=None):
    canvas = image.copy()
    for i, (x, y) in enumerate(observed):
        p = tuple(np.rint([x, y]).astype(int))
        cv2.circle(canvas, p, 3, (0, 255, 0), -1)
        if i in (0, 7, 40, 47):
            cv2.putText(canvas, str(i), (p[0]+5, p[1]-5), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 255), 1)
        if predicted is not None:
            q = tuple(np.rint(predicted[i]).astype(int))
            cv2.line(canvas, p, q, (0, 0, 255), 1)
            cv2.circle(canvas, q, 2, (255, 0, 255), -1)
    return canvas


def rigid(value, name):
    matrix = np.asarray(value, dtype=float).reshape(4, 4)
    if (not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-5)
            or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=.001)
            or not np.isclose(np.linalg.det(matrix[:3, :3]), 1, atol=.001)):
        raise ValueError(f'{name} is not a rigid metre transform')
    return matrix


def pose_candidates(points, xyz, k, distortion, strict=True, max_rms=1.5):
    count, rotations, translations, _ = cv2.solvePnPGeneric(xyz, points, k, distortion, flags=cv2.SOLVEPNP_IPPE)
    candidates = []
    for rotation, translation in zip(rotations, translations):
        matrix = np.eye(4)
        matrix[:3, :3] = cv2.Rodrigues(rotation)[0]
        matrix[:3, 3] = translation.ravel()
        camera_points = stereo.apply(matrix, xyz)
        if (camera_points[:, 2] <= 0).any():
            continue
        projected = cv2.projectPoints(xyz, rotation, translation, k, distortion)[0].reshape(-1, 2)
        candidates.append(dict(matrix=matrix, rms=stereo.rms(projected-points), projected=projected,
                               cameraPoints=camera_points))
    candidates.sort(key=lambda c: c['rms'])
    if count == 0 or not candidates or (max_rms is not None and candidates[0]['rms'] > max_rms):
        raise ValueError('Source-board pose failed positive-depth / 1.5 source-pixel reprojection gate')
    if strict and len(candidates) > 1:
        separation = np.linalg.norm(candidates[0]['cameraPoints']-candidates[1]['cameraPoints'], axis=1).max()
        if candidates[1]['rms']-candidates[0]['rms'] < .15 and separation > .002:
            raise ValueError('Planar pose is ambiguous: take a more oblique board view or establish independent continuity')
    return candidates


def camera_profile(path, sample, board):
    value = json.loads(Path(path).read_text())
    if value.get('coordinateSpace') != 'saved-source-pixels' or value.get('imageSize') != [sample['sourceWidth'], sample['sourceHeight']]:
        raise ValueError('Frozen camera profile must use this saved-source resolution')
    if value.get('fingerprint') != sample['fingerprint'] or value.get('board') != board:
        raise ValueError('Frozen camera profile ROM or measured-board identity mismatch')
    if value.get('sourceStream') != sample.get('sourceStream') or not sample.get('sourceStream'):
        raise ValueError('Frozen calibration belongs to a different source-stream configuration')
    k = np.asarray(value['cameraMatrix'], dtype=float).reshape(3, 3)
    d = np.asarray(value.get('distortion', [0]*5), dtype=float)
    if not np.isfinite(k).all() or not np.isfinite(d).all() or min(k[0, 0], k[1, 1]) <= 0 or not np.allclose(k[2], [0, 0, 1]):
        raise ValueError('Invalid frozen camera profile')
    return k, d, value


def calibration(args):
    board = read_board(args.board)
    xyz = object_points(board).astype(np.float32)
    records, rejected, source_keys = [], [], set()
    region_path = getattr(args, 'source_regions', None)
    regions = json.loads(Path(region_path).read_text()) if region_path is not None else {}
    if not isinstance(regions, dict):
        raise ValueError('Source regions must map sample directory names to [x0, y0, x1, y1] pixels')
    selected_names = set()
    args.output.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.session.glob('*/sample.json')):
        sample = json.loads(path.read_text())
        tag = sample.get('automatic', {})
        if getattr(args, 'run', None) and tag.get('run') != args.run:
            continue
        if tag.get('captureSequence') != 'board-source-views-v1':
            continue
        selected_names.add(path.parent.name)
        try:
            source_contract(sample)
            key = (sample['session'], sample['captureSeconds'])
            if key in source_keys:
                raise ValueError('Repeated camera exposure')
            source_keys.add(key)
            image = cv2.imread(str(path.parent/'source.ppm'))
            points = detect(image, roi=regions.get(path.parent.name)).astype(np.float32)
            if image.shape[:2] != (sample['sourceHeight'], sample['sourceWidth']):
                raise ValueError('Source image resolution does not match metadata')
            records.append(dict(path=path, sample=sample, points=points, image=image, split=tag['board']['split']))
        except (ValueError, KeyError) as error:
            rejected.append(dict(sample=str(path), reason=str(error)))
    write_json(args.output/'rejected.json', rejected)
    if set(regions) - selected_names:
        raise ValueError('Source regions include samples outside the selected board-view run')
    train = [r for r in records if r['split'] == 'fit']
    held = [r for r in records if r['split'] == 'validation']
    if len(train) < 12 or len(held) < 4:
        raise ValueError(f'Need 12 fit and 4 held-out board views; found {len(train)} + {len(held)}; see rejected.json')
    if len({r['sample']['automatic']['run'] for r in records}) != 1 or sorted(r['sample']['automatic']['pose'] for r in records) != list(range(16)):
        raise ValueError('Select exactly one complete 16-view run for calibration')
    fingerprint = train[0]['sample']['fingerprint']
    size = (train[0]['sample']['sourceWidth'], train[0]['sample']['sourceHeight'])
    if any(r['sample']['fingerprint'] != fingerprint or r['image'].shape[1::-1] != size or r['sample'].get('sourceStream') != train[0]['sample'].get('sourceStream') for r in records):
        raise ValueError('Calibration mixes ROMs or source dimensions')
    flags = cv2.CALIB_ZERO_TANGENT_DIST | cv2.CALIB_FIX_K3
    if args.model == 'pinhole':
        flags |= cv2.CALIB_FIX_K1 | cv2.CALIB_FIX_K2
    def fit(rows):
        return cv2.calibrateCamera([xyz]*len(rows), [r['points'] for r in rows], size, None, None, flags=flags)
    pooled, k, d, _, _ = fit(train)
    reports = []
    for row in records:
        c = pose_candidates(row['points'].astype(float), xyz.astype(float), k, d, strict=False, max_rms=None)[0]
        delta = c['projected']-row['points']
        stem = row['path'].parent.name
        cv2.imwrite(str(args.output/f'{stem}.png'), draw(row['image'], row['points'], c['projected']))
        reports.append(dict(sample=str(row['path']), split=row['split'], rmsSavedPixels=c['rms'],
            boardRegionPixels=regions.get(stem),
            centreNormalized=(row['points'].mean(0)/size).tolist(),
            residualPixels=delta.tolist(), cameraFromBoard=c['matrix'].tolist(),
            sourceSha256=digest(row['path'].parent/'source.ppm'), sampleSha256=digest(row['path'])))
    sensitivity = [fit(train[:i]+train[i+1:])[1] for i in range(len(train))]
    k_values = np.array([[a[0, 0], a[1, 1], a[0, 2], a[1, 2]] for a in sensitivity])
    report = dict(schema=1, coordinateSpace='saved-source-pixels', imageSize=list(size),
        model=args.model, cameraMatrix=k.tolist(), distortion=d.ravel().tolist(), fingerprint=fingerprint,
        board=board, sourceStream=train[0]['sample']['sourceStream'], pooledRmsSavedPixels=pooled, views=reports, rejected=rejected,
        sourceRegionsPixels=regions,
        leaveOneViewOutIntrinsicsRangePixels=np.ptp(k_values, axis=0).tolist(),
        gatePassed=pooled <= 1 and max(r['rmsSavedPixels'] for r in reports if r['split']=='validation') <= 1.5,
        status='diagnostic candidate; inspect coverage and sensitivity before freezing; never installed automatically')
    write_json(args.output/'camera-profile.json', report)
    print(json.dumps({key: report[key] for key in ('gatePassed', 'pooledRmsSavedPixels', 'leaveOneViewOutIntrinsicsRangePixels')}, indent=2))


def source_contract(sample):
    if sample.get('automatic', {}).get('captureSequence') not in KINDS or sample.get('mode') != 0:
        raise ValueError('Requires a board capture with Mode A')
    correction = sample.get('poseCorrection', {})
    if correction.get('id') != 'current' or correction.get('enabled') is not False or correction.get('cameraRayScale') != 1 or sample.get('sizeScale') != 1:
        raise ValueError('Board diagnostics require Current position and scale 1')
    if not sample.get('sourceStream'):
        raise ValueError('Source-stream configuration is missing')
    if not sample.get('headStableAtExposure') or not sample.get('exposureHistoryCovered'):
        raise ValueError('Source exposure lacks stable bracketing head history')
    if not np.allclose(np.asarray(sample['imageTransform']).reshape(3, 3), np.eye(3), atol=1e-6):
        raise ValueError('Source path has unexpected image resampling')
    if sample['captureFrame'][3] <= 0 or sample['captureFrame'][4] != 0:
        raise ValueError('Repeated or invalid source exposure')
    age = sample['monotonicSecondsAtReadback']-sample['captureSeconds']
    if not 0 <= age <= .9:
        raise ValueError('Invalid source exposure timestamp or stale capture')
    rigid(sample['headToStageAtCapture'], 'capture head')
    rigid(sample['cameraToHead'], 'camera to head')


def reference_contract(sample, event):
    source_contract(sample)
    if event.get('frame') != sample['sequence'] or abs(event.get('captureSeconds', -1)-sample['captureSeconds']) > 1e-6:
        raise ValueError('Reference and exported exposure identity differ')
    tag = event.get('automatic', {})
    source_tag = sample['automatic']
    if any(tag.get(key) != source_tag.get(key) for key in ('run', 'trial', 'pose', 'epoch', 'phase', 'captureSequence')) or tag.get('phase') != 'MARKED':
        raise ValueError('Reference belongs to another board hold or capture phase')
    if event.get('referenceLayout') != 'roll-side-columns-v1' or event.get('protocol') != stereo.PROTOCOL:
        raise ValueError('Wrong reference protocol or layout')
    if event.get('ownerRoundTripMaxMetres', 1) >= .0001:
        raise ValueError('Reference mesh owner conversion failed')
    h = rigid(sample['headToStageAtCapture'], 'capture head')
    optical = rigid(sample['cameraToHead'], 'optical')
    if not np.allclose(rigid(event['rigToStage'], 'reference head'), h, atol=1e-5):
        raise ValueError('Reference and source head pose differ')
    if not np.allclose(rigid(event['cameraToHead'], 'reference optical'), optical, atol=1e-5):
        raise ValueError('Reference and source optical transform differ')
    if sorted(m.get('id', -1) for m in event['markers']) != list(range(12)):
        raise ValueError('Journal must contain all twelve independent marker geometries')
    for marker in event['markers']:
        local = stereo.corners(marker['id'], 'roll-side-columns-v1')
        if not np.allclose(np.asarray(marker['rigCorners']).reshape(4, 3), local, atol=1e-6) or not np.allclose(np.asarray(marker['stageCorners']).reshape(4, 3), stereo.apply(h, local), atol=1e-5):
            raise ValueError('Logged marker geometry differs from the independent layout')
    upload = event['uploadSeconds']
    if not 0 <= upload-sample['captureSeconds'] <= 2:
        raise ValueError('Reference upload is stale or precedes exposure')
    at_upload = rigid(event['headToStageAtUpload'], 'upload head')
    if np.linalg.norm(at_upload[:3, 3]-h[:3, 3]) > .005:
        raise ValueError('Head moved between source exposure and reference upload')
    angle = np.degrees(np.arccos(np.clip((np.trace(at_upload[:3, :3].T@h[:3, :3])-1)/2, -1, 1)))
    if angle > .5:
        raise ValueError('Head rotated between source exposure and reference upload')
    return h, optical


def compare(xyz, pose, h, optical, cameras, observed):
    stage = stereo.apply(h @ optical @ CV_TO_CAMERA @ pose, xyz)
    prediction = [stereo.apply(p @ np.linalg.inv(h), stage) for p in cameras]
    errors = [p - o for p, o in zip(prediction, observed)]
    return stage, prediction, [dict(rmsPixels=stereo.rms(e), meanXYPixels=e.mean(0).tolist(),
        maxPixels=float(np.linalg.norm(e, axis=1).max()), residualPixels=e.tolist()) for e in errors]


def capture_evidence(args):
    sample = json.loads(args.sample.read_text())
    source_contract(sample)
    pair = json.loads((args.pair/'pair.json').read_text())
    if pair.get('viewIds') != [0, 1] or 'pts' not in pair or 'timeBase' not in pair:
        raise ValueError('Need a same-PTS stereo pair with original view IDs')
    images = [cv2.imread(str(args.pair/f'eye{i}.png')) for i in (0, 1)]
    if any(image is None for image in images) or images[0].shape != images[1].shape:
        raise ValueError('Missing or unequal recorded eye images')
    if pair.get('eyeSha256') != [digest(args.pair/f'eye{i}.png') for i in (0, 1)]:
        raise ValueError('Pair lacks verified image hashes; extract with this tool')
    cameras, gates, sequences = [], [], []
    for image in images:
        camera, gate = stereo.calibrate_view(image, reference_layout='roll-side-columns-v1')
        cameras.append(camera)
        gates.append(gate)
        sequences.append(stereo.decode_sequence(image, camera))
    if sequences != [sample['sequence']]*2:
        raise ValueError(f'Both eye frame codes must equal source sequence {sample["sequence"]}, found {sequences}')
    events = [json.loads(line) for line in args.timeline.read_text().splitlines()]
    events = [e['details'] for e in events if e.get('event') == 'projection_reference' and e.get('details', {}).get('frame') == sample['sequence']]
    if len(events) != 1:
        raise ValueError('Need exactly one journal reference upload for this exported sequence')
    event = events[0]
    h, optical = reference_contract(sample, event)
    source = cv2.imread(str(args.sample.parent/'source.ppm'))
    if source is None or source.shape[:2] != (sample['sourceHeight'], sample['sourceWidth']):
        raise ValueError('Source image resolution does not match metadata')
    return sample, source, images, pair, cameras, gates, h, optical


def pilot(args):
    args.output.mkdir(parents=True, exist_ok=True)
    sample, source, images, pair, cameras, gates, h, optical = capture_evidence(args)
    regions = read_regions(args)
    for name, image in zip(('source', 'eye0', 'eye1'), [source]+images):
        points = detect(image, roi=regions.get(name))
        cv2.imwrite(str(args.output/f'{name}-corners.png'), draw(image, points))
        write_json(args.output/f'{name}-corners.json', points.tolist())
    write_json(args.output/'pilot.json', dict(status='PILOT_READABLE', sequence=sample['sequence'],
        referenceGates=gates, pair=pair, sampleSha256=digest(args.sample), boardRegionsPixels=regions,
        scope='Board detected in source and both eyes; matching exposure codes, reference fit, and head pose checks passed. No camera calibration or physical alignment acceptance.'))
    print(args.output/'pilot.json')


def observe(args):
    args.output.mkdir(parents=True, exist_ok=True)
    sample = json.loads(args.sample.read_text())
    source_contract(sample)
    board = read_board(args.board)
    xyz = object_points(board)
    k, d, profile = camera_profile(args.camera, sample, board)
    if not profile.get('gatePassed'):
        raise ValueError('Freeze a camera candidate that passed held-out source validation first')
    sample, source, images, pair, cameras, gates, h, optical = capture_evidence(args)
    identity = json.loads(args.identity.read_text())
    regions = read_regions(args)
    source_points = detect(source, identity['source'], regions.get('source'))
    observed = [detect(im, identity[f'eye{i}'], regions.get(f'eye{i}')) for i, im in enumerate(images)]
    candidates = pose_candidates(source_points, xyz, k, d)
    pose = candidates[0]['matrix']
    stage, predictions, errors = compare(xyz, pose, h, optical, cameras, observed)
    triangulated = stereo.triangulate(cameras, observed)
    stereo_errors = [stereo.rms(stereo.apply(p, triangulated)-o) for p, o in zip(cameras, observed)]
    if max(stereo_errors) > 2:
        raise ValueError('Physical board identity or stereo observations are inconsistent (>2px)')
    grid = triangulated.reshape(6, 8, 3)
    spacing = [np.linalg.norm(np.diff(grid, axis=axis), axis=2).ravel() for axis in (1, 0)]
    _, _, vt = np.linalg.svd(triangulated-triangulated.mean(0), full_matrices=False)
    plane = (triangulated-triangulated.mean(0))@vt[-1]
    for i in (0, 1):
        cv2.imwrite(str(args.output/f'eye{i}-residuals.png'), draw(images[i], observed[i], predictions[i]))
    cv2.imwrite(str(args.output/'source-residuals.png'), draw(source, source_points, candidates[0]['projected']))
    report = dict(schema=1, sequence=sample['sequence'], captureSeconds=sample['captureSeconds'],
        session=sample['session'], run=sample['automatic']['run'], pose=sample['automatic']['pose'],
        poseLabel=sample['automatic']['poseLabel'], group=identity['group'],
        placement=identity.get('placement', {}), board=board, referenceGates=gates, eyes=errors,
        boardRegionsPixels=regions,
        cameraFromBoard=pose.tolist(), headToStage=h.tolist(), cameraToHead=optical.tolist(),
        boardCentreDepthMetres=float(candidates[0]['cameraPoints'][:, 2].mean()),
        predictedStageMetres=stage.tolist(), triangulatedReferenceRigMetres=triangulated.tolist(),
        stereoConsistencyRmsPixels=stereo_errors,
        squareLengthsMeanXYMetres=[float(a.mean()) for a in spacing],
        squareLengthsStdXYMetres=[float(a.std()) for a in spacing],
        planarityRmsMetres=float(np.sqrt(np.mean(plane**2))),
        sourceRmsPixels=candidates[0]['rms'], planarCandidateRmsPixels=[c['rms'] for c in candidates],
        withinDiagnosticTarget=all(e['rmsPixels'] <= 3 for e in errors),
        provenance=dict(sampleSha256=digest(args.sample), sourceSha256=digest(args.sample.parent/'source.ppm'),
            cameraSha256=digest(args.camera), boardSha256=digest(args.board), identitySha256=digest(args.identity),
            pair=pair, timelineSha256=digest(args.timeline)),
        limitations=['Static source-to-display assumption requires a fixed board and still wearer.',
            'Camera/head history uses callback timestamps; matching frame codes do not timestamp passthrough exposure.',
            'Recorded eyes do not establish final physical display alignment. No correction is fitted or applied.'])
    write_json(args.output/'observation.json', report)
    print(json.dumps(dict(sequence=sample['sequence'], rmsPixelsPerEye=[e['rmsPixels'] for e in errors], withinDiagnosticTarget=report['withinDiagnosticTarget']), indent=2))


def summarize(args):
    rows = [json.loads(path.read_text()) for path in args.observations]
    keys = [(r['session'], r['captureSeconds']) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate exposures cannot count as repeatability evidence')
    if len({r['provenance']['cameraSha256'] for r in rows}) != 1 or len({r['provenance']['boardSha256'] for r in rows}) != 1:
        raise ValueError('Do not pool different camera candidates or measured boards')
    groups = {}
    for name in sorted({r['group'] for r in rows}):
        group = [r for r in rows if r['group'] == name]
        values = np.array([[e['meanXYPixels'] for e in r['eyes']] for r in group])
        groups[name] = dict(exposures=len(group), repeatabilityReady=len(group) >= 3,
            split='held-out' if name in args.held_out else 'development',
            meanXYPixelsPerEye=values.mean(0).tolist(), stdXYPixelsPerEye=values.std(0).tolist(),
            rmsPixelsPerEye=np.sqrt(np.mean([[e['rmsPixels']**2 for e in r['eyes']] for r in group], axis=0)).tolist(),
            depthRangeMetres=[min(r['boardCentreDepthMetres'] for r in group), max(r['boardCentreDepthMetres'] for r in group)])
    if any(name not in groups for name in args.held_out):
        raise ValueError('Named held-out group has no observations')
    write_json(args.output, dict(groups=groups, heldOutGroups=args.held_out,
        note='Fixed-transform diagnostics; held-out groups are reserved before any future correction fit.'))
    print(args.output)


def extract(args):
    stereo.extract(args)
    path = args.output/'pair.json'
    value = json.loads(path.read_text())
    value['eyeSha256'] = [digest(args.output/f'eye{i}.png') for i in (0, 1)]
    write_json(path, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    cal = commands.add_parser('calibrate')
    for name in ('session', 'board', 'output'):
        cal.add_argument('--'+name, type=Path, required=True)
    cal.add_argument('--run', help='Select one run when a session contains repeated 16-view sets')
    cal.add_argument('--model', choices=['pinhole', 'radial-k1-k2'], default='pinhole')
    cal.add_argument('--source-regions', type=Path,
        help='Optional JSON visible-board crops keyed by sample directory; corners remain in full-image pixels')
    cal.set_defaults(action=calibration)
    pilot_parser = commands.add_parser('pilot')
    for name in ('sample', 'timeline', 'pair', 'output'):
        pilot_parser.add_argument('--'+name, type=Path, required=True)
    pilot_parser.set_defaults(action=pilot)
    pilot_parser.add_argument('--regions', type=Path, help='Optional JSON image-space board crops: source/eye0/eye1 -> [x0,y0,x1,y1]')
    obs = commands.add_parser('observe')
    for name in ('sample', 'timeline', 'pair', 'board', 'camera', 'identity', 'output'):
        obs.add_argument('--'+name, type=Path, required=True)
    obs.set_defaults(action=observe)
    obs.add_argument('--regions', type=Path, help='Optional JSON image-space board crops; identity remains in full-image pixels')
    dec = commands.add_parser('extract')
    dec.add_argument('--video', type=Path, required=True)
    dec.add_argument('--seconds', type=float, required=True)
    dec.add_argument('--output', type=Path, required=True)
    dec.set_defaults(action=extract)
    detect_parser = commands.add_parser('detect')
    detect_parser.add_argument('--image', type=Path, required=True)
    detect_parser.add_argument('--output', type=Path, required=True)
    detect_parser.add_argument('--roi', type=int, nargs=4, metavar=('X0', 'Y0', 'X1', 'Y1'),
        help='Optional visible-board crop in original image pixels')
    def detection(args):
        im = cv2.imread(str(args.image))
        points = detect(im, roi=args.roi)
        args.output.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.output/'corners.png'), draw(im, points))
        write_json(args.output/'corners.json', dict(points=points.tolist(), boardRegionPixels=args.roi,
            instruction='Use the physical label to confirm origin and rowEnd (first and last internal corners of physical top row).'))
    detect_parser.set_defaults(action=detection)
    summary = commands.add_parser('summarize')
    summary.add_argument('--observations', type=Path, nargs='+', required=True)
    summary.add_argument('--held-out', nargs='+', required=True)
    summary.add_argument('--output', type=Path, required=True)
    summary.set_defaults(action=summarize)
    args = parser.parse_args()
    args.action(args)


if __name__ == '__main__':
    main()
