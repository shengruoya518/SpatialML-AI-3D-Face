"""Combine the compact/fused tracing-off and operator-traced headset windows.

This analyzer makes no device calls. It admits only fresh, face-bearing, unrejected schema-2
all-output frames after a five-frame window warmup. Traced service work must form the exact
detector -> landmark_fit -> expressions -> output_7 dependency chain and associate uniquely
with one journal frame through app clock anchors.
"""

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
PACKET_BYTES = 6332
PIPELINE_ORDER = ['detector', 'landmark_fit', 'expressions', 'output_7']
LOG_LINE = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{6})\s+(\d+)\s+')
TRACE_EVENT = re.compile(
    r'SpatialMLDebug pid=(\d+) pipeline=(0x[0-9a-fA-F]+) stage=(\w+)(.*)$'
)
FIELD = re.compile(r'(\w+)=(\S+)')


IMPLEMENTATIONS = {
    ('detector', 'RectifiedVSTAccess', 0): 'Native RectifiedVSTAccess, 336x256 RGB8',
    ('detector', 'RectifiedVSTAccess', 1): 'Native RectifiedVSTAccess, 3248x2464 RGB8',
    ('detector', 'CameraSpaceToWorld', 2): 'Native CameraSpaceToWorld',
    ('detector', 'detector_compact_preprocess_gpu', 3): 'Weightless LiteRT GPU model, backend 1',
    ('detector', 'face_detector', 4): 'Trained LiteRT detector, backend 2',
    ('detector', 'face_detector_control', 5): 'Weightless LiteRT CPU model, backend 0',
    ('landmark_fit', 'landmark_preprocess_rgb_gpu', 0): 'Weightless LiteRT GPU model, backend 1',
    ('landmark_fit', 'face_landmarks_detector', 1): 'Trained LiteRT landmark model, backend 2',
    ('landmark_fit', 'face_landmark_control_lab', 2): 'Weightless LiteRT CPU model, backend 0',
    ('expressions', 'face_blend_input', 0): 'Weightless LiteRT CPU model, backend 0',
    ('expressions', 'face_blendshapes', 1): 'Trained LiteRT blendshape model, backend 2',
    ('output_7', 'face_output_7', 0): 'Weightless LiteRT CPU model, backend 0',
    ('output_7', 'face_completion_marker', 1): 'Weightless LiteRT CPU model, backend 0',
}


DESCRIPTIONS = {
    ('detector', 'RectifiedVSTAccess', 0): 'Acquire an aspect-preserving compact detector view.',
    ('detector', 'RectifiedVSTAccess', 1): 'Acquire the adjacent full-resolution landmark source and authoritative timestamp/intrinsics.',
    ('detector', 'CameraSpaceToWorld', 2): 'Resolve the left optical-camera pose at the full-view timestamp.',
    ('detector', 'detector_compact_preprocess_gpu', 3): 'Crop columns 40 through 295, convert only the 256x256 crop to float, and normalize.',
    ('detector', 'face_detector', 4): 'Infer 896 detector boxes and scores.',
    ('detector', 'face_detector_control', 5): 'Decode detections and fuse ranking, ROI, affine, calibration, clock/state, and producer snapshot work.',
    ('landmark_fit', 'landmark_preprocess_rgb_gpu', 0): 'Affine-sample the full RGB8 source and normalize one 256x256 landmark input.',
    ('landmark_fit', 'face_landmarks_detector', 1): 'Infer 478 XYZ landmarks and face presence.',
    ('landmark_fit', 'face_landmark_control_lab', 2): 'Fuse landmark validation/tracking, three Horn/Jacobi fits, pose, diagnostics, feedback, and lab snapshot.',
    ('expressions', 'face_blend_input', 0): 'Gather and normalize the 146 expression input points.',
    ('expressions', 'face_blendshapes', 1): 'Infer 52 blendshape scores.',
    ('output_7', 'face_output_7', 0): 'Pack pose, mesh, and blendshapes into the selected 6332-byte final packet.',
    ('output_7', 'face_completion_marker', 1): 'Publish the terminal sequence only after the final packet is complete.',
}


