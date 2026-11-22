"""Execute weightless models on host LiteRT and the production Kotlin final-output decoder.

Compare the app mesh against the shipped service operators at their float32
boundaries. This does not establish Android delegation, rendering or latency.
Run with uv run --no-project --with ai-edge-litert python <this file> --output ...
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from ai_edge_litert.interpreter import Interpreter

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
ASSETS = ROOT / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker'


def validate(output, json_jar):
    output.mkdir(parents=True, exist_ok=True)
    models = {}
    for item in json.loads((ASSETS / 'model/face_output_models.json').read_text()):
        path = ASSETS / 'model' / (item['name'] + '.tflite')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
        m = Interpreter(model_path=str(path), num_threads=1)
        m.allocate_tensors()
        models[item['name']] = m

    def infer(name, tensors):
        m = models[name]
        for detail in m.get_input_details():
            m.set_tensor(detail['index'], np.asarray(tensors[detail['name']], np.float32).reshape(detail['shape']))
        m.invoke()
        return m.get_tensor(m.get_output_details()[0]['index']).flatten()

    js = subprocess.Popen(['node', str(ROOT / 'FaceLandmarkerApp/tools/run_operator.mjs')],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    def op(name, **tensors):
        js.stdin.write(json.dumps(dict(script=str(ASSETS / 'operators' / (name + '.js')),
                        tensors={k: np.asarray(v).flatten().tolist() for k, v in tensors.items()})) + '\n')
        js.stdin.flush()
        response = json.loads(js.stdout.readline())
        assert 'error' not in response, response
        return {k: np.asarray(v, np.float32) for k, v in response['tensors'].items()}

    geo = json.loads((ASSETS / 'data/face_geometry.json').read_text())
    canonical = np.asarray(geo['canonical'] + [0] * 40, np.float32)
    rng = np.random.default_rng(423)
    fixtures = []
    blend_error = 0.0
    try:
        for case in range(24):
            raw = rng.uniform([30, 40, -30], [220, 210, 30], (478, 3)).astype(np.float32)
            roi = np.asarray([1, .98, rng.uniform(200, 2900), rng.uniform(200, 2200),
                              rng.uniform(200, 1400), rng.uniform(-2, 2)], np.float32)
            k = np.asarray([1800, 0, 1623.5, 0, 1780, 1231.5, 0, 0, 1], np.float32)
            settings = [3248, 2464]
            good = case % 6 != 0
            validity = [int(good), .99]
            lm = op('mesh_landmarks', rawLandmarks=raw, roi=roi, settings=settings,
                    validity=validity, subset=geo['blendshapeIndices'],
                    landmarks=np.zeros(1434), blendInput=np.zeros(292))
            blended = infer('face_blend_input', dict(raw_landmarks=raw, roi=roi))
            if good:
                expected_blend = lm['blendInput'] / np.float32(1024)
                blend_error = max(blend_error, float(np.max(np.abs(blended - expected_blend))))
                np.testing.assert_allclose(blended, expected_blend, rtol=0, atol=1e-6)
            projected = op('geometry_project', landmarks=lm['landmarks'], intrinsics=k,
                           settings=settings, canonical=canonical, validity=validity,
                           projected=np.zeros(1434), targets=np.zeros(1434), depthOffset=[0])
            scales = [np.float32(.012 + case * .0001), np.float32(.91)]
            metric = op('geometry_unproject', projected=projected['projected'],
                        depthOffset=projected['depthOffset'], firstScale=scales[:1], secondScale=scales[1:],
                        canonical=canonical, validity=validity, targets=np.zeros(1434))['targets']
            a = .03 * case; c, s = np.cos(a), np.sin(a)
            pose = np.asarray([c, 0, s, 2, 0, 1, 0, -3, -s, 0, c, -70, 0, 0, 0, 1], np.float32)
            world = pose.copy(); world[[3, 7, 11]] *= .01
            camera = np.eye(4, dtype=np.float32).flatten()
            diag = np.zeros(32, np.float32)
            diag[[1, 2, 12, 13, 14, 15, 30]] = [100000, .1234567, k[0], k[4], k[2], k[5], 1]
            command = [100001 + case, .5, 1, 1]
            scores = rng.random(52).astype(np.float32)
            legacy = op('pack_service_result', command=command, validity=validity, roi=roi,
                        landmarks=lm['landmarks'], metric=metric, pose=pose, worldPose=world,
                        blendshapes=scores, detectorInfo=[0, 0, 0], diagnostics=diag,
                        leftCameraToXr=camera, result=np.zeros(2994))['result']
            tensors = dict(command=command, validity=validity, roi=roi, diagnostics=diag, camera=camera,
                           world_pose=world, raw_landmarks=raw, fit_pose=pose, first_scale=scales[:1],
                           second_scale=scales[1:], depth=projected['depthOffset'], blendshapes=scores)
            for mask in range(1, 8):
                packet = infer(f'face_output_{mask}', tensors)
                # Publication is pure copying, including frame counts beyond FP16 exact integers.
                expected = np.concatenate([np.asarray(tensors[d['name']], np.float32).flatten()
                    for d in models[f'face_output_{mask}'].get_input_details()] + [np.asarray([2, mask], np.float32)])
                np.testing.assert_array_equal(packet.view(np.uint32), expected.view(np.uint32))
                fixtures.append(dict(mask=mask, packet=packet.tolist(), expected=legacy.tolist()))
    finally:
        js.stdin.close(); js.wait(timeout=10)
    (output / 'fixtures.json').write_text(json.dumps(fixtures))
    runner = (SOURCE / 'FaceLandmarkerRunner.kt').read_text()
    (output / 'Frame.kt').write_text('package com.pico.spatial.ml.sample.facelandmarker\nimport kotlin.math.hypot\n' + runner[runner.index('internal class FaceFrame('):])
    policy = runner[runner.index('    private val mutableOutputs'):runner.index('    @Volatile var sizeScale')]
    (output / 'Selection.kt').write_text('package com.pico.spatial.ml.sample.facelandmarker\nimport kotlinx.coroutines.flow.MutableStateFlow\nimport kotlinx.coroutines.flow.asStateFlow\ninternal data class LabSelectionState(val locked: Boolean = false, val showCaptureTools: Boolean = false)\ninternal data class LabSelectionAuto(val active: Boolean = false)\ninternal class LabSelection {\n    val requestedOutputs = MutableStateFlow(FaceOutputs.ALL)\n    val ui = MutableStateFlow(LabSelectionState())\n    val automaticUi = MutableStateFlow(LabSelectionAuto())\n}\ninternal class SelectionFixture(private val lab: LabSelection? = null, private val helmetMode: Boolean = false) {\n    private val mutableFrame = MutableStateFlow<FaceFrame?>(null)\n' + policy + '\n    fun selected() = effectiveOutputs()\n    fun evidence() = needsCalibrationEvidence()\n}\n')
    (output / 'Fixture.kt').write_text(r'''package com.pico.spatial.ml.sample.facelandmarker
import org.json.JSONArray
import java.io.File
import kotlin.math.abs
internal class LabAutoTag
internal class LabRegistrationEvidence(val headToStage: FloatArray)
internal object SpatialMLGraphSession { const val WIDTH = 3248; const val HEIGHT = 2464 }
private fun array(a: JSONArray) = FloatArray(a.length()) { a.getDouble(it).toFloat() }
private fun rejected(block: () -> Unit) {
    try { block() } catch (_: IllegalArgumentException) { return }
    error("Malformed output accepted")
}
fun main(args: Array<String>) {
    val selection = SelectionFixture()
    check(selection.selected() == FaceOutputs.ALL && !selection.evidence())
    for(mask in 0..7) { selection.setOutputs(FaceOutputs(mask)); check(selection.selected().mask == mask) }
    val lab = LabSelection()
    val captureSelection = SelectionFixture(lab)
    for(mask in 0..7) {
        captureSelection.setOutputs(FaceOutputs(mask))
        check(!captureSelection.evidence())
        lab.automaticUi.value = LabSelectionAuto(true)
        check(captureSelection.selected() == FaceOutputs.ALL && captureSelection.evidence())
        captureSelection.setOutputs(FaceOutputs(mask xor 7))
        check(captureSelection.outputs.value.mask == mask)
        lab.automaticUi.value = LabSelectionAuto(false)
        check(captureSelection.selected().mask == mask && !captureSelection.evidence())
        lab.ui.value = LabSelectionState(locked=true)
        check(captureSelection.selected() == FaceOutputs.ALL && captureSelection.evidence())
        captureSelection.setOutputs(FaceOutputs(mask xor 7))
        check(captureSelection.outputs.value.mask == mask)
        lab.ui.value = LabSelectionState(showCaptureTools=true)
        check(captureSelection.selected() == FaceOutputs.ALL && captureSelection.evidence())
        lab.ui.value = LabSelectionState()
        check(captureSelection.selected().mask == mask && !captureSelection.evidence())
    }
    val fixtures = JSONArray(File(args[0]).readText())
    val identity = floatArrayOf(1f,0f,0f,0f,0f,1f,0f,0f,0f,0f,1f,0f,0f,0f,0f,1f)
    var maxError = 0f
    check(!FaceOutputs.NONE.any)
    rejected { FaceOutputs(8) }
    for (i in 0 until fixtures.length()) {
        val fixture = fixtures.getJSONObject(i)
        val outputs = FaceOutputs(fixture.getInt("mask"))
        val packet = array(fixture.getJSONArray("packet"))
        val expected = array(fixture.getJSONArray("expected"))
        val decoded = FaceOutputPacket.decode(packet, outputs)
        val frame = FaceFrame(decoded, outputs = outputs)
        check(frame.outputs == outputs && frame.sequence == expected[0].toInt())
        check(frame.hasFace == (expected[1] > 0))
        check(frame.vertices.size == if(outputs.mesh) 1434 else 0)
        check(frame.pose.size == if(outputs.pose) 16 else 0)
        check(frame.blendshapes.size == if(outputs.blendshapes) 52 else 0)
        val rebase = frame.inStage(identity).withAutomatic(null)
        check(rebase.outputs == outputs)
        val ranges = listOf(0..3, 2946..2993) +
            (if(outputs.mesh) listOf(4..2871) else emptyList()) +
            (if(outputs.pose) listOf(2924..2939) else emptyList()) +
            (if(outputs.blendshapes) listOf(2872..2923) else emptyList())
        for (range in ranges) for (j in range) {
            val error = abs(decoded[j] - expected[j]); maxError = maxOf(error, maxError)
            check(error <= 2e-6f) { "case=$i value=$j got=${decoded[j]} expected=${expected[j]}" }
        }
        rejected { FaceOutputPacket.decode(packet.copyOf(packet.size - 1), outputs) }
        rejected { FaceOutputPacket.decode(packet.copyOf().also { it[it.lastIndex] = 0f }, outputs) }
        rejected { FaceOutputPacket.decode(packet.copyOf().also { it[it.lastIndex-1] = 99f }, outputs) }
        val invalid = packet.copyOf().also { it[4] = 0f }
        check(!FaceFrame(FaceOutputPacket.decode(invalid, outputs), outputs=outputs).hasFace)
        val corrupt = packet.copyOf().also { it[5] = Float.NaN }
        check(!FaceFrame(FaceOutputPacket.decode(corrupt, outputs), outputs=outputs).hasFace)
    }
    println("PASS ${fixtures.length()} model/decoder combinations; maximum absolute geometry difference=$maxError")
}
''')
    cache = Path.home() / '.gradle/caches/modules-2/files-2.1'
    def jar(group, name, version):
        return next((cache / group / name / version).glob('*/*.jar'))
    stdlib = jar('org.jetbrains.kotlin', 'kotlin-stdlib', '2.0.21')
    compiler = [jar('org.jetbrains.kotlin', n, '2.0.21') for n in
                ('kotlin-compiler-embeddable', 'kotlin-script-runtime', 'kotlin-reflect', 'kotlin-daemon-embeddable')]
    compiler += [stdlib, jar('org.jetbrains', 'annotations', '13.0'), jar('org.jetbrains.intellij.deps', 'trove4j', '1.0.20200330'),
                 jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.6.4')]
    java = '/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java'
    cp = os.pathsep.join(map(str, [stdlib, json_jar.resolve(), jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.6.4')]))
    subprocess.run([java, '-cp', os.pathsep.join(map(str, compiler)), 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler',
                    '-no-stdlib', '-no-reflect', '-classpath', cp, '-d', str(output / 'classes'),
                    str(output / 'Frame.kt'), str(output / 'Fixture.kt'), str(output / 'Selection.kt'),
                    *[str(SOURCE / name) for name in ('FaceOutputs.kt', 'StageRegistration.kt',
                       'LabPoseCorrection.kt', 'LabCameraProfile.kt', 'LabIntrinsics.kt',
                       'LabStereoCalibration.kt', 'FaceTrackingPacing.kt', 'FacePoseMeshStabilizer.kt')]], check=True)
    result = subprocess.run([java, '-cp', str(output / 'classes') + os.pathsep + cp,
                    'com.pico.spatial.ml.sample.facelandmarker.FixtureKt', str(output / 'fixtures.json')],
                    text=True, capture_output=True, check=True)
    print(result.stdout)
    report = dict(status='PASS', selectionPolicy='PASS: all masks, all-off and calibration override/restoration', combinations=len(fixtures), publication='bit-exact FP32',
                  blendInputMaximumError=blend_error, kotlin=result.stdout.strip(),
                  boundary='Host CPU LiteRT and production Kotlin; Android runtime/performance not measured')
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--json-jar', default=Path('/private/tmp/face-calibration-tuner/json.jar'), type=Path)
    a = p.parse_args()
    validate(a.output, a.json_jar)
