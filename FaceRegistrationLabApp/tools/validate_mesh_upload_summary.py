"""Check upload timing joins, boundaries, exclusions and malformed clocks."""
import copy
import json
from pathlib import Path
import tempfile
from summarize_mesh_upload import summarize


def main():
    seq = 21
    pub = dict(zip(['registeredSeconds', 'filterStartedSeconds', 'filterCompletedSeconds', 'publishedSeconds'], [1.002, 1.003, 1.004, 1.005]))
    keys = ['sceneReceivedSeconds', 'sceneAcquiredSeconds', 'ownerSnapshotStartSeconds', 'ownerSnapshotEndSeconds',
            'workerDispatchedSeconds', 'workerStartedSeconds', 'preparedSeconds', 'sdkUploadStartSeconds',
            'sdkUploadEndSeconds', 'uiResumedSeconds', 'sceneReadySeconds']
    timing = dict(zip(keys, [1.006, 1.007, 1.008, 1.009, 1.010, 1.011, 1.016, 1.017, 1.020, 1.024, 1.025]))
    timing.update(schema=1, frame=seq, captureSeconds=.9, readbackSeconds=1., publication=pub,
                  coordinateSeconds=.001, normalSeconds=.0001, boundsSeconds=.0002,
                  visible=True, preparedStyle=0, appliedStyle=0, operation='replace')
    packet = dict(frame=seq, captureSeconds=.9, readbackSeconds=1., submitSeconds=.95,
                  hasFace=True, nativePacketFinite=True, freshCameraFrame=True,
                  calibrationEvidence=False, outputMask=7, detector=False, rejection=None)
    scene = dict(frame=seq, captureSeconds=.9, readbackSeconds=1., visible=True, uploadNanos=1026000000)
    rows = [dict(event='session', session='test'), dict(event='pipeline_frame', details=packet),
            dict(event='scene_update_complete', mesh=scene), dict(event='mesh_upload_timing', details=timing)]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'timeline.jsonl'
        def run(data):
            path.write_text(''.join(json.dumps(r)+'\n' for r in data))
            return summarize(path)
        good = run(rows)
        g = next(iter(good['groups'].values()))
        assert abs(g['sdk_upload_call_ms']['median']-3) < 1e-9
        assert abs(g['readback_to_sdk_return_ms']['median']-20) < 1e-9
        assert abs(g['readback_to_scene_ack_ms']['median']-26) < 1e-9
        assert abs(g['ui_resume_wait_ms']['median']-4) < 1e-9
        assert run(rows+[rows[-1]])['exclusions']['missing_or_ambiguous_upload'] == 1
        assert run(rows+[rows[1]])['exclusions']['duplicate_packet_identity'] == 1
        assert run(rows[:-1])['exclusions']['missing_or_ambiguous_upload'] == 1
        for container, key, value in [(1, 'rejection', 'stale'), (1, 'freshCameraFrame', False),
                                      (1, 'nativePacketFinite', False), (1, 'hasFace', False),
                                      (1, 'calibrationEvidence', True), (1, 'outputMask', 1),
                                      (3, 'readbackSeconds', 1.1), (3, 'captureSeconds', .8),
                                      (3, 'sdkUploadEndSeconds', 1.015), (3, 'normalSeconds', -1),
                                      (3, 'normalSeconds', 1), (3, 'schema', 2),
                                      (3, 'publication', None), (3, 'appliedStyle', 1),
                                      (3, 'visible', False), (3, 'sdkUploadEndSeconds', True),
                                      (3, 'sdkUploadEndSeconds', None)]:
            bad = copy.deepcopy(rows); bad[container]['details'][key] = value
            assert not run(bad)['groups'], (key, value)
        try:
            run(rows+rows[:1])
        except ValueError:
            pass
        else:
            raise AssertionError('Accepted multiple sessions')
        legacy = run(rows[:-1]); assert not legacy['groups'] and legacy['upload_records'] == 0
    print('PASS: SDK/legacy endpoints, paired populations, duplicate/missing events, rejected/evidence/hidden frames, invalid clocks and legacy journals')


if __name__ == '__main__':
    main()
