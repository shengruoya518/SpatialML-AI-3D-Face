"""Analyze microsecond SpatialML service events against a recorded Kotlin graph layout.

Only complete successful tasks with every operator start/end are admitted. Process owners,
pipeline handles and task IDs remain part of the identity. Pipeline wait includes upstream
dependencies and is reported separately from execution; it is never summed twice.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import re

from analyze_pipeline_journal import stats

LINE = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{6})\s+(\d+)\s+(\d+)\s+\w\s+(.*)$')
EVENT = re.compile(r'SpatialMLDebug pid=(\d+) (?:pipeline=(0x[0-9a-fA-F]+) )?stage=(\w+)(.*)$')
FIELD = re.compile(r'(\w+)=(\S+)')
TYPES = {'RectifiedVSTAccess':'RECTIFIED_VST_ACCESS', 'CameraSpaceToWorld':'CAMERA_SPACE_TO_WORLD',
         'RetainedVSTAccess':'RETAINED_VST_ACCESS', 'RetainedVSTRoi':'RETAINED_VST_ROI',
         'RetainedVSTAffine':'RETAINED_VST_AFFINE',
         'ApplyAffine':'APPLY_AFFINE', 'Assignment':'ASSIGNMENT',
         'Arithmetic':'ARITHMETIC_COMPOSE', 'SVD':'SVD'}


def operator_type(spec):
    return {'javascript': 'JS_SCRIPTING', 'model': 'RUN_MODEL_INFERENCE'}.get(spec['kind'], TYPES.get(spec['name']))


def analyze(capture, layout, client_pid, mode='lab', year=2026, skip=5, handle_pipelines=None):
    handle_pipelines = handle_pipelines or {}
    tasks = {}
    stages = Counter()
    malformed = 0
    for line in capture.read_text(errors='replace').splitlines():
        match = LINE.match(line)
        if not match:
            if 'SpatialMLDebug' in line:
                malformed += 1
            continue
        event = EVENT.search(match[4])
        if not event or int(event[1]) != client_pid:
            continue
        timestamp = datetime.strptime(f'{year}-'+match[1], '%Y-%m-%d %H:%M:%S.%f').timestamp()*1000
        fields = dict(FIELD.findall(event[4]))
        stages[event[3]] += 1
        if not event[2] or 'task' not in fields:
            continue
        key = (int(match[2]), client_pid, event[2], fields['task'])
        task = tasks.setdefault(key, {'operators':{}, 'starts':{}, 'errors':[]})
        stage = event[3]
        if stage in ('task_enqueue', 'task_run_start', 'task_run_complete'):
            if stage in task:
                task['errors'].append('duplicate '+stage)
            task[stage] = timestamp
            if stage == 'task_run_complete':
                task['status'] = fields.get('status')
            if stage == 'task_enqueue':
                task['fields'] = fields
        elif stage == 'submit':
            task['submission'] = fields
        elif stage in ('operator_execute_start', 'operator_execute_complete'):
            index = int(fields['index'])
            if stage.endswith('start'):
                if index in task['starts']:
                    task['errors'].append('duplicate operator start')
                task['starts'][index] = timestamp
            else:
                if index not in task['starts'] or index in task['operators'] or fields.get('status') != 'ok':
                    task['errors'].append('missing/duplicate/failed operator completion')
                    continue
                task['operators'][index] = {'start':task['starts'][index], 'end':timestamp,
                                            'durationMs':timestamp-task['starts'][index], 'type':fields.get('type')}
    pipelines = defaultdict(list)
    for key, task in tasks.items():
        pipelines[key[:3]].append((key,task))
    results = []
    for owner, entries in sorted(pipelines.items()):
        entries.sort(key=lambda pair:pair[1].get('task_enqueue',pair[1].get('task_run_start',0)))
        observed = max((len(t['operators']) for _,t in entries), default=0)
        # Output publication and expression pipelines can have equal lengths. Validate their
        # complete type signatures instead of assigning semantic names by count alone.
        observed_types = {i: {t['operators'][i]['type'] for _, t in entries if i in t['operators']}
                          for i in range(observed)}
        requested_pipeline = handle_pipelines.get(owner[2])
        candidates = [p for p in layout[mode] if len(p['operators'])==observed and
                      (requested_pipeline is None or p['pipeline']==requested_pipeline) and
                      all(observed_types[i] == {operator_type(spec)} for i, spec in enumerate(p['operators']))]
        if len(candidates)!=1:
            results.append({'servicePid':owner[0], 'clientPid':owner[1], 'pipelineHandle':owner[2],
                            'observedOperatorCount':observed, 'status':'unmapped', 'tasks':len(entries),
                            'requestedPipeline':requested_pipeline})
            continue
        specification = candidates[0]
        expected = len(specification['operators'])
        complete = []
        exclusions = Counter()
        for key, task in entries:
            if task['errors'] or task.get('status')!='ok' or not all(s in task for s in ('task_enqueue','task_run_start','task_run_complete')):
                exclusions['missing_or_failed_events'] += 1
                continue
            if set(task['operators']) != set(range(expected)):
                exclusions['incomplete_operators'] += 1
                continue
            operators = [task['operators'][i] for i in range(expected)]
            if any(o['durationMs']<0 for o in operators) or any(a['end']>b['start'] for a,b in zip(operators,operators[1:])):
                exclusions['invalid_operator_order'] += 1
                continue
            if task['task_run_start']>operators[0]['start'] or operators[-1]['end']>task['task_run_complete']:
                exclusions['invalid_task_bounds'] += 1
                continue
            # Validate the typed native entries as well as count before mapping indices to JS/model names.
            if any(operators[spec['index']]['type'] != operator_type(spec)
                   for spec in specification['operators']):
                exclusions['layout_type_mismatch'] += 1
                continue
            complete.append((key,task))
        exclusions['warmup'] = min(skip,len(complete))
        complete=complete[skip:]
        execution=[t['task_run_complete']-t['task_run_start'] for _,t in complete]
        operator_sum=[sum(o['durationMs'] for o in t['operators'].values()) for _,t in complete]
        gaps=[total-op for total,op in zip(execution,operator_sum)]
        rows=[]
        for spec in specification['operators']:
            rows.append(dict(spec, durationMs=stats(t['operators'][spec['index']]['durationMs'] for _,t in complete)))
        groups=defaultdict(list)
        for _,task in complete:
            per_task=defaultdict(float)
            for spec in specification['operators']:
                per_task[spec['name']] += task['operators'][spec['index']]['durationMs']
            for name,total in per_task.items(): groups[name].append(total)
        results.append({'servicePid':owner[0], 'clientPid':owner[1], 'pipelineHandle':owner[2],
                        'pipeline':specification['pipeline'], 'status':'mapped', 'expectedOperators':expected,
                        'mappingBasis':'explicit_handle' if requested_pipeline else 'unique_layout_signature',
                        'acceptedTasks':len(complete), 'exclusions':dict(exclusions),
                        'executionMs':stats(execution), 'operatorSumMs':stats(operator_sum), 'tracedGapMs':stats(gaps),
                        'enqueueToRunMs':stats(t['task_run_start']-t['task_enqueue'] for _,t in complete),
                        'operators':rows, 'componentSumsMs':{k:stats(v) for k,v in groups.items()}})
        results[-1]['taskRecords'] = [
            {'task':key[3], 'enqueueMs':task['task_enqueue'],
             'runStartMs':task['task_run_start'], 'runCompleteMs':task['task_run_complete'],
             'waitForTask':task.get('submission', {}).get('wait_for'),
             'operatorDurationMs':[task['operators'][i]['durationMs'] for i in range(expected)]}
            for key,task in complete
        ]
    return {'clientPid':client_pid, 'mode':mode, 'stageCounts':dict(stages), 'unparsedStructuredLines':malformed,
            'pipelines':results,
            'boundary':'Trace timestamps include diagnostic logging overhead. Enqueue wait includes producer dependencies. No operator times exist unless native service trace events were captured.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture',type=Path)
    parser.add_argument('--layout',required=True,type=Path)
    parser.add_argument('--client-pid',required=True,type=int)
    parser.add_argument('--mode',default='lab',choices=['lab','normal'])
    parser.add_argument('--skip',default=5,type=int)
    parser.add_argument('--pipeline-handle-map',type=Path,
                        help='Optional JSON object mapping trace pipeline handles to layout pipeline names')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    handle_pipelines=json.loads(args.pipeline_handle_map.read_text()) if args.pipeline_handle_map else None
    data=analyze(args.capture,json.loads(args.layout.read_text()),args.client_pid,args.mode,
                 skip=args.skip,handle_pipelines=handle_pipelines)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2)+'\n')
    print('Mapped:',[(p.get('pipeline'),p.get('acceptedTasks')) for p in data['pipelines']])