def json_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def eligible(frame):
    return (
        frame['outputMask'] == 7
        and frame['resultSchema'] == 2
        and frame['readbackBytes'] == PACKET_BYTES
        and not frame['calibrationEvidence']
        and frame['hasFace']
        and frame['freshCameraFrame']
        and not frame['rejection']
        and -.1 <= frame['cameraAgeAtReadbackSeconds'] <= 2
    )


def load_window(session):
    manifest = json.loads((session / 'manifest.json').read_text())
    if len(manifest['windows']) != 1:
        raise AssertionError(f'Expected one window in {session}, found {len(manifest["windows"])}')
    window = dict(manifest['windows'][0])
    data = session / 'performance-data'
    journal_path = data / f'{window["label"]}-timeline.jsonl'
    log_path = data / window['log']
    rows = json_rows(journal_path)
    all_frames = [
        row['details']
        for row in rows
        if row['event'] == 'pipeline_frame'
        and window['startFrame'] < row['details']['frame'] <= window['endFrame']
    ]
    frames = all_frames[WARMUP:]
    scenes = {
        row['mesh']['frame']: row['mesh']
        for row in rows
        if row['event'] == 'scene_update_complete'
        and row.get('mesh')
        and window['startFrame'] < row['mesh']['frame'] <= window['endFrame']
    }
    return {
        'session': session,
        'manifest': manifest,
        'window': window,
        'journalPath': journal_path,
        'logPath': log_path,
        'allFrames': all_frames,
        'frames': frames,
        'scenes': scenes,
    }


def summarize_window(data):
    frames = data['frames']
    faces = [frame for frame in frames if eligible(frame)]
    paired = [
        (frame, data['scenes'][frame['frame']])
        for frame in faces
        if frame['frame'] in data['scenes'] and data['scenes'][frame['frame']].get('visible')
    ]
    intervals = [
        (following['submitSeconds'] - current['submitSeconds']) * 1000
        for current, following in zip(frames, frames[1:])
    ]
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
    return {
        'window': data['window'],
        'totalFrames': len(data['allFrames']),
        'warmupExcluded': min(WARMUP, len(data['allFrames'])),
        'analyzedFrames': len(frames),
        'eligibleFaceFrames': len(faces),
        'detectorFrames': sum(frame['detector'] for frame in frames),
        'trackingFrames': sum(not frame['detector'] for frame in frames),
        'noFaceFrames': sum(not frame['hasFace'] for frame in frames),
        'unfreshFrames': sum(not frame['freshCameraFrame'] for frame in frames),
        'rejections': dict(Counter(frame['rejection'] for frame in frames if frame['rejection'])),
        'packetContractViolations': violations,
        'submitToReadbackMs': stats(frame['submitToReadbackSeconds'] * 1000 for frame in faces),
        'submitMinusExposureMs': stats(
            (frame['submitSeconds'] - frame['captureSeconds']) * 1000 for frame in faces
        ),
        'cameraAgeAtReadbackMs': stats(frame['cameraAgeAtReadbackSeconds'] * 1000 for frame in faces),
        'appDecodeMs': stats(frame['appDecodeSeconds'] * 1000 for frame in faces),
        'appRegistrationMs': stats(frame['appRegistrationSeconds'] * 1000 for frame in faces),
        'submitToAppResultReadyMs': stats(
            (
                frame['submitToReadbackSeconds']
                + frame['appDecodeSeconds']
                + frame['appRegistrationSeconds']
            )
            * 1000
            for frame in faces
        ),
        'readbackToMeshUploadMs': stats(
            (scene['uploadNanos'] / 1e9 - frame['readbackSeconds']) * 1000
            for frame, scene in paired
        ),
        'cameraAgeAtMeshUploadMs': stats(
            (scene['uploadNanos'] / 1e9 - frame['captureSeconds']) * 1000
            for frame, scene in paired
        ),
        'presentationPairCount': len(paired),
        'submitIntervalMs': stats(intervals),
        'completionHz': 1000 / statistics.fmean(intervals) if intervals else None,
        'boundary': 'Tracing-off terminal readback and app upload acknowledgement; upload is not compositor presentation.',
    }


