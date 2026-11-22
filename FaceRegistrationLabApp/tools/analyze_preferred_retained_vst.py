"""Analyze the retained-frame CPU/GPU benchmark without any device calls."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import re
import statistics

from analyze_pipeline_journal import stats
from analyze_spatialml_trace import analyze as analyze_trace


WARMUP = 5
PIPELINE_ORDER = ['detector', 'landmark_fit', 'expressions', 'output_7']
PACKET_BYTES = 6332


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def eligible(frame):
    return (
        frame['hasFace']
        and frame['freshCameraFrame']
        and not frame['rejection']
        and -.1 <= frame['cameraAgeAtReadbackSeconds'] <= 2
    )


def summarize(frames, scenes):
    faces = [frame for frame in frames if eligible(frame)]
    paired = [
        (frame, scenes[frame['frame']])
        for frame in faces
        if frame['frame'] in scenes and scenes[frame['frame']].get('visible')
    ]
    cadence = [
        (following['submitSeconds'] - current['submitSeconds']) * 1000
        for current, following in zip(frames, frames[1:])
    ]
    return {
        'frames': len(frames),
        'eligibleFaceFrames': len(faces),
        'submitToReadbackMs': stats(frame['submitToReadbackSeconds'] * 1000 for frame in faces),
        'cameraAgeAtReadbackMs': stats(frame['cameraAgeAtReadbackSeconds'] * 1000 for frame in faces),
        'appDecodeMs': stats(frame['appDecodeSeconds'] * 1000 for frame in faces),
        'appRegistrationMs': stats(frame['appRegistrationSeconds'] * 1000 for frame in faces),
        'readbackToMeshUploadMs': stats(
            (scene['uploadNanos'] / 1e9 - frame['readbackSeconds']) * 1000 for frame, scene in paired
        ),
        'cameraAgeAtMeshUploadMs': stats(
            (scene['uploadNanos'] / 1e9 - frame['captureSeconds']) * 1000 for frame, scene in paired
        ),
        'submitIntervalMs': stats(cadence),
        'completionHz': 1000 / statistics.fmean(cadence) if cadence else None,
        'noFaceFrames': sum(not frame['hasFace'] for frame in frames),
        'unfreshFrames': sum(not frame['freshCameraFrame'] for frame in frames),
        'rejections': dict(Counter(frame['rejection'] for frame in frames if frame['rejection'])),
    }


def description(pipeline, name, index, variant):
    known = {
        'RetainedVSTAccess': 'Acquire one full-resolution exposure, retain its hardware buffer, and affine-sample the 256x256 detector RGB image',
        'RetainedVSTRoi': 'Copy only the bounded rotated landmark ROI extent into a zero-padded 768x768 RGB tile and adjust its affine',
        'lab_camera': 'Select effective calibration intrinsics',
        'CameraSpaceToWorld': 'Resolve the left camera pose at the exposure timestamp',
        'face_detector': 'Infer detector boxes and confidence scores',
        'decode_detection': 'Decode detector tensors and construct the face ROI',
        'prepare_roi': 'Update current ROI and tracking state',
        'lab_frame_snapshot': 'Copy producer calibration evidence',
        'landmark_preprocess_tile_rgb_gpu': 'GPU affine-sample the retained RGB tile, round pixels, and normalize landmark input',
        'face_landmarks_detector': 'Infer 478 landmark triplets and presence',
        'track_landmarks': 'Validate landmarks, update tracking, and prepare 33 fit points',
        'face_fit_inline': 'Run three inline fits, rotations, unprojections, scales, and pose',
        'face_pose': 'Transform/filter pose and feed tracker validity',
        'registration_diagnostics': 'Compute fit/reprojection quality and tracker feedback',
        'lab_geometry_snapshot': 'Copy sparse fit calibration evidence',
        'face_blend_input': 'Gather and normalize expression input points',
        'face_blendshapes': 'Infer 52 blendshape scores',
        'face_output_7': 'Pack pose, mesh, and blendshapes into the final packet',
        'lab_capture_marker': 'Publish terminal completion sequence',
    }
    if name == 'lab_affine':
        return 'Compose the detector affine with the lab image transform' if pipeline == 'detector' else 'Compose the landmark affine with the lab image transform'
    if pipeline == 'detector' and name == 'Assignment':
        return 'Convert the 256x256 detector RGB bytes to float'
    if pipeline == 'detector' and name == 'Arithmetic':
        return 'Normalize the detector float pixels to 0..1'
    if pipeline == 'landmark_fit' and variant == 'cpu' and name == 'ApplyAffine':
        return 'Native CPU affine-sample the 768x768 RGB tile into the 256x256 landmark crop'
    if pipeline == 'landmark_fit' and variant == 'cpu' and name == 'Assignment':
        return 'Convert the sampled landmark crop from RGB bytes to float'
    if pipeline == 'landmark_fit' and variant == 'cpu' and name == 'Arithmetic':
        return 'Normalize the landmark float pixels to 0..1'
    if pipeline == 'landmark_fit' and variant == 'gpu' and name == 'Arithmetic':
        return 'Reconstruct byte-valued diagnostic crop from normalized GPU output'
    if pipeline == 'landmark_fit' and variant == 'gpu' and name == 'Assignment':
        return 'Convert the reconstructed diagnostic crop to uint8'
    return known.get(name, f'{pipeline} operator {index}: {name}')


def clock_anchors(data, client_pid):
    anchors = []
    records = []
    for log in sorted(data.glob('*.log')):
        for line in log.read_text(errors='replace').splitlines():
            if 'face_frame seq=' not in line:
                continue
            match = re.match(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{6})\s+(\d+)\s+', line)
            if not match or int(match[2]) != client_pid:
                continue
            fields = dict(re.findall(r'(\w+)=([^\s]+)', line))
            try:
                capture = float(fields['capture'])
                age = float(fields['capture_age_s'])
                if not -.1 <= age <= 2 or not math.isfinite(capture + age):
                    continue
                epoch = datetime.strptime('2026-' + match[1], '%Y-%m-%d %H:%M:%S.%f').timestamp() * 1000
                offset = epoch - (capture + age) * 1000
                anchors.append(offset)
                records.append({'log': log.name, 'sequence': fields['seq'], 'offsetMs': offset})
            except (KeyError, ValueError):
                continue
    return anchors, records


def analyze(session, layouts):
    data = session / 'performance-data'
    manifest = json.loads((session / 'manifest.json').read_text())
    journals = {}
    windows = []
    raw_windows = {}
    reports = []
    modes = {}
    for item in manifest['windows']:
        window = dict(item)
        window['journal'] = str(data / (item['label'] + '-timeline.jsonl'))
        window['logPath'] = str(data / item['log'])
        windows.append(window)
        path = Path(window['journal'])
        journals.setdefault(path, rows(path))
        journal = journals[path]
        all_frames = [
            row['details']
            for row in journal
            if row['event'] == 'pipeline_frame'
            and window['startFrame'] < row['details']['frame'] <= window['endFrame']
        ]
        frames = all_frames[WARMUP:]
        scenes = {
            row['mesh']['frame']: row['mesh']
            for row in journal
            if row['event'] == 'scene_update_complete'
            and row.get('mesh')
            and window['startFrame'] < row['mesh']['frame'] <= window['endFrame']
        }
        metrics = summarize(frames, scenes)
        metrics.update(window=window, totalFrames=len(all_frames), warmupExcluded=min(WARMUP, len(all_frames)))
        violations = [
            frame['frame']
            for frame in frames
            if frame['outputMask'] != 7
            or frame['resultSchema'] != 2
            or frame['readbackBytes'] != PACKET_BYTES
            or frame['calibrationEvidence']
        ]
        if violations:
            raise AssertionError(f'Packet contract violations: {violations}')
        reports.append(metrics)
        raw_windows[window['label']] = (all_frames, frames, scenes)
        if window['debug'] == '0':
            modes[window['variant']] = metrics

    components = {}
    operation_rows = []
    for window in windows:
        if window['debug'] != '1':
            continue
        variant = window['variant']
        selected = {'lab': [pipe for pipe in layouts[variant]['lab'] if pipe['pipeline'] in PIPELINE_ORDER]}
        traced = analyze_trace(Path(window['logPath']), selected, int(window['clientPid']), skip=0)
        (data / (window['label'] + '-operators.json')).write_text(json.dumps(traced, indent=2) + '\n')
        mapped_pipelines = [pipe for pipe in traced['pipelines'] if pipe['status'] == 'mapped']
        mapped_counts = Counter(pipe['pipeline'] for pipe in mapped_pipelines)
        pipelines = {pipe['pipeline']: pipe for pipe in mapped_pipelines}
        if set(pipelines) != set(PIPELINE_ORDER) or any(count != 1 for count in mapped_counts.values()):
            components[variant] = {
                'error': 'Missing or ambiguous pipeline',
                'observed': dict(sorted(mapped_counts.items())),
                'expected': PIPELINE_ORDER,
            }
            continue
        if len({(pipe['servicePid'], pipe['clientPid']) for pipe in pipelines.values()}) != 1:
            raise AssertionError('Pipeline owner changed during one trace window')
        tasks = {
            name: {str(int(task['task'], 0)): task for task in pipe['taskRecords']}
            for name, pipe in pipelines.items()
        }
        anchors, anchor_records = clock_anchors(data, int(window['clientPid']))
        offset = statistics.median(anchors) if anchors else None
        all_frames, kept_frames, _ = raw_windows[window['label']]
        kept = {frame['frame'] for frame in kept_frames}
        chains = []
        unmatched = 0
        for terminal in tasks[PIPELINE_ORDER[-1]].values():
            chain = {PIPELINE_ORDER[-1]: terminal}
            for name, following in reversed(list(zip(PIPELINE_ORDER, PIPELINE_ORDER[1:]))):
                previous = tasks[name].get(chain[following].get('waitForTask'))
                if previous is None:
                    break
                chain[name] = previous
            if len(chain) != len(PIPELINE_ORDER):
                continue
            ordered = [chain[name] for name in PIPELINE_ORDER]
            if not all(a['runCompleteMs'] <= b['runStartMs'] for a, b in zip(ordered, ordered[1:])):
                continue
            if offset is None:
                continue
            start = (ordered[0]['runStartMs'] - offset) / 1000
            end = (ordered[-1]['runCompleteMs'] - offset) / 1000
            candidates = [
                frame
                for frame in all_frames
                if frame['submitSeconds'] - .01 <= start < frame['readbackSeconds']
                and frame['submitSeconds'] <= end <= frame['readbackSeconds'] + .01
            ]
            if len(candidates) != 1:
                unmatched += 1
                continue
            frame = candidates[0]
            if frame['frame'] not in kept or not eligible(frame):
                continue
            elapsed = ordered[-1]['runCompleteMs'] - ordered[0]['runStartMs']
            execution = sum(task['runCompleteMs'] - task['runStartMs'] for task in ordered)
            operator = sum(sum(task['operatorDurationMs']) for task in ordered)
            chains.append(
                {
                    'frame': frame['frame'],
                    'tasks': {name: task['task'] for name, task in chain.items()},
                    'operatorMs': operator,
                    'withinTaskOverheadMs': execution - operator,
                    'interTaskGapMs': elapsed - execution,
                    'outsideServiceSpanMs': frame['submitToReadbackSeconds'] * 1000 - elapsed,
                    'submitToReadbackMs': frame['submitToReadbackSeconds'] * 1000,
                }
            )
        if len({chain['frame'] for chain in chains}) != len(chains):
            raise AssertionError('Duplicate frame/chain association')
        for pipeline_name in PIPELINE_ORDER:
            pipeline = pipelines[pipeline_name]
            specification = next(pipe for pipe in selected['lab'] if pipe['pipeline'] == pipeline_name)
            for operator in pipeline['operators']:
                values = [
                    tasks[pipeline_name][str(int(chain['tasks'][pipeline_name], 0))]['operatorDurationMs'][
                        operator['index']
                    ]
                    for chain in chains
                ]
                operation_rows.append(
                    {
                        'variant': variant,
                        'order': sum(
                            len(next(pipe for pipe in selected['lab'] if pipe['pipeline'] == prior)['operators'])
                            for prior in PIPELINE_ORDER[: PIPELINE_ORDER.index(pipeline_name)]
                        )
                        + operator['index']
                        + 1,
                        'pipeline': pipeline_name,
                        'index': operator['index'],
                        'name': operator['name'],
                        'kind': operator['kind'],
                        'description': description(
                            pipeline_name, operator['name'], operator['index'], variant
                        ),
                        **stats(values),
                    }
                )
            if len(specification['operators']) != len(pipeline['operators']):
                raise AssertionError('Recorded and traced layouts differ')
        components[variant] = {
            'faceChains': len(chains),
            'unmatchedCompleteChains': unmatched,
            'clockAnchorCount': len(anchors),
            'clockOffsetSpreadMs': max(anchors) - min(anchors) if anchors else None,
            'clockAnchors': anchor_records,
            'budget': {
                key: stats(chain[key] for chain in chains)
                for key in (
                    'operatorMs',
                    'withinTaskOverheadMs',
                    'interTaskGapMs',
                    'outsideServiceSpanMs',
                    'submitToReadbackMs',
                )
            },
            'pipelines': {
                name: {'acceptedTasks': pipe['acceptedTasks'], 'exclusions': pipe['exclusions']}
                for name, pipe in pipelines.items()
            },
        }
        (data / (window['label'] + '-face-chains.json')).write_text(json.dumps(chains, indent=2) + '\n')

    result = {
        'warmupFramesPerWindow': WARMUP,
        'windows': reports,
        'modes': modes,
        'components': components,
        'orderedOperations': operation_rows,
        'boundary': 'Tracing-off fresh face frames for end-to-end latency; tracing-on exact wait-for chains uniquely associated to journal frames using clock anchors. GPU timings include wrapper copies and invocation. Upload acknowledgement is not presentation.',
    }
    (data / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    if operation_rows:
        with (data / 'ordered-operations.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(operation_rows[0]))
            writer.writeheader()
            writer.writerows(operation_rows)
    for variant, metrics in modes.items():
        print(
            variant,
            'faces',
            metrics['eligibleFaceFrames'],
            'p50',
            metrics['submitToReadbackMs'].get('p50'),
            'p95',
            metrics['submitToReadbackMs'].get('p95'),
            'Hz',
            metrics['completionHz'],
        )
    for variant, component in components.items():
        print(variant, 'chains', component.get('faceChains'), component.get('error', 'mapped'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--cpu-layout', type=Path, required=True)
    parser.add_argument('--gpu-layout', type=Path, required=True)
    arguments = parser.parse_args()
    analyze(
        arguments.session,
        {
            'cpu': json.loads(arguments.cpu_layout.read_text()),
            'gpu': json.loads(arguments.gpu_layout.read_text()),
        },
    )
