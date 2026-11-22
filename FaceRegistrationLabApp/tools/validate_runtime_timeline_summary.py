"""Verify timing/report boundaries with synthetic valid and invalid journal fixtures."""
import json
from pathlib import Path
import tempfile
import unittest

from summarize_runtime_timeline import summarize


def packet(seq, face=True, detector=False, mask=7, evidence=False, rejection=None):
    return dict(event='pipeline_frame', details=dict(
        frame=seq, hasFace=face, detector=detector, outputMask=mask,
        calibrationEvidence=evidence, rejection=rejection, nativePacketFinite=True,
        freshCameraFrame=True, submitSeconds=seq * .1, readbackSeconds=seq * .1 + .02,
        captureSeconds=seq * .1 - .03, readbackBytes=6332, appDecodeSeconds=.001,
        appRegistrationSeconds=.002, poseCorrection=dict(id='fixture', revision=0)))


def acknowledgement(seq, delta=0, visible=True):
    return dict(event='scene_update_complete', mesh=dict(
        frame=seq, captureSeconds=seq * .1 - .03 + delta,
        uploadNanos=round((seq * .1 + .03) * 1e9), visible=visible, hasFace=True,
        poseCorrection=dict(id='fixture', revision=0)))


class RuntimeSummaryTests(unittest.TestCase):
    def test_unique_paired_timings_and_population_boundaries(self):
        rows = [dict(event='session', session='fixture'), packet(1), acknowledgement(1),
                packet(2), acknowledgement(2), packet(3, face=False), packet(4, detector=True),
                acknowledgement(4), acknowledgement(4), packet(5), acknowledgement(5, delta=.01),
                packet(6, rejection='clock'), packet(7, evidence=True), packet(8, mask=1),
                acknowledgement(8, visible=False), packet(9), packet(9)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'journal.jsonl'
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            result = summarize(path, 0)
        group = result['groups']['mask7/normal/face/tracking']
        self.assertEqual(group['eligible_packets'], 3)
        self.assertEqual(group['metrics']['readback_to_mesh_upload_ms']['count'], 2)
        self.assertAlmostEqual(group['metrics']['readback_to_mesh_upload_ms']['median'], 10)
        self.assertEqual(group['metrics']['submission_interval_ms']['count'], 1)
        self.assertEqual(result['warnings']['ambiguous_scene_acknowledgements'], 1)
        self.assertEqual(result['warnings']['mismatched_scene_acknowledgements'], 1)
        self.assertEqual(result['excluded_packets']['duplicate_identity'], 2)
        self.assertEqual(result['excluded_packets']['rejected'], 1)
        self.assertIn('mask7/normal/no_face/tracking', result['groups'])
        self.assertIn('mask7/evidence/face/tracking', result['groups'])
        self.assertNotIn('readback_to_mesh_upload_ms', result['groups']['mask1/normal/face/tracking']['metrics'])

    def test_invalid_partial_nonfinite_and_multisession_inputs(self):
        for text in ['{"event":', '[1,2]\n', '{"event":"pipeline_frame","value":NaN}\n',
                     '{"event":"session","session":"a"}\n{"event":"session","session":"b"}\n']:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'journal.jsonl'
                path.write_text(text)
                with self.assertRaises(ValueError):
                    summarize(path)


if __name__ == '__main__':
    unittest.main()