def infer_handle_map(log_path, client_pid):
    evidence = defaultdict(lambda: {'operatorCounts': Counter(), 'placeholderCounts': Counter()})
    for line in log_path.read_text(errors='replace').splitlines():
        match = TRACE_EVENT.search(line)
        if not match or int(match[1]) != client_pid:
            continue
        fields = dict(FIELD.findall(match[4]))
        handle = match[2]
        if match[3] == 'pipeline_load_summary' and 'operator_count' in fields:
            evidence[handle]['operatorCounts'][int(fields['operator_count'])] += 1
        elif match[3] == 'submit' and 'placeholder_count' in fields:
            evidence[handle]['placeholderCounts'][int(fields['placeholder_count'])] += 1
    expected = {
        (6, 17): 'detector',
        (3, 23): 'landmark_fit',
        (2, 3): 'expressions',
        (2, 14): 'output_7',
    }
    mapping = {}
    records = {}
    for handle, counts in evidence.items():
        operator_counts = list(counts['operatorCounts'])
        placeholder_counts = list(counts['placeholderCounts'])
        if len(operator_counts) != 1 or len(placeholder_counts) != 1:
            raise AssertionError(f'Unstable handle signature for {handle}: {counts}')
        signature = (operator_counts[0], placeholder_counts[0])
        if signature not in expected:
            raise AssertionError(f'Unexpected handle signature for {handle}: {signature}')
        pipeline = expected[signature]
        if pipeline in mapping.values():
            raise AssertionError(f'Duplicate pipeline signature for {pipeline}')
        mapping[handle] = pipeline
        records[handle] = {
            'pipeline': pipeline,
            'operatorCount': signature[0],
            'placeholderCount': signature[1],
            'loadSummaryEvents': counts['operatorCounts'][signature[0]],
            'submitEvents': counts['placeholderCounts'][signature[1]],
        }
    if set(mapping.values()) != set(PIPELINE_ORDER):
        raise AssertionError(f'Incomplete handle mapping: {mapping}')
    return mapping, records


def clock_anchors(log_path, client_pid, year):
    anchors = []
    records = []
    for line in log_path.read_text(errors='replace').splitlines():
        if 'face_frame seq=' not in line:
            continue
        match = LOG_LINE.match(line)
        if not match or int(match[2]) != client_pid:
            continue
        fields = dict(FIELD.findall(line))
        try:
            capture = float(fields['capture'])
            age = float(fields['capture_age_s'])
            if not -.1 <= age <= 2 or not math.isfinite(capture + age):
                continue
            wall_ms = datetime.strptime(
                f'{year}-' + match[1], '%Y-%m-%d %H:%M:%S.%f'
            ).timestamp() * 1000
            offset = wall_ms - (capture + age) * 1000
            anchors.append(offset)
            records.append(
                {'sequence': int(fields['seq']), 'offsetMs': offset, 'captureAgeSeconds': age}
            )
        except (KeyError, ValueError):
            continue
    return anchors, records


