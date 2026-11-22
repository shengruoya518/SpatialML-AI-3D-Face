"""Summarize frame-paired mesh upload timers from one lab journal (host only)."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


def distribution(values):
    values = sorted(values)
    at = (len(values) - 1) * .95
    lo, hi = math.floor(at), math.ceil(at)
    return dict(count=len(values), median=statistics.median(values),
                p95=values[lo] + (values[hi] - values[lo]) * (at-lo))


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def summarize(path, skip_frames=20):
    frames, timings, scenes = (defaultdict(list) for _ in range(3))
    sessions = []
    data = path.read_bytes()
    for line in data.splitlines():
        if not line.strip():
            continue
        row = json.loads(line, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
        if row.get('event') == 'session':
            sessions.append(row['session'])
        elif row.get('event') == 'pipeline_frame':
            frames[row['details']['frame']].append(row['details'])
        elif row.get('event') == 'mesh_upload_timing':
            timings[row['details']['frame']].append(row['details'])
        elif row.get('event') == 'scene_update_complete' and row.get('mesh'):
            scenes[row['mesh']['frame']].append(row['mesh'])
    if len(sessions) != 1:
        raise ValueError('Require exactly one complete journal session')
    exclusions = Counter()
    groups = defaultdict(lambda: defaultdict(list))
    for seq, candidates in frames.items():
        if len(candidates) != 1:
            exclusions['duplicate_packet_identity'] += 1
            continue
        frame = candidates[0]
        reason = next((name for name, excluded in [
            ('warmup', seq <= skip_frames),
            ('rejected', frame.get('rejection') is not None),
            ('nonfinite', frame.get('nativePacketFinite') is not True),
            ('unfresh', frame.get('freshCameraFrame') is not True),
            ('no_face', frame.get('hasFace') is not True),
            ('evidence', frame.get('calibrationEvidence') is not False),
            ('no_mesh', not frame.get('outputMask', 0) & 2),
        ] if excluded), None)
        if reason:
            exclusions[reason] += 1
            continue
        if len(timings[seq]) != 1 or len(scenes[seq]) != 1:
            exclusions['missing_or_ambiguous_upload'] += 1
            continue
        t, scene = timings[seq][0], scenes[seq][0]
        if not t.get('visible') or not scene.get('visible') or t.get('preparedStyle') != t.get('appliedStyle'):
            exclusions['hidden_or_style_transition'] += 1
            continue
        if t.get('schema') != 1 or not isinstance(t.get('publication'), dict):
            exclusions['missing_or_unsupported_timing'] += 1
            continue
        pub = t['publication']
        try:
            for key in ['captureSeconds', 'readbackSeconds']:
                if not number(frame.get(key)) or any(not number(r.get(key)) or abs(r[key]-frame[key]) > 1e-6 for r in (t, scene)):
                    raise ValueError('mismatched clock identity')
            for key in ['id', 'revision']:
                if (frame.get('poseCorrection') or {}).get(key) != (scene.get('poseCorrection') or {}).get(key):
                    raise ValueError('mismatched correction identity')
            if not number(scene.get('uploadNanos')) or not number(frame.get('submitSeconds')):
                raise ValueError('invalid submit/ack clock')
            # Ordered timestamps create non-overlapping budgets that reconcile for each frame.
            clocks = [frame['readbackSeconds'], pub['registeredSeconds'], pub['filterStartedSeconds'],
                      pub['filterCompletedSeconds'], pub['publishedSeconds'], t['sceneReceivedSeconds'],
                      t['sceneAcquiredSeconds'], t['ownerSnapshotStartSeconds'], t['ownerSnapshotEndSeconds'],
                      t['workerDispatchedSeconds'], t['workerStartedSeconds'], t['preparedSeconds'],
                      t['sdkUploadStartSeconds'], t['sdkUploadEndSeconds'], t['uiResumedSeconds'],
                      t['sceneReadySeconds'], scene['uploadNanos'] * 1e-9]
            if not all(number(c) for c in clocks) or any(b < a for a, b in zip(clocks, clocks[1:])):
                raise ValueError('unordered clock')
            if not frame['captureSeconds'] <= frame['readbackSeconds'] or frame['submitSeconds'] > frame['readbackSeconds']:
                raise ValueError('invalid exposure/submission clock')
            numeric = [t[k] for k in ['coordinateSeconds', 'normalSeconds', 'boundsSeconds']]
            if not all(number(v) and v >= 0 for v in numeric) or sum(numeric) > t['preparedSeconds']-t['workerStartedSeconds']+1e-6:
                raise ValueError('invalid preparation subtimers')
        except (KeyError, TypeError, ValueError):
            exclusions['invalid_or_mismatched_clock'] += 1
            continue
        profile = (scene.get('meshStabilization') or {}).get('responseProfile', 'off')
        phase = 'detection' if frame.get('detector') else 'tracking'
        key = f"mask{frame['outputMask']}/{phase}/style{t['preparedStyle']}/{profile}/{t.get('operation', 'unknown')}"
        group = groups[key]
        spans = ['readback_to_registered', 'post_registration', 'smoothing', 'publication_bookkeeping',
                 'publication_to_collector', 'serialization_wait', 'scene_setup', 'owner_basis_snapshot',
                 'dispatch_bookkeeping', 'worker_scheduling', 'mesh_preparation', 'pre_upload_bookkeeping',
                 'sdk_upload_call', 'ui_resume_wait', 'scene_finalize', 'legacy_ack_bookkeeping']
        for name, a, b in zip(spans, clocks, clocks[1:]):
            group[name+'_ms'].append((b-a)*1000)
        for name, value in zip(['coordinate', 'normals', 'bounds'], numeric):
            group[name+'_ms'].append(value*1000)
        group['other_preparation_ms'].append(max(0, (t['preparedSeconds']-t['workerStartedSeconds']-sum(numeric))*1000))
        group['readback_to_sdk_return_ms'].append((t['sdkUploadEndSeconds']-frame['readbackSeconds'])*1000)
        group['exposure_to_sdk_return_ms'].append((t['sdkUploadEndSeconds']-frame['captureSeconds'])*1000)
        group['readback_to_scene_ack_ms'].append((clocks[-1]-clocks[0])*1000)
        group['submit_to_readback_ms'].append((frame['readbackSeconds']-frame['submitSeconds'])*1000)
    return dict(schema=1, session=sessions[0], journal_sha256=hashlib.sha256(data).hexdigest(),
                packet_identities=len(frames), upload_records=sum(map(len, timings.values())),
                unpaired_upload_identities=len(set(timings)-set(frames)), exclusions=dict(exclusions),
                groups={k: {m: distribution(v) for m, v in g.items()} for k, g in sorted(groups.items())},
                boundary='SDK call return includes SDK scheduling/adaptation/replacement; not screen presentation',
                notes=['Compare readback_to_scene_ack_ms to the historical 18.89/33.86 ms baseline.',
                       'Subtimer quantiles are not additive; all metrics within a group use identical paired frames.',
                       'Smoothing CPU time is distinct from temporal filter response lag.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal', type=Path)
    parser.add_argument('--skip-frames', type=int, default=20)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.journal, args.skip_frames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2, allow_nan=False))
