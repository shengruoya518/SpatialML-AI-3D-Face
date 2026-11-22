"""Summarize existing lab telemetry without changing an app or contacting a headset.

Latency groups use fresh, finite, unrejected packets after warmup. Render timings
require a unique matching scene acknowledgement and describe SDK upload completion.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


def distribution(values):
    values = sorted(values)
    if not values:
        return None
    at = (len(values) - 1) * .95
    low, high = math.floor(at), math.ceil(at)
    return dict(count=len(values), minimum=min(values), median=statistics.median(values),
                mean=statistics.mean(values), maximum=max(values),
                p95=values[low] + (values[high] - values[low]) * (at - low))


def summarize(path, skip_frames=20):
    frames, scenes, sessions, warnings = [], defaultdict(list), [], Counter()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for line_number, line in enumerate(stream, 1):
            digest.update(line)
            if not line.strip():
                continue
            try:
                row = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f'Nonfinite JSON literal {value}')))
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError(f'{path.name}:{line_number}: invalid or partial journal row') from error
            if not isinstance(row, dict):
                raise ValueError(f'{path.name}:{line_number}: journal row must be an object')
            if row.get('event') == 'session':
                sessions.append(row['session'])
            elif row.get('event') == 'pipeline_frame':
                frames.append(row['details'])
            elif row.get('event') == 'scene_update_complete' and row.get('mesh'):
                scenes[row['mesh']['frame']].append(row['mesh'])
    if len(sessions) != 1:
        raise ValueError('Require exactly one session record; use a complete single-session journal')
    counts = Counter(frame['frame'] for frame in frames)
    duplicate_ids = {number for number, count in counts.items() if count != 1}
    warnings['duplicate_packet_ids'] = len(duplicate_ids)
    groups, exclusions = {}, Counter()
    accepted = []
    for frame in frames:
        reason = None
        if frame['frame'] in duplicate_ids:
            reason = 'duplicate_identity'
        elif frame['frame'] <= skip_frames:
            reason = 'warmup'
        elif frame.get('rejection') is not None:
            reason = 'rejected'
        elif not frame.get('nativePacketFinite'):
            reason = 'nonfinite_packet'
        elif not frame.get('freshCameraFrame'):
            reason = 'unfresh'
        times = [frame.get(key) for key in ['submitSeconds', 'readbackSeconds', 'captureSeconds']]
        if reason is None and not all(isinstance(t, (int, float)) and math.isfinite(t) for t in times):
            reason = 'invalid_clock'
        if reason is None and frame['readbackSeconds'] < frame['submitSeconds']:
            reason = 'negative_duration'
        if reason is not None:
            exclusions[reason] += 1
            continue
        phase = 'detection' if frame['detector'] else 'tracking'
        workload = 'face' if frame['hasFace'] else 'no_face'
        mode = 'evidence' if frame['calibrationEvidence'] else 'normal'
        key = f'mask{frame["outputMask"]}/{mode}/{workload}/{phase}'
        group = groups.setdefault(key, dict(metrics=defaultdict(list), frames=0, bytes=set(),
                                             filter_reasons=Counter(), response_profiles=Counter()))
        group['frames'] += 1
        group['bytes'].add(frame['readbackBytes'])
        for name, value in {
            'submit_to_readback_ms': (frame['readbackSeconds'] - frame['submitSeconds']) * 1000,
            'camera_age_at_readback_ms': (frame['readbackSeconds'] - frame['captureSeconds']) * 1000,
            'app_decode_ms': frame.get('appDecodeSeconds', math.nan) * 1000,
            'app_registration_ms': frame.get('appRegistrationSeconds', math.nan) * 1000,
        }.items():
            if math.isfinite(value):
                group['metrics'][name].append(value)
        acknowledgements = scenes[frame['frame']]
        if len(acknowledgements) > 1:
            warnings['ambiguous_scene_acknowledgements'] += 1
        elif len(acknowledgements) == 1:
            scene = acknowledgements[0]
            correction = frame.get('poseCorrection', {})
            same_correction = all(scene.get('poseCorrection', {}).get(k) == correction.get(k)
                                  for k in ['id', 'revision'])
            same_capture = abs(scene['captureSeconds'] - frame['captureSeconds']) <= 1e-6
            if not same_capture or not same_correction:
                warnings['mismatched_scene_acknowledgements'] += 1
            elif scene['visible'] and scene['hasFace'] and frame['hasFace'] and frame['outputMask'] & 2:
                upload_seconds = scene['uploadNanos'] * 1e-9
                if upload_seconds < frame['readbackSeconds']:
                    warnings['negative_upload_duration'] += 1
                else:
                    group['metrics']['readback_to_mesh_upload_ms'].append(
                        (upload_seconds - frame['readbackSeconds']) * 1000)
                    group['metrics']['exposure_to_mesh_upload_ms'].append(
                        (upload_seconds - frame['captureSeconds']) * 1000)
                filtered = scene.get('meshStabilization')
                if filtered:
                    group['filter_reasons'][filtered['reason']] += 1
                    group['response_profiles'][filtered.get('responseProfile', 'unspecified')] += 1
        accepted.append((key, frame))
    for (older_key, older), (newer_key, newer) in zip(accepted, accepted[1:]):
        if older_key != newer_key or newer['frame'] != older['frame'] + 1:
            continue
        cadence = (newer['submitSeconds'] - older['submitSeconds']) * 1000
        gap = (newer['submitSeconds'] - older['readbackSeconds']) * 1000
        if cadence <= 0 or gap < 0:
            warnings['overlapping_or_nonadvancing_submissions'] += 1
            continue
        groups[older_key]['metrics']['submission_interval_ms'].append(cadence)
        groups[older_key]['metrics']['readback_to_next_submission_ms'].append(gap)
    result = dict(schema=1, session=sessions[0], journal_sha256=digest.hexdigest(),
                  total_packets=len(frames), excluded_packets=dict(exclusions),
                  warnings={key: value for key, value in warnings.items() if value},
                  percentile_method='linear interpolation at (n-1)*0.95',
                  warmup_policy=f'Exclude packet frame <= {skip_frames}',
                  timing_boundary='Existing app clocks and SDK upload acknowledgement; not display presentation',
                  metric_notes=[
                      'Quantiles from different stages are not additive.',
                      'Readback-to-upload includes decode/registration/filtering/preparation/scheduling/replacement.',
                      'App registration excludes downstream presentation filtering in the current journal schema.',
                      'No-face, detection/tracking, selected-output and evidence populations stay separate.',
                  ], groups={})
    for key, group in sorted(groups.items()):
        result['groups'][key] = dict(eligible_packets=group['frames'], readback_bytes=sorted(group['bytes']),
                                    metrics={name: distribution(values) for name, values in group['metrics'].items()},
                                    filter_reasons=dict(group['filter_reasons']),
                                    response_profiles=dict(group['response_profiles']))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--skip-frames', type=int, default=20)
    args = parser.parse_args()
    if args.skip_frames < 0:
        parser.error('--skip-frames must be nonnegative')
    try:
        report = summarize(args.timeline, args.skip_frames)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'Cannot summarize journal: {error}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{report["total_packets"]} packets; {len(report["groups"])} groups; '
          f'{sum(report["excluded_packets"].values())} exclusions; '
          f'{sum(report["warnings"].values())} warnings. Report: {args.output}')