def delegate_evidence(data, service_pid, client_pid):
    path = data['session'] / 'performance-data' / 'session-continuous.log'
    delegated = []
    models = []
    delegate_pattern = re.compile(
        r'Replacing (\d+) out of (\d+) node\(s\) with delegate \(LITERT_CL\) node, '
        r'yielding (\d+) partitions'
    )
    for line in path.read_text(errors='replace').splitlines():
        outer = LOG_LINE.match(line)
        if not outer or int(outer[2]) != service_pid:
            continue
        match = delegate_pattern.search(line)
        if match:
            delegated.append(
                {
                    'delegatedNodes': int(match[1]),
                    'totalNodes': int(match[2]),
                    'partitions': int(match[3]),
                }
            )
        event = TRACE_EVENT.search(line)
        if event and int(event[1]) == client_pid and event[3] == 'model_operator_create':
            fields = dict(FIELD.findall(event[4]))
            if fields.get('backend') == 'GPU':
                models.append(fields.get('model'))
    expected_models = {'detector_compact_preprocess_gpu', 'landmark_preprocess_rgb_gpu'}
    if set(models) != expected_models:
        raise AssertionError(f'Unexpected GPU model creation evidence: {models}')
    signatures = {(item['delegatedNodes'], item['totalNodes'], item['partitions']) for item in delegated}
    if not {(3, 3, 1), (68, 68, 1)} <= signatures:
        raise AssertionError(f'Missing complete OpenCL delegation evidence: {delegated}')
    return {
        'log': str(path),
        'modelsCreatedWithGpuBackend': models,
        'openClDelegations': delegated,
        'interpretation': 'Both preprocessing graphs are fully delegated to one OpenCL partition.',
    }


