"""Run shipped JS snapshot packing through the real Kotlin decoder, camera profile and motion gate.

Uses the project's cached Kotlin compiler and Android compile API. Android JSON methods
are not executed in this host fixture. No device or additional Gradle dependency required.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess


def validate(output):
    project = Path(__file__).resolve().parents[2]
    source = project / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    assets = project / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/operators'
    output.mkdir(parents=True, exist_ok=True)
    command, frame = [17, .1, 1, 1], [100, .125, .03, 1, 0, .4]
    producer = dict(command=command, frame=frame, roi=[1, .99, 1650, 1200, 400, .1],
                    affine=[.4, .1, -650, -.1, .4, -300], intrinsics=[2, 0, 3, 0, 4, 5, 0, 0, 1],
                    serviceIntrinsics=[6]*9, imageTransform=[7]*9, leftCameraToXr=[8]*16, labMode=[3])

    def snapshot(name, tensors):
        size = sum(len(v) for v in tensors.values())
        completed = subprocess.run(['node', str(project / 'FaceLandmarkerApp/tools/run_operator.mjs')],
            input=json.dumps(dict(script=str(assets / f'{name}.js'),
                                  tensors=dict(tensors, snapshot=[0]*size)))+'\n',
            text=True, capture_output=True, check=True)
        return json.loads(completed.stdout)['tensors']['snapshot']

    first = snapshot('lab_frame_snapshot', producer)

    def geometry(points, targets, result, upstream):
        return dict(command=command, frame=frame, roi=producer['roi'], affine=producer['affine'],
                    rawLandmarks=[.25]*1434, projected=[.5]*(points*3), firstTargets=[.75]*(targets*3),
                    secondTargets=[1.25]*(targets*3), metric=[1.5]*(points*3), pose=[2.5]*16,
                    rawWorldPose=[3.5]*16, worldPose=[4.5]*16, firstScale=[5.5], secondScale=[6.5],
                    depthOffset=[7.5], intrinsics=producer['intrinsics'],
                    leftCameraToXr=producer['leftCameraToXr'], result=result, upstream=upstream)

    second = snapshot('lab_geometry_snapshot', geometry(33, 33, [0], first))
    final = snapshot('lab_geometry_snapshot', geometry(478, 1, [17]+[0]*2993, second))
    binary = output / 'snapshot.f32'
    binary.write_bytes(struct.pack('<'+'f'*len(final), *final))
    runner = (source / 'FaceLandmarkerRunner.kt').read_text()
    completion = runner[runner.index('internal suspend fun readCompletedFaceResult('):]
    completion = completion[:completion.index('\n/**')]
    completion_source = output / 'FrameCompletionProduction.kt'
    completion_source.write_text('package com.pico.spatial.ml.sample.facelandmarker\n'
                                 'import kotlinx.coroutines.delay\n' + completion)
    graph = (source / 'FaceLandmarkerGraph.kt').read_text()
    mesh = graph[graph.index('    private fun buildMesh('):graph.index('    private fun buildExpressions(')]
    assert mesh.index('"pack_service_result"') < mesh.index('geometryProbe(') < mesh.index(
        'completionMarker(checkNotNull(completedSequence))')
    marker = graph[graph.index('    private fun GraphPipeline.completionMarker('):
                   graph.index('    private fun GraphPipeline.geometryProbe(')]
    assert '"face_completion_marker"' in marker and '"lab_capture_marker"' in marker
    assert 'mapOf("sequence" to sequence)' in marker
    assert 'activeGraph.resultComplete(sequence)' in runner
    fixture = output / 'LabRuntimeFixture.kt'
    fixture.write_text(r'''package com.pico.spatial.ml.sample.facelandmarker
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs
import kotlinx.coroutines.*

internal object SpatialMLGraphSession { const val WIDTH = 3248; const val HEIGHT = 2464 }
internal object FaceFrame { const val RESULT_SIZE = 2994 }
private fun rejected(block: () -> Unit) {
    try { block() } catch (_: IllegalArgumentException) { return }
    error("Invalid capture accepted")
}
private fun pose(x: Float = 0f, angle: Double = 0.0): FloatArray {
    val c = kotlin.math.cos(angle).toFloat(); val s = kotlin.math.sin(angle).toFloat()
    return floatArrayOf(c, -s, 0f, x, s, c, 0f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 0f, 1f)
}
fun main(args: Array<String>) {
    val bytes = File(args[0]).readBytes()
    val values = FloatArray(bytes.size / 4)
    ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(values)
    val probe = LabGeometryProbe(values, 17, 3)
    check(probe.producer.getValue("cropAffine")[2] == -650f)
    check(probe.fit.getValue("firstTargets").size == 99)
    check(probe.fit.getValue("firstTargets").all { it == .75f })
    check(probe.fit.getValue("secondTargets").all { it == 1.25f })
    check(probe.mesh.getValue("metricVerticesCm").size == 1434)
    check(probe.mesh.getValue("metricVerticesCm").all { it == 1.5f })
    check(probe.mesh.getValue("rawWorldPose").all { it == 3.5f })
    check(probe.mesh.getValue("filteredWorldPose").all { it == 4.5f })
    val packet = probe.mesh.getValue("result").copyOf()
    check(probe.resultMatches(packet))
    val negativeZero = packet.copyOf().also { it[1] = -0.0f }
    check(!probe.mesh.getValue("result").contentEquals(negativeZero))
    check(probe.resultMatches(negativeZero))
    check(!probe.resultMatches(packet.copyOf().also { it[1] = 1e-12f }))
    check(!probe.resultMatches(packet.copyOf().also { it[1] = Float.MIN_VALUE }))
    check(!probe.resultMatches(packet.copyOf().also { it[1] = Float.NaN }))
    check(!probe.resultMatches(packet.copyOf(packet.size - 1)))
    runBlocking {
        // The service can publish a current header with an old tail. Reading that header
        // cannot authorize presentation; the separately committed last operator must finish.
        var committed = 16
        val torn = packet.copyOf().also { it[2733] = 9f }
        var reads = 0
        val completed = async {
            readCompletedFaceResult(17, { committed == 17 }) {
                reads += 1
                torn.copyOf()
            }
        }
        yield()
        check(reads == 0 && !completed.isCompleted)
        torn[2733] = packet[2733]
        committed = 17
        val coherent = completed.await()
        check(reads == 1 && probe.resultMatches(coherent))
        var staleReads = 0
        val retried = readCompletedFaceResult(17, { true }) {
            staleReads += 1
            packet.copyOf().also { if (staleReads == 1) it[0] = 16f }
        }
        check(staleReads == 2 && probe.resultMatches(retried))
        val timeout = runCatching {
            withTimeout(20) {
                readCompletedFaceResult(18, { false }) { error("Read before completion") }
            }
        }.exceptionOrNull()
        check(timeout is TimeoutCancellationException)
        // The optional 1 ms policy preserves the same barrier and can be cancelled while waiting.
        committed = 16
        reads = 0
        val eager = async {
            readCompletedFaceResult(17, { committed == 17 }, pollMillis = 1) {
                reads += 1
                packet.copyOf()
            }
        }
        yield()
        check(reads == 0 && !eager.isCompleted)
        committed = 17
        check(probe.resultMatches(eager.await()) && reads == 1)
        val cancelled = async {
            readCompletedFaceResult(18, { false }, pollMillis = 1) {
                error("Read before terminal publication")
            }
        }
        yield()
        cancelled.cancelAndJoin()
        check(cancelled.isCancelled)
    }
    val fitOffset = values.size - LabGeometryProbe.fitFields.values.sum()
    val producerOffset = values.size - LabGeometryProbe.producerFields.values.sum()
    for (offset in listOf(0, fitOffset, producerOffset)) {
        rejected { LabGeometryProbe(values.copyOf().also { it[offset] += 1 }, 17, 3) }
    }
    rejected { LabGeometryProbe(values.copyOf().also { it[fitOffset + 4] += 1 }, 17, 3) }
    rejected { LabGeometryProbe(values, 17, 2) }
    rejected { LabGeometryProbe(values.copyOf().also { it[50] = Float.NaN }, 17, 3) }
    rejected { LabGeometryProbe(values.copyOf(values.size - 1), 17, 3) }

    val still = (0..400).map { i -> i / 100.0 to pose(if (i > 150) .04f else 0f) }
    check(LabMotion.measure(still, .95, 1.05).stable)
    check(!LabMotion.measure(still, .5, 3.95).stable)
    val translation = still.map { (t, _) -> t to pose(if (t >= 1) .011f else 0f) }
    check(!LabMotion.measure(translation, .95, 1.05).stable)
    val rotation = still.map { (t, _) -> t to pose(angle = if (t >= 1) Math.toRadians(1.1) else 0.0) }
    check(!LabMotion.measure(rotation, .95, 1.05).stable)
    check(!LabMotion.measure(still.filter { it.first !in .9..1.1 }, .95, 1.05).covered)
    check(!LabMotion.measure(still.drop(100), .95, 1.05).covered)
    check(!LabMotion.measure(emptyList(), .95, 1.05).stable)

    check(LabCameraProfile.configuration(0, "other").first.contentEquals(LabCameraProfile.identity))
    for (mode in 1 until LabCameraProfile.MODE_COUNT) rejected { LabCameraProfile.configuration(mode, "other") }
    rejected { LabCameraProfile.configuration(LabCameraProfile.MODE_COUNT, LabCameraProfile.FINGERPRINT) }
    check(LabCameraProfile.configuration(LabCameraProfile.CUSTOM_MODE, LabCameraProfile.FINGERPRINT).second.contentEquals(LabIntrinsics.modeC.matrix()))
    val (a, k) = LabCameraProfile.configuration(3, LabCameraProfile.FINGERPRINT)
    check(abs(a[0] - .7673501372337341f) < 1e-7f && a[2] == 377.70703125f)
    check(abs(k[0] - 2642.704699f) < .001f && abs(k[4] - 2036.955265f) < .001f)
    check(abs(a[0] * k[0] - 2027.879814f) < .001f)
    check(abs(a[0] * k[2] + a[2] - 1661.005689f) < .001f)
    println("PASS: terminal completion before packet read; stale packet retry and bounded timeout; shipped JS -> Kotlin snapshot decode; signed-zero numeric equivalence; real packet/size/NaN mismatch rejection; stale frame/mode rejection; exposure vs export motion; measured profile and ROM guards")
}
''')
    cache = Path.home() / '.gradle/caches/modules-2/files-2.1'

    def jar(group, artifact, version):
        return next((cache / group / artifact / version).glob('*/*.jar'))

    stdlib = jar('org.jetbrains.kotlin', 'kotlin-stdlib', '2.0.21')
    compiler = [jar('org.jetbrains.kotlin', name, '2.0.21') for name in
                ('kotlin-compiler-embeddable', 'kotlin-script-runtime', 'kotlin-reflect', 'kotlin-daemon-embeddable')]
    compiler += [stdlib, jar('org.jetbrains', 'annotations', '13.0'),
                 jar('org.jetbrains.intellij.deps', 'trove4j', '1.0.20200330'),
                 jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.6.4')]
    android = Path.home() / 'Library/Android/sdk/platforms/android-35/android.jar'
    java = Path(os.environ.get('JAVA_HOME', '/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home')) / 'bin/java'
    classes = output / 'classes'
    cp = os.pathsep.join(map(str, [stdlib, android,
        jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.6.4')]))
    subprocess.run([str(java), '-cp', os.pathsep.join(map(str, compiler)),
                    'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-no-stdlib', '-no-reflect',
                    '-classpath', cp, '-d', str(classes), str(fixture), str(completion_source),
                    *[str(source / name) for name in ('LabGeometryProbe.kt', 'LabMotion.kt', 'LabCameraProfile.kt', 'LabStereoCalibration.kt', 'LabIntrinsics.kt')]], check=True)
    subprocess.run([str(java), '-cp', str(classes)+os.pathsep+cp,
                    'com.pico.spatial.ml.sample.facelandmarker.LabRuntimeFixtureKt', str(binary)], check=True)
    (output / 'runtime-validation.json').write_text(json.dumps(dict(
        boundary='Host fixtures only; not native execution or physical alignment acceptance.',
        producer_elements=len(first), fit_elements=len(second), mesh_elements=len(final),
        terminal_completion_regressions='PASS', javascript_to_kotlin_decode='PASS',
        exposure_motion_regressions='PASS', measured_rom_profile='PASS'), indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    validate(parser.parse_args().output)
