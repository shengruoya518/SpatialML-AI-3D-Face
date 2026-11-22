"""Measure saved frame/journal boundaries without treating them as operator benchmarks."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics


def stats(values):
    values = sorted(v for v in values if math.isfinite(v))
    if not values:
        return {'count': 0}
    def quantile(q):
        index = q * (len(values) - 1)
        lo = int(index)
        return values[lo] + (values[min(lo+1, len(values)-1)]-values[lo])*(index-lo)
    return dict(count=len(values), mean=statistics.fmean(values), p50=quantile(.5),
                p90=quantile(.9), p95=quantile(.95), minimum=values[0], maximum=values[-1])


def analyze(path, warmup=10):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    frames = [r['details'] for r in rows if r['event'] == 'pipeline_frame']
    scenes = {r['mesh']['frame']: r['mesh'] for r in rows
              if r['event'] == 'scene_update_complete' and r.get('mesh')}
    saved = {r['details']['frame']: r for r in rows if r['event'] == 'automatic_capture_saved'}
    rejected = {r['details']['frame']: r for r in rows if r['event'] == 'automatic_capture_rejected'}
    export_ids = saved.keys() | rejected.keys()
    subsets = {'all_after_warmup': [], 'face_not_exported': [], 'face_exports': [],
               'face_marked': [], 'face_clean': [], 'face_idle': [], 'no_face': []}
    for index, frame in enumerate(frames):
        if index < warmup:
            continue
        subsets['all_after_warmup'].append(frame)
        if not frame['hasFace']:
            subsets['no_face'].append(frame)
            continue
        if frame['frame'] in export_ids:
            subsets['face_exports'].append(frame)
            continue
        subsets['face_not_exported'].append(frame)
        scene = scenes.get(frame['frame'])
        tag = scene.get('automatic') if scene else None
        phase = tag.get('phase') if tag else None
        key = 'face_marked' if phase == 'MARKED' else 'face_clean' if phase in ('CLEAN_BEFORE', 'CLEAN_AFTER') else 'face_idle'
        subsets[key].append(frame)
    by_id = {f['frame']: f for f in frames}
    distributions = {}
    for name, sample in subsets.items():
        paired = [(f, scenes[f['frame']]) for f in sample if f['frame'] in scenes]
        distributions[name] = {
            'frames': len(sample),
            'submitToReadbackMs': stats(f['submitToReadbackSeconds']*1000 for f in sample),
            'cameraAgeAtReadbackMs': stats(f['cameraAgeAtReadbackSeconds']*1000 for f in sample
                                          if -.1 <= f['cameraAgeAtReadbackSeconds'] <= 2),
            'submitMinusExposureMs': stats((f['submitSeconds']-f['captureSeconds'])*1000 for f in sample
                                           if -.1 <= f['cameraAgeAtReadbackSeconds'] <= 2),
            'readbackToUploadMs': stats((s['uploadNanos']/1e9-f['readbackSeconds'])*1000 for f, s in paired),
            'pairedCameraAgeAtReadbackMs': stats(f['cameraAgeAtReadbackSeconds']*1000 for f, s in paired
                                                if -.1 <= f['cameraAgeAtReadbackSeconds'] <= 2),
            'cameraAgeAtUploadMs': stats((s['uploadNanos']/1e9-f['captureSeconds'])*1000 for f, s in paired
                                         if -.1 <= f['cameraAgeAtReadbackSeconds'] <= 2),
            'presentationPairCount': len(paired),
        }
    intervals = []
    for current, following in zip(frames[warmup:], frames[warmup+1:]):
        interval = following['submitSeconds'] - current['submitSeconds']
        gap = following['submitSeconds'] - current['readbackSeconds']
        intervals.append({'frame': current['frame'], 'export': current['frame'] in export_ids,
                          'knownMismatch': current['frame'] in rejected, 'face': current['hasFace'],
                          'intervalMs': interval*1000, 'readbackToNextSubmitMs': gap*1000})
    cadence = {}
    for name, group in [('all', intervals), ('not_exported', [r for r in intervals if not r['export']]),
                        ('exported_or_rejected', [r for r in intervals if r['export']])]:
        span = sum(r['intervalMs']/1000 for r in group)
        cadence[name] = {'count':len(group), 'completionHzOverIncludedIntervals':len(group)/span if span else None,
                         'submitIntervalMs':stats(r['intervalMs'] for r in group),
                         'readbackToNextSubmitMs':stats(r['readbackToNextSubmitMs'] for r in group)}
    export_cost = []
    for frame_id, event in (saved | rejected).items():
        if frame_id not in by_id:
            continue
        frame = by_id[frame_id]
        export_cost.append({'frame': frame_id, 'accepted':frame_id in saved,
                            'run':event['details']['run'], 'phase':event['details']['phase'],
                            'readbackToSaveEventMs':(event['monotonicNanos']/1e9-frame['readbackSeconds'])*1000})
    return {'journal':str(path), 'frames':len(frames), 'warmupExcluded':warmup,
            'faceFrames':sum(f['hasFace'] for f in frames),
            'detectorFrames':sum(f['detector'] for f in frames),
            'unfreshFrames':sum(not f['freshCameraFrame'] for f in frames),
            'rejections':dict(Counter(f['rejection'] or 'none' for f in frames)),
            'knownPacketMismatchFrames':sorted(rejected), 'distributions':distributions,
            'cadence':cadence, 'exports':export_cost,
            'acceptedExportReadbackToSaveMs':stats(e['readbackToSaveEventMs'] for e in export_cost if e['accepted']),
            'boundary':'Submission/readback, upload acknowledgement and journal save only. Legacy frame completion can be premature. No operator, pure IO, compositor or motion-to-photon timing.'}


def coherent_exports(folder):
    samples = [json.loads(p.read_text()) for p in folder.glob('*/sample.json')]
    for sample in samples:
        diff = sample['snapshotDifference']
        assert diff['numericMismatchCount'] == diff['signedZeroDifferenceCount'] == 0
        assert sample['geometryProbe']['resultMatchesReadback']
        assert sample['captureAcceptance'] == 'EXPOSURE_STABLE'
    return {'acceptedCoherentExports':len(samples),
            'submissionToReadbackMs':stats(s['frameReadbackLatencySeconds']*1000 for s in samples),
            'cameraAgeAtReadbackMs':stats(s['cameraAgeAtReadbackSeconds']*1000 for s in samples),
            'boundary':'Selected exports validated for packet coherence; not a random steady-state population.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journals', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--warmup', type=int, default=10)
    parser.add_argument('--captures', type=Path, help='Optional folder of accepted sample.json exports')
    args = parser.parse_args()
    result = {'sessions':[analyze(p, args.warmup) for p in args.journals]}
    if args.captures:
        result['coherentExportTimings'] = coherent_exports(args.captures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    for s in result['sessions']:
        row=s['distributions']['face_not_exported']
        print(Path(s['journal']).parent.name, 'face frames', row['frames'],
              'readback p50/p95', row['submitToReadbackMs'].get('p50'), row['submitToReadbackMs'].get('p95'),
              'upload p50', row['readbackToUploadMs'].get('p50'))