def trace_analysis(data, layout, output, year):
    window = data['window']
    client_pid = int(window['clientPid'])
    handle_map, mapping_evidence = infer_handle_map(data['logPath'], client_pid)
    traced = analyze_trace(
        data['logPath'],
        layout,
        client_pid,
        mode='lab',
        year=year,
        skip=0,
        handle_pipelines=handle_map,
    )
    (output / 'mapped-operator-timings.json').write_text(json.dumps(traced, indent=2) + '\n')
    pipelines = {
        item['pipeline']: item for item in traced['pipelines'] if item['status'] == 'mapped'
    }
    if set(pipelines) != set(PIPELINE_ORDER):
        raise AssertionError(f'Missing mapped pipelines: {set(PIPELINE_ORDER) - set(pipelines)}')
    owners = {(item['servicePid'], item['clientPid']) for item in pipelines.values()}
    if len(owners) != 1:
        raise AssertionError(f'Pipeline owner changed: {owners}')
    tasks = {
        name: {str(int(task['task'], 0)): task for task in pipeline['taskRecords']}
        for name, pipeline in pipelines.items()
    }
    anchors, anchor_records = clock_anchors(data['logPath'], client_pid, year)
    if not anchors:
        raise AssertionError('No usable face_frame clock anchors')
    offset_ms = statistics.median(anchors)
    kept_frames = {frame['frame'] for frame in data['frames']}
    complete_chains = []
    unmatched = []
    matched = []
    for terminal in tasks['output_7'].values():
        chain = {'output_7': terminal}
        for previous, following in reversed(list(zip(PIPELINE_ORDER, PIPELINE_ORDER[1:]))):
            task = tasks[previous].get(chain[following].get('waitForTask'))
            if task is None:
                break
            chain[previous] = task
        if len(chain) != len(PIPELINE_ORDER):
            continue
        ordered = [chain[name] for name in PIPELINE_ORDER]
        if not all(a['runCompleteMs'] <= b['runStartMs'] for a, b in zip(ordered, ordered[1:])):
            continue
        service_span = ordered[-1]['runCompleteMs'] - ordered[0]['runStartMs']
        task_execution = sum(task['runCompleteMs'] - task['runStartMs'] for task in ordered)
        operator_sum = sum(sum(task['operatorDurationMs']) for task in ordered)
        record = {
            'tasks': {name: task['task'] for name, task in chain.items()},
            'serviceChainSpanMs': service_span,
            'taskExecutionMs': task_execution,
            'operatorMs': operator_sum,
            'withinTaskOverheadMs': task_execution - operator_sum,
            'interTaskGapMs': service_span - task_execution,
        }
        complete_chains.append(record)
        start = (ordered[0]['runStartMs'] - offset_ms) / 1000
        end = (ordered[-1]['runCompleteMs'] - offset_ms) / 1000
        candidates = [
            frame
            for frame in data['allFrames']
            if frame['submitSeconds'] - .010 <= start < frame['readbackSeconds']
            and frame['submitSeconds'] <= end <= frame['readbackSeconds'] + .010
        ]
        if len(candidates) != 1:
            unmatched.append({'tasks': record['tasks'], 'candidateFrames': [f['frame'] for f in candidates]})
            continue
        frame = candidates[0]
        scene = data['scenes'].get(frame['frame'])
        record.update(
            {
                'frame': frame['frame'],
                'eligibleFace': frame['frame'] in kept_frames and eligible(frame),
                'submitToReadbackMs': frame['submitToReadbackSeconds'] * 1000,
                'outsideServiceSpanMs': frame['submitToReadbackSeconds'] * 1000 - service_span,
                'appDecodeMs': frame['appDecodeSeconds'] * 1000,
                'appRegistrationMs': frame['appRegistrationSeconds'] * 1000,
                'readbackToMeshUploadMs': (
                    (scene['uploadNanos'] / 1e9 - frame['readbackSeconds']) * 1000
                    if scene and scene.get('visible')
                    else None
                ),
            }
        )
        matched.append(record)
    frame_ids = [chain['frame'] for chain in matched]
    if len(set(frame_ids)) != len(frame_ids):
        raise AssertionError('Multiple service chains associated with one journal frame')
    face_chains = [chain for chain in matched if chain['eligibleFace']]
    if not face_chains:
        raise AssertionError('No eligible face chains')
    if any(chain['outsideServiceSpanMs'] < 0 for chain in face_chains):
        raise AssertionError('Service chain extends outside app submit/readback bounds')

    ordered_operations = []
    operation_order = 0
    for pipeline_name in PIPELINE_ORDER:
        pipeline = pipelines[pipeline_name]
        specification = next(
            item for item in layout['lab'] if item['pipeline'] == pipeline_name
        )
        if len(specification['operators']) != len(pipeline['operators']):
            raise AssertionError(f'Layout mismatch for {pipeline_name}')
        for operator in pipeline['operators']:
            operation_order += 1
            key = (pipeline_name, operator['name'], operator['index'])
            values = [
                tasks[pipeline_name][str(int(chain['tasks'][pipeline_name], 0))][
                    'operatorDurationMs'
                ][operator['index']]
                for chain in face_chains
            ]
            ordered_operations.append(
                {
                    'order': operation_order,
                    'pipeline': pipeline_name,
                    'pipelineHandle': pipeline['pipelineHandle'],
                    'index': operator['index'],
                    'name': operator['name'],
                    'kind': operator['kind'],
                    'implementation': IMPLEMENTATIONS[key],
                    'description': DESCRIPTIONS[key],
                    **stats(values),
                }
            )
    return {
        'clientPid': client_pid,
        'servicePid': next(iter(owners))[0],
        'pipelineHandleMap': mapping_evidence,
        'clockAssociation': {
            'anchorCount': len(anchors),
            'offsetMs': offset_ms,
            'offsetSpreadMs': max(anchors) - min(anchors),
            'anchors': anchor_records,
            'toleranceMs': 10,
            'method': 'Outer logcat wall timestamp minus app capture plus capture-age monotonic timestamp.',
        },
        'delegateEvidence': delegate_evidence(data, next(iter(owners))[0], client_pid),
        'completeDependencyChains': len(complete_chains),
        'matchedWindowChains': len(matched),
        'unmatchedCompleteChains': len(unmatched),
        'eligibleFaceChains': len(face_chains),
        'ineligibleMatchedChains': len(matched) - len(face_chains),
        'unmatched': unmatched,
        'budget': {
            key: stats(chain[key] for chain in face_chains)
            for key in (
                'operatorMs',
                'withinTaskOverheadMs',
                'interTaskGapMs',
                'serviceChainSpanMs',
                'outsideServiceSpanMs',
                'submitToReadbackMs',
                'appDecodeMs',
                'appRegistrationMs',
            )
        },
        'pipelines': {
            name: {
                'pipelineHandle': pipeline['pipelineHandle'],
                'mappingBasis': pipeline['mappingBasis'],
                'acceptedTasks': pipeline['acceptedTasks'],
                'exclusions': pipeline['exclusions'],
                'executionMs': pipeline['executionMs'],
                'operatorSumMs': pipeline['operatorSumMs'],
                'tracedGapMs': pipeline['tracedGapMs'],
            }
            for name, pipeline in pipelines.items()
        },
        'orderedOperations': ordered_operations,
        'faceChains': face_chains,
        'boundary': 'Trace logging is enabled. Model-call times include current SpatialML/LiteRT wrapper copies and invocation. Enqueue dependency wait is not added to execution because it overlaps upstream work.',
    }


def write_csv(path, rows):
    fields = [
        'order',
        'pipeline',
        'pipelineHandle',
        'index',
        'name',
        'kind',
        'implementation',
        'description',
        'count',
        'mean',
        'p50',
        'p90',
        'p95',
        'minimum',
        'maximum',
    ]
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def analyze(normal_session, trace_session, layout_path, output, year):
    output.mkdir(parents=True, exist_ok=True)
    layout = json.loads(layout_path.read_text())
    normal_data = load_window(normal_session)
    trace_data = load_window(trace_session)
    normal = summarize_window(normal_data)
    traced_window = summarize_window(trace_data)
    traced = trace_analysis(trace_data, layout, output, year)
    write_csv(output / 'ordered-face-operations.csv', traced['orderedOperations'])
    (output / 'face-chains.json').write_text(json.dumps(traced.pop('faceChains'), indent=2) + '\n')
    result = {
        'configuration': {
            'name': 'compact-adjacent-vst-fused-controls',
            'preprocessing': 'gpu-rgb-first',
            'outputMask': 7,
            'packetBytes': PACKET_BYTES,
            'normalSession': str(normal_session),
            'traceSession': str(trace_session),
            'layout': str(layout_path),
        },
        'admission': {
            'warmupFramesPerWindow': WARMUP,
            'requirements': [
                'schema 2',
                'output mask 7',
                '6332-byte result',
                'no calibration-evidence route',
                'face present',
                'fresh camera frame',
                'no rejection',
                'camera age in sensor domain',
            ],
        },
        'normalWindow': normal,
        'tracedWindow': traced_window,
        'traceComponents': traced,
        'trackingMeasurement': {
            'observedTrackingFramesNormal': normal['trackingFrames'],
            'observedTrackingFramesTrace': traced_window['trackingFrames'],
            'status': 'unmeasured',
            'reason': 'Every admitted journal frame selected the detector path and no tracking pipeline task was observed.',
        },
        'boundary': 'Normal-window end-to-end values are tracing-off. Operator values are from exact tracing-on eligible face chains and must not be summed with tracing-off quantiles. Upload acknowledgement is not display presentation; zero-copy is not claimed.',
    }
    result_path = output / 'compact-fused-analysis.json'
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    print(
        'normal faces',
        normal['eligibleFaceFrames'],
        'p50/p95',
        normal['submitToReadbackMs']['p50'],
        normal['submitToReadbackMs']['p95'],
        'Hz',
        normal['completionHz'],
    )
    print(
        'trace chains',
        traced['eligibleFaceChains'],
        'matched',
        traced['matchedWindowChains'],
        'unmatched',
        traced['unmatchedCompleteChains'],
    )
    print('ordered operations', len(traced['orderedOperations']))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--normal-session', required=True, type=Path)
    parser.add_argument('--trace-session', required=True, type=Path)
    parser.add_argument('--layout', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--year', default=2026, type=int)
    arguments = parser.parse_args()
    analyze(
        arguments.normal_session,
        arguments.trace_session,
        arguments.layout,
        arguments.output,
        arguments.year,
    )
