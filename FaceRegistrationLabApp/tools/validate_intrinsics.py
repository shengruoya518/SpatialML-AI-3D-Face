"""Exercise shipped tuning state, profile codec/store, graph resets and packet decoding.

Requires a real org.json JAR (--json-jar). Android storage/context have small host
adapters: this checks app logic, not Android AtomicFile or headset rendering.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess


def validate(output, json_jar):
    project = Path(__file__).resolve().parents[2]
    source = project / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    operators = project / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/operators'
    output.mkdir(parents=True, exist_ok=True)
    packets = []
    for dt, fresh in [(0, 1), (.03, 0), (.03, 1), (0, 0)]:
        tensors = dict(projected=[0]*1434, metric=[0]*1434, canonical=[0]*1912,
                       pose=[0]*16, validity=[0], roi=[0]*6, intrinsics=[1700,0,1600,0,1800,1200,0,0,1],
                       frame=[100,.125,dt,fresh,0,0], command=[17,.1,1,1],
                       trackState=[0]*24, poseStatus=[0], diagnostics=[0]*32)
        completed = subprocess.run(['node', str(project / 'FaceLandmarkerApp/tools/run_operator.mjs')],
            input=json.dumps(dict(script=str(operators / 'registration_diagnostics.js'), tensors=tensors))+'\n',
            text=True, capture_output=True, check=True)
        diagnostics = json.loads(completed.stdout)['tensors']['diagnostics']
        assert diagnostics[3] == dt and diagnostics[30] == fresh
        packet = [0.0]*2994
        packet[0] = 17
        packet[2946:2978] = diagnostics
        packets.extend(packet)
    (output / 'packets.f32').write_bytes(struct.pack('<'+'f'*len(packets), *packets))

    # Real raw headset packets independently exercise the new registration translation.
    captured = project / 'artifacts/facelandmarker/registration-lab/roll-trial-2026-11-05-b8c6a3/2026-11-05T02-30-39.647895Z-b8c6a3'
    samples = []
    for path in sorted(captured.glob('*/sample.json')):
        value = json.loads(path.read_text())
        value['sourcePath'] = str(path.resolve())
        samples.append(value)
    (output / 'pose-comparison-input.json').write_text(json.dumps(samples))
    (output / 'stereo-profile.json').write_text((project / 'FaceRegistrationLabApp/calibration/stereo-face-existing-data-2026-11-06.json').read_text())

    # Execute production methods, including constructor/autoload and asynchronous persistence.
    lab = (source / 'FaceRegistrationLab.kt').read_text()
    lab_code = lab[:lab.index('    suspend fun publishPreview')]
    companion = lab[lab.index('    companion object {'):lab.index('        private fun floats')]
    (output / 'FaceRegistrationLab.kt').write_text(lab_code + companion + '    }\n}\n')
    runner = (source / 'FaceLandmarkerRunner.kt').read_text()
    assert 'acquire || evidenceRequested || frameCalibration != previousCalibration' in runner
    assert 'val acquireFrame = lab != null || acquire' not in runner
    frame_code = runner[runner.index('internal class FaceFrame('):]
    graph = (source / 'FaceLandmarkerGraph.kt').read_text()
    graph_method = graph[graph.index('    fun setCalibration('):graph.index('    fun submitCapture()')]
    (output / 'HostContext.kt').write_text('''package android.content
import java.io.File
open class Context(val filesDir: File, private val external: File) {
    val applicationContext get() = this
    val packageName = "test.registrationlab"
    fun getExternalFilesDir(type: String?): File = external
    fun registerReceiver(r: BroadcastReceiver, f: IntentFilter, p: String, h: Any?, flags: Int = 0) {}
    fun unregisterReceiver(r: BroadcastReceiver) {}
    companion object { const val RECEIVER_EXPORTED = 2 }
}
abstract class BroadcastReceiver { var resultCode = 0; var resultData: String? = null; abstract fun onReceive(context: Context, intent: Intent) }
class Intent(private val extras: Map<String, String> = emptyMap()) { fun getStringExtra(key: String): String? = extras[key] }
class IntentFilter(val action: String)
''')
    (output / 'HostBuild.kt').write_text('''package android.os
object Build {
    const val FINGERPRINT = "Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys"
    object VERSION { const val SDK_INT = 35 }
}
''')
    (output / 'HostStorage.kt').write_text('''package android.util
import java.io.File
import java.io.FileOutputStream
class AtomicFile(val baseFile: File) {
    private val staged get() = File(baseFile.path + ".new")
    fun readFully() = baseFile.readBytes()
    fun startWrite(): FileOutputStream { baseFile.parentFile.mkdirs(); return FileOutputStream(staged) }
    fun finishWrite(stream: FileOutputStream) { stream.close(); check(staged.renameTo(baseFile)) }
    fun failWrite(stream: FileOutputStream) { stream.close(); staged.delete() }
}
object Base64 { const val NO_WRAP = 2; fun encodeToString(bytes: ByteArray, flags: Int) = java.util.Base64.getEncoder().encodeToString(bytes) }
object Log {
    fun i(tag: String, message: String) = 0
    fun w(tag: String, message: String, error: Throwable) = 0
}
''')
    (output / 'IntrinsicsFixture.kt').write_text('''package com.pico.spatial.ml.sample.facelandmarker
import android.content.Context
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.hypot
import kotlin.math.abs
import org.json.JSONObject
internal object SpatialMLGraphSession { const val WIDTH = 3248; const val HEIGHT = 2464 }
internal object FaceLandmarkerRunner { const val TAG = "HostFixture" }
''' + frame_code + '''
private class GraphHarness {
    val lab = true
    var calibrationMode = -1
    var calibrationRevision = -1
    var appliedCustom: LabIntrinsics? = null
    var diagnosticImageTransform = FloatArray(9)
    val imageTransform = "image"
    val compactDetectorMapping = "detector_mapping"
    val trialIntrinsics = "intrinsics"
    val labMode = "mode"
    val trackState = "clock"
    val poseState = "pose"
    val session = Session()
    class Session {
        val resets = mutableMapOf<String, FloatArray>()
        fun reset(name: String, values: FloatArray) { resets[name] = values.copyOf() }
    }
''' + graph_method + '''
}
private fun rejected(block: () -> Unit) {
    try { block() } catch (_: Exception) { return }
    error("Invalid input accepted")
}
private fun awaitIo(lab: FaceRegistrationLab) {
    val until = System.nanoTime() + 5_000_000_000L
    while (lab.ui.value.profileBusy && System.nanoTime() < until) Thread.sleep(5)
    check(!lab.ui.value.profileBusy) { "Persistence timed out" }
}
private fun countdown(lab: FaceRegistrationLab, expired: Boolean = false) {
    val field = lab.javaClass.getDeclaredField("saveAfter")
    field.isAccessible = true
    field.setDouble(lab, System.nanoTime()*1e-9 - (if (expired) 16.0 else .01))
}
fun main(args: Array<String>) {
    val root = File(args[0], "run-" + System.nanoTime()).apply { mkdirs() }
    val context = Context(File(root, "private"), File(root, "external"))
    val c = LabIntrinsics.modeC
    val values = LabIntrinsics(1699.5f, 1720.25f, 1612f, 1209f)
    for (p in IntrinsicParameter.entries) {
        val adjusted = c.adjusted(p, c.value(p) + 5)
        for (other in IntrinsicParameter.entries) check(adjusted.value(other) == c.value(other) + if (p == other) 5 else 0)
        check(c.adjusted(p, -1f).value(p) == p.range.start)
        check(c.adjusted(p, 99999f).value(p) == p.range.endInclusive)
    }
    rejected { c.adjusted(IntrinsicParameter.FX, Float.NaN) }
    rejected { c.copy(fy = 0f) }
    rejected { c.copy(cx = Float.POSITIVE_INFINITY) }
    check(LabCalibrationStore.decode(JSONObject(LabCalibrationStore.encode(values).toString())) == values)
    for ((key, invalid) in listOf("schema" to 2, "profileType" to "source-camera", "fingerprint" to "other-ROM",
            "nativeWidth" to 1624, "nativeHeight" to 1232, "coordinateSpace" to "source", "fx" to 0,
            "fy" to 7000, "cx" to -1, "cy" to 2465)) {
        rejected { LabCalibrationStore.decode(LabCalibrationStore.encode(values).put(key, invalid)) }
    }
    rejected { LabCalibrationStore.decode(LabCalibrationStore.encode(values).apply { getJSONArray("cameraIntrinsics").put(2, 999) }) }
    rejected { LabCalibrationStore.decode(LabCalibrationStore.encode(values).apply { getJSONArray("imageTransform").put(0, 1) }) }
    val store = LabCalibrationStore(context)
    check(store.load() == null)
    val archive = store.save(values)
    check(archive.exists() && store.load() == values)
    check(JSONObject(File(context.getExternalFilesDir(null), "RegistrationLabProfiles/saved-calibration.json").readText()).getDouble("fx").toFloat() == values.fx)
    store.save(c)
    check(archive.exists() && store.load() == c)

    val lab = FaceRegistrationLab(context)
    check(lab.configuration() == LabCameraConfiguration(5, c, 0))
    check(lab.poseCorrection().stereo)
    val beforeSmoothing = lab.frameSettings()
    check(lab.stabilizeMesh())
    lab.toggleMeshStabilization(); check(!lab.stabilizeMesh())
    lab.toggleMeshStabilization(); check(lab.stabilizeMesh())
    check(lab.frameSettings() == beforeSmoothing) // Presentation filtering cannot change K/D.
    lab.adjust(IntrinsicParameter.FX, values.fx)
    val requested = lab.configuration()
    lab.markFrame(requested.copy(revision = 0), 1, true, "Ready")
    check(!lab.ui.value.ready)
    lab.markFrame(requested, 2, true, "Ready")
    check(lab.ui.value.ready)
    lab.queueSave()
    check(!lab.stabilizeMesh()) // Raw manual calibration exports bypass the display filter.
    lab.toggleMeshStabilization(); check(lab.ui.value.stabilizeMesh)
    lab.adjust(IntrinsicParameter.CY, 1000f); lab.nextStep(); lab.cycleMode()
    check(lab.configuration() == requested && lab.ui.value.step == 0)
    check(lab.takeSave(requested, true, "Ready") == null) // countdown
    countdown(lab)
    check(lab.takeSave(requested.copy(revision = 0), true, "Old values") == null)
    check(lab.takeSave(requested, false, "No face") == null && lab.ui.value.pending)
    val save = lab.takeSave(requested, true, "Ready")
    check(save == LabSaveRequest(0, 0, requested, poseCorrection = lab.poseCorrection()))
    check(lab.takeSave(requested, true, "Ready") == null && lab.ui.value.saving)
    lab.imageCaptured()
    val message = lab.ui.value.message
    lab.markFrame(requested, 3, true, "Ready")
    check(lab.ui.value.message == message)
    lab.fail("Fixture export failure")
    lab.queueSave(); countdown(lab, true)
    check(lab.takeSave(requested, false, "No face") == null)
    check(!lab.ui.value.pending && !lab.ui.value.locked && lab.ui.value.message.contains("No usable frame"))
    lab.fail("Camera stopped", fatal = true)
    lab.saveValues(); awaitIo(lab) // no camera, face or eligible frame
    check(lab.ui.value.stopped && lab.ui.value.savedProfileAvailable)
    check(store.load() == requested.custom)
    lab.close()
    val remote = FaceRegistrationLab(context)
    fun command(vararg entries: Pair<String,String>): JSONObject {
        val f = remote.javaClass.getDeclaredField("commands").apply { isAccessible = true }
        val receiver = f.get(remote) as android.content.BroadcastReceiver
        receiver.onReceive(context, android.content.Intent(mapOf(*entries)))
        return JSONObject(String(java.util.Base64.getDecoder().decode(checkNotNull(receiver.resultData).removePrefix("FACE_LAB_V1:"))))
    }
    val initial = command("command" to "status")
    check(initial.getBoolean("accepted") && initial.isNull("appliedValues"))
    val sent = command("command" to "set", "parameter" to "cy", "value" to "1200.5")
    check(sent.getBoolean("accepted") && sent.getJSONObject("values").getDouble("cy") == 1200.5)
    check(sent.getInt("revision") == initial.getInt("revision") + 1)
    val beforeAutomatic = remote.configuration()
    check(command("command" to "auto_check").getBoolean("accepted"))
    check(command("command" to "status").getJSONObject("automatic").getBoolean("active"))
    check(!command("command" to "set", "parameter" to "cy", "value" to "1205").getBoolean("accepted"))
    check(!command("command" to "save_values").getBoolean("accepted"))
    check(command("command" to "auto_cancel").getBoolean("accepted"))
    check(remote.configuration().custom == beforeAutomatic.custom)
    check(remote.configuration().revision > beforeAutomatic.revision)
    check(store.load() == requested.custom) // automatic runs never save a calibration profile
    val config = remote.configuration()
    remote.markFrame(config, 51, true, "Ready", config.custom.matrix(), true)
    val received = command("command" to "status")
    check(received.getJSONObject("appliedValues").getDouble("cy") == 1200.5)
    check(received.getInt("frame") == 51 && received.getBoolean("hasFace"))
    for (bad in listOf("NaN", "Infinity", "-1", "2465", "oops"))
        check(!command("command" to "set", "parameter" to "cy", "value" to bad).getBoolean("accepted"))
    check(!command("command" to "erase").getBoolean("accepted"))
    remote.queueSave()
    check(!command("command" to "set", "parameter" to "fx", "value" to "1700").getBoolean("accepted"))
    check(command("command" to "status").getBoolean("accepted"))
    check(remote.configuration() == config)
    remote.fail("stopped", fatal = true)
    check(command("command" to "status").getBoolean("stopped"))
    remote.close()
    val restored = FaceRegistrationLab(context)
    check(restored.configuration().custom == requested.custom)
    restored.resetToC()
    check(restored.configuration().custom == c)
    restored.loadValues(); awaitIo(restored)
    check(restored.configuration().custom == requested.custom)
    restored.close()
    File(context.filesDir, "face-intrinsics-calibration-v1.json").writeText("broken JSON")
    val corrupt = FaceRegistrationLab(context)
    check(corrupt.configuration().custom == c && !corrupt.ui.value.savedProfileAvailable)
    check(corrupt.ui.value.profileMessage.contains("could not be loaded"))
    corrupt.close()

    val g = GraphHarness()
    g.setCalibration(LabCameraConfiguration(4, c, 0))
    check(g.session.resets.getValue("detector_mapping").contentEquals(
        CompactFaceDetector.toImage(LabCameraProfile.preservedImageAffine)))
    // A compact detector samples raw camera coordinates, while ROI/crop state is calibrated.
    // Off-center source points catch omission or double application of the image transform.
    for (mode in 0 until LabCameraProfile.MODE_COUNT) {
        val transform = LabCameraProfile.configuration(mode, android.os.Build.FINGERPRINT).first
        val mapping = CompactFaceDetector.toImage(transform)
        for (x in listOf(400f, 1624f, 2800f)) for (y in listOf(200f, 1232f, 2200f)) {
            val dx = x * CompactFaceDetector.VST_SIZE / SpatialMLGraphSession.WIDTH - CompactFaceDetector.CROP_X
            val dy = y * CompactFaceDetector.VIEW_HEIGHT / SpatialMLGraphSession.HEIGHT
            check(abs(mapping[0]*dx + mapping[2] - (transform[0]*x + transform[2])) < .001f)
            check(abs(mapping[1]*dy + mapping[3] - (transform[4]*y + transform[5])) < .001f)
        }
    }
    g.session.resets.clear()
    g.setCalibration(LabCameraConfiguration(4, values, 1))
    check("clock" !in g.session.resets && "pose" in g.session.resets)
    check(values.matches(g.session.resets.getValue("intrinsics")))
    g.session.resets.clear()
    g.setCalibration(LabCameraConfiguration(4, values, 1))
    check(g.session.resets.isEmpty())
    g.setCalibration(LabCameraConfiguration(0, values, 2))
    check("clock" in g.session.resets)

    val bytes = File(args[0], "packets.f32").readBytes()
    val packets = FloatArray(bytes.size/4)
    ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(packets)
    for ((i, expected) in listOf(true, false, true, false).withIndex()) {
        val frame = FaceFrame(packets.copyOfRange(i*2994, (i+1)*2994))
        check(frame.freshCameraFrame == expected && frame.captureSeconds == 100.125)
        check(LabIntrinsics(1700f,1800f,1600f,1200f).matches(frame.effectiveIntrinsics))
    }
    val timelineFolder = File(root, "timeline-fixture")
    val timeline = LabTimeline(timelineFolder, 100_000_000_000L)
    val timingPacket = packets.copyOfRange(0, 2994).apply { this[1] = 1f }
    val identity = floatArrayOf(1f,0f,0f,0f,0f,1f,0f,0f,0f,0f,1f,0f,0f,0f,0f,1f)
    val posePacket = timingPacket.copyOf().also {
        identity.copyInto(it, FaceFrame.POSE_OFFSET)
        it[FaceFrame.POSE_OFFSET+11] = -1.2f
        for (i in 0 until 478) it[FaceFrame.VERTEX_OFFSET+i*3+2] = -1.2f
    }
    val meshOnly = FaceFrame(posePacket, outputs=FaceOutputs(2))
    check(meshOnly.pose.isEmpty() && meshOnly.geometryPose.size == 16)
    val translated = identity.copyOf().also { it[3] = .05f }
    val rebased = meshOnly.inStage(translated)
    check(abs(rebased.geometryPose[3]-.05f)<1e-6 && rebased.pose.isEmpty())
    val filter = FacePoseMeshStabilizer()
    filter.update(rebased.vertices,rebased.geometryPose,100.0,1f,"fixture")
    val shiftedPacket = rebased.packet().also {
        it[FaceFrame.POSE_OFFSET+3] += .005f
        for (i in 0 until 478) it[FaceFrame.VERTEX_OFFSET+i*3] += .005f
    }
    val rawDisplay = FaceFrame(shiftedPacket, outputs=FaceOutputs(2))
    val unchangedRaw = rawDisplay.packet()
    val displayed = rawDisplay.withPresentationGeometry(filter.update(rawDisplay.vertices,
        rawDisplay.geometryPose,100.06,1f,"fixture"))
    check(rawDisplay.packet().contentEquals(unchangedRaw))
    check(displayed.geometryPose[3]<rawDisplay.geometryPose[3] && displayed.pose.isEmpty())
    check(displayed.presentationStabilization?.getString("algorithm")=="pose-and-local-shape-v2")
    check(displayed.presentationStabilization?.getString("responseProfile")=="balanced")
    check(displayed.withAutomatic(null).presentationStabilization != null)
    // Camera acquisition follows the existing ROI unless a detection, evidence capture or
    // calibration transition requires acquisition. Inspect the actual submit call policy.
    val olderFrame = FaceFrame(timingPacket, LabCameraConfiguration(4, c, 7), 100.2).inStage(identity)
    check(olderFrame.labConfiguration?.revision == 7 && olderFrame.readbackSeconds == 100.2)
    timeline.meshApplied(olderFrame, true, 100_300_000_000L)
    timeline.tick(100_500_000_000L)
    val badge = timeline.ui.value
    check(badge.mesh?.revision == 7 && badge.mesh?.sequence == 17)
    check(badge.elapsedSeconds == .5 && badge.cameraElapsedSeconds == .125)
    check(badge.text().contains("UI 0.500 s | CAM 0.125 s"))
    check(badge.text().contains("F17 K7 M4 | MESH"))
    timeline.visibilityChanged(false)
    check(timeline.ui.value.text().contains("HIDDEN"))
    timeline.meshApplied(null, false)
    check(timeline.ui.value.mesh == null && timeline.ui.value.text().contains("NO MESH"))
    timeline.close()
    val stoppedTick = timeline.ui.value.tick
    timeline.tick()
    check(timeline.ui.value.tick == stoppedTick)
    val until = System.nanoTime() + 5_000_000_000L
    var rows = emptyList<JSONObject>()
    while (System.nanoTime() < until) {
        rows = runCatching { timeline.file.readLines().filter { it.isNotBlank() }.map(::JSONObject) }.getOrDefault(emptyList())
        if (rows.lastOrNull()?.optString("event") == "close") break
        Thread.sleep(5)
    }
    check(rows.first().getLong("originNanos") == 100_000_000_000L)
    check(rows.last().getString("event") == "close")
    val recorded = rows.single { it.optString("event") == "ui_tick" && it.getLong("tick") == badge.tick }
    check(recorded.getDouble("relativeSeconds") == badge.elapsedSeconds)
    check(recorded.getJSONObject("mesh").getInt("revision") == 7)
    check(recorded.getJSONObject("mesh").getDouble("captureRelativeSeconds") == .125)
    // The production automatic controller runs with deterministic time and real packet decoding.
    val auto = LabAutoCapture()
    val originalConfig = LabCameraConfiguration(4, values, 15)
    auto.start("fixture", originalConfig, true, 0.0)
    auto.tick(14.0); check(auto.ui.phase == "COUNTDOWN")
    auto.tick(15.0); check(auto.ui.phase == "POSE" && auto.configuration?.custom == c)
    auto.tick(23.0); check(auto.ui.phase == "SETTLE")
    var clock = 23.0
    var seq = 100
    fun autoFrame(controller: LabAutoCapture, now: Double, good: Boolean = true): FaceFrame {
        val conf = checkNotNull(controller.configuration)
        val packet = FloatArray(2994)
        packet[0] = (++seq).toFloat(); packet[1] = 1f
        val exposure = now - .4
        packet[2947] = exposure.toInt().toFloat(); packet[2948] = (exposure-exposure.toInt()).toFloat()
        packet[2958] = conf.custom.fx; packet[2959] = conf.custom.fy
        packet[2960] = conf.custom.cx; packet[2961] = conf.custom.cy
        packet[2976] = if (good) 1f else 0f
        for ((n, id) in LabAutoCapture.markerIds.withIndex()) {
            packet[FaceFrame.VERTEX_OFFSET + id*3] = n*.015f
            packet[FaceFrame.VERTEX_OFFSET + id*3 + 2] = 1f
        }
        return FaceFrame(packet, conf, now)
    }
    check(auto.frame(autoFrame(auto, clock), false, true, clock) == null)
    // Face-independent board captures require new exposures, stable measured head poses,
    // Mode A, exact scene acknowledgements and zero correction. No dummy face geometry.
    fun boardFrame(controller: LabAutoCapture, now: Double, head: FloatArray = identity): FaceFrame {
        val p = autoFrame(controller, now).packet()
        p[1] = 0f
        for (i in FaceFrame.VERTEX_OFFSET until FaceFrame.VERTEX_OFFSET + 478*3) p[i] = 0f
        return FaceFrame(p, controller.configuration, now, registrationEvidence = LabRegistrationEvidence(head, identity, identity))
    }
    for (kind in LabBoardCapture.kinds) {
        val board = LabAutoCapture()
        board.start("board-fixture", originalConfig, true, 100.0, boardKind = kind)
        var time = 100.0
        val captures = mutableListOf<LabAutoTag>()
        while (board.ui.active && time < 800) {
            time += .2
            board.tick(time)
            val frame = boardFrame(board, time)
            val tag = board.frame(frame, true, true, time)
            board.sceneApplied(board.tag, frame.sequence, time)
            if (tag != null) {
                check(!frame.hasFace && board.configuration!!.mode == 0)
                check(tag.board && tag.sideReferences && tag.boardKind == kind)
                check(tag.markers == (kind != LabBoardCapture.VIEWS))
                check(board.sceneMatches(tag, frame.sequence))
                captures.add(tag)
                board.saved(tag, time + .01)
            }
        }
        check(board.ui.phase == "DONE" && captures.size == LabBoardCapture.count(kind))
        check(board.configuration == null)
        check(captures.groupBy { it.pose }.values.all { it.size == if (kind == LabBoardCapture.VIEWS) 1 else 3 })
    }
    val boardGuard = LabAutoCapture()
    boardGuard.start("board-guard", originalConfig, true, 100.0, boardKind = LabBoardCapture.CHECK)
    boardGuard.tick(123.0); boardGuard.tick(131.0)
    val repeatedBoard = boardFrame(boardGuard, 131.0)
    repeat(20) { check(boardGuard.frame(repeatedBoard, true, true, 131.0 + it*.02) == null) }
    check(boardGuard.ui.saved == 0 && boardGuard.ui.phase == "SETTLE")
    val beforeMotion = identity.copyOf().also { it[3] = .004f }
    check(!LabBoardCapture.stationary(identity.toList(), beforeMotion))
    check(!LabBoardCapture.stationary(emptyList(), identity))
    boardGuard.stop(); check(boardGuard.configuration == null && !boardGuard.ui.active)
    val boardLab = FaceRegistrationLab(Context(File(root,"board-profile"), File(root,"board-external")))
    val beforeBoard = boardLab.configuration()
    boardLab.toggleDiagnosticPreview()
    check(boardLab.ui.value.showCaptureTools)
    boardLab.togglePoseCorrection()
    val correctionBeforeBoard = boardLab.poseCorrection()
    boardLab.startAutomatic(single=true, boardKind=LabBoardCapture.CHECK)
    check(!boardLab.poseCorrection().enabled && !boardLab.ui.value.showCaptureTools)
    boardLab.cancelAutomatic()
    check(boardLab.poseCorrection().enabled == correctionBeforeBoard.enabled && boardLab.ui.value.showCaptureTools)
    check(boardLab.configuration().mode == beforeBoard.mode && boardLab.configuration().custom == beforeBoard.custom)
    boardLab.close()
    println("PASS: board check / 16 source views / 8 holds without a face; repeated exposure and motion gates; correction/configuration restoration")

    val requests = mutableListOf<LabAutoTag>()
    while (auto.ui.active && clock < 60) {
        clock += .5
        val frame = autoFrame(auto, clock)
        val request = auto.frame(frame, true, true, clock)
        val tag = auto.tag
        // A save cannot proceed without a scene acknowledgement for that exact frame.
        if (request != null) {
            check(!auto.sceneMatches(request, frame.sequence))
            requests.add(request)
        }
        auto.sceneApplied(tag, frame.sequence, clock)
        if (request != null) {
            check(auto.sceneMatches(request, frame.sequence))
            check(!auto.sceneMatches(request.copy(epoch = request.epoch-1), frame.sequence))
            check(auto.frame(frame, true, true, clock) == null) // no duplicate save while exporting
            auto.saved(request, clock + .1)
        }
    }
    check(auto.ui.phase == "DONE" && auto.ui.saved == 3 && auto.configuration == null)
    check(requests.map { it.phase } == listOf("CLEAN_BEFORE", "MARKED", "CLEAN_AFTER"))
    auto.start("full", originalConfig, false, 0.0)
    clock = 23.0; auto.tick(15.0); auto.tick(clock)
    val fullRequests = mutableListOf<LabAutoTag>()
    while (auto.ui.active && clock < 1500) {
        clock += .5
        auto.tick(clock)
        if (!auto.ui.active) break
        val frame = autoFrame(auto, clock)
        val request = auto.frame(frame, true, true, clock)
        auto.sceneApplied(auto.tag, frame.sequence, clock)
        if (request != null) { fullRequests.add(request); auto.saved(request, clock + .1) }
    }
    check(auto.ui.phase == "DONE" && fullRequests.size == 84)
    check(fullRequests.groupBy { it.pose }.values.all { it.size == 21 })
    check(fullRequests.chunked(3).all { it.map { t -> t.phase } == listOf("CLEAN_BEFORE", "MARKED", "CLEAN_AFTER") })
    val candidateOrder = listOf("C", "F98", "F97", "Y40", "Y75", "Y110", "C-repeat")
    check(LabAutoCapture.candidates.map { it.id } == candidateOrder)
    for ((pose, group) in fullRequests.groupBy { it.pose }) {
        check(group.chunked(3).map { it.first().candidate } == if (pose%2 == 0) candidateOrder else candidateOrder.reversed())
    }
    check(LabAutoCapture.candidates[2].values.fx == c.fx*.97f && LabAutoCapture.candidates[2].values.fy == c.fy*.97f)
    check(LabAutoCapture.candidates.slice(3..5).map { it.values.cy } == listOf(c.cy-40f, c.cy-75f, c.cy-110f))
    check(LabAutoCapture.candidates.all { it.values.cx == c.cx })
    check(LabAutoCapture.candidates.first().values == LabAutoCapture.candidates.last().values)
    auto.start("binocular", originalConfig, false, 0.0, geometry = true)
    clock = 23.0; auto.tick(15.0); auto.tick(clock)
    val geometryRequests = mutableListOf<LabAutoTag>()
    while (auto.ui.active && clock < 1500) {
        clock += .5; auto.tick(clock)
        if (!auto.ui.active) break
        val frame = autoFrame(auto, clock)
        check(frame.labConfiguration?.custom == c)
        val request = auto.frame(frame, true, true, clock)
        auto.sceneApplied(auto.tag, frame.sequence, clock)
        if (request != null) { geometryRequests.add(request); auto.saved(request, clock + .1) }
    }
    check(auto.ui.phase == "DONE" && geometryRequests.size == 30)
    check(geometryRequests.all { it.protocol == LabProjectionReference.PROTOCOL && it.poseLabel.isNotEmpty() && it.candidate == "C" })
    check(geometryRequests.map { it.pose }.distinct() == (0..9).toList())
    auto.start("geometry-check", originalConfig, true, 0.0, geometry = true)
    check(auto.ui.total == 1)
    auto.tick(15.0)
    check(auto.tag?.protocol == LabProjectionReference.PROTOCOL && auto.configuration?.custom == c)
    auto.stop()
    // Roll targets use measured capture-head transforms, independent of prompt names.
    fun rotation(yaw: Double = 0.0, pitch: Double = 0.0, roll: Double = 0.0): FloatArray {
        fun matrix(axis: Int, angle: Double): FloatArray {
            val a = Math.toRadians(angle); val c = kotlin.math.cos(a).toFloat(); val s = kotlin.math.sin(a).toFloat()
            val r = identity.copyOf()
            val u = (axis+1)%3; val v = (axis+2)%3
            r[u*4+u]=c; r[v*4+v]=c; r[u*4+v]=-s; r[v*4+u]=s
            return r
        }
        return StageRegistration.multiply(StageRegistration.multiply(matrix(1,yaw),matrix(0,pitch)),matrix(2,roll))
    }
    val baselineHead = rotation(23.0, -8.0, 3.0).also { it[3]=.4f; it[7]=1.2f; it[11]=-.3f }
    val measured = LabRollCapture.motion(baselineHead.toList(), StageRegistration.multiply(baselineHead, rotation(2.0,-1.0,15.0)))!!
    check(kotlin.math.abs(measured.roll-15f)<.001 && kotlin.math.abs(measured.yaw-2f)<.001 && kotlin.math.abs(measured.pitch+1f)<.001)
    check(measured.ready(1) && !measured.ready(2))
    check(!LabRollCapture.motion(baselineHead.toList(), StageRegistration.multiply(baselineHead, rotation(yaw=15.0)))!!.ready(1))
    check(!LabRollCapture.validHead(identity.copyOf().also { it[0]=-1f }))
    check(LabRollCapture.motion(baselineHead.toList(), FloatArray(16)) == null)
    fun rollFrame(controller: LabAutoCapture, now: Double, localHead: FloatArray = identity, offCentre: Boolean = false): FaceFrame {
        val raw = autoFrame(controller, now)
        val packet = raw.packet().copyOf()
        for (i in 0 until 478) {
            packet[FaceFrame.VERTEX_OFFSET+i*3] = if (offCentre) .5f else 0f
            packet[FaceFrame.VERTEX_OFFSET+i*3+1] = 0f
            packet[FaceFrame.VERTEX_OFFSET+i*3+2] = -1f
        }
        for ((n,id) in LabAutoCapture.markerIds.withIndex()) packet[FaceFrame.VERTEX_OFFSET+id*3] += (n-3)*.015f
        val head = StageRegistration.multiply(baselineHead, localHead)
        return FaceFrame(packet, controller.configuration, now).inStage(head, LabRegistrationEvidence(head,identity,head))
    }
    auto.start("roll", originalConfig, false, 0.0, rollOnly = true)
    auto.tick(15.0); auto.tick(23.0); clock=23.0
    check(auto.ui.total==4 && auto.tag!!.rollOnly && auto.tag!!.protocol==LabProjectionReference.PROTOCOL)
    for (i in 1..4) { clock+=.5; check(auto.frame(autoFrame(auto,clock),true,true,clock)==null) }
    check(auto.ui.phase=="SETTLE" && auto.tag!!.rollBaseline.isEmpty())
    val rollRequests=mutableListOf<LabAutoTag>()
    var rejectedWrongMotion=false
    while (auto.ui.active && clock<500) {
        clock+=.5; auto.tick(clock)
        if (!auto.ui.active) break
        if (auto.ui.pose==1 && auto.ui.phase=="SETTLE" && !rejectedWrongMotion) {
            val fixedBaseline=auto.tag!!.rollBaseline
            for (i in 1..6) {
                clock+=.5
                val wrong=rollFrame(auto,clock,rotation(yaw=15.0))
                check(auto.frame(wrong,true,true,clock)==null)
                auto.sceneApplied(auto.tag,wrong.sequence,clock)
            }
            check(auto.ui.phase=="SETTLE" && auto.tag!!.rollBaseline==fixedBaseline)
            check(auto.frame(rollFrame(auto,clock+.1,rotation(roll=15.0),true),true,true,clock+.1)==null)
            rejectedWrongMotion=true
        }
        val target=LabRollCapture.targets[auto.ui.pose].toDouble()
        val f=rollFrame(auto,clock,rotation(roll=target))
        val request=auto.frame(f,true,true,clock)
        auto.sceneApplied(auto.tag,f.sequence,clock)
        if (request!=null) {
            check(LabRollCapture.evidence(request,f.registrationEvidence!!.headToStage)!!.getJSONObject("measured").getBoolean("orientationAccepted"))
            rollRequests.add(request); auto.saved(request,clock+.1)
        }
    }
    check(auto.ui.phase=="DONE" && rollRequests.size==12 && rejectedWrongMotion)
    check(rollRequests.map { it.pose }.distinct()==listOf(0,1,2,3))
    check(rollRequests.all { it.rollOnly && it.rollBaseline==rollRequests.first().rollBaseline && it.rollBaseline.size==16 })
    check(auto.configuration==null)
    auto.start("roll-cancel",originalConfig,false,0.0,rollOnly=true);auto.stop()
    check(auto.configuration==null && !auto.ui.active)
    println("PASS: 12-export roll flow; measured nonidentity baseline; yaw/opposite-roll/missing-tracking/reflection/face-border rejection; immutable baseline and cancellation")
    // Export production geometry/atlas to the independent image and projection regression.
    // The actual production registration, frame pose and every vertex share one head-local shift.
    val poseCorrection = LabPoseCorrection(true, 2)
    val poseContext = Context(File(root, "comparison-private"), File(root, "comparison-external"))
    val poseLab = FaceRegistrationLab(poseContext)
    poseLab.resetToC()
    val unchangedConfig = poseLab.configuration()
    check(!poseLab.poseCorrection().enabled)
    poseLab.togglePoseCorrection()
    check(poseLab.poseCorrection() == poseCorrection && poseLab.configuration() == unchangedConfig)
    poseLab.markFrame(unchangedConfig, 90, true, "Ready", correction = LabPoseCorrection())
    check(!poseLab.ui.value.ready)
    poseLab.markFrame(unchangedConfig, 91, true, "Ready", correction = poseCorrection)
    check(poseLab.ui.value.ready)
    poseLab.queueSave(); poseLab.togglePoseCorrection()
    check(poseLab.poseCorrection() == poseCorrection)
    countdown(poseLab)
    val pinnedRequest = poseLab.takeSave(unchangedConfig, true, "Ready")!!
    check(pinnedRequest.poseCorrection == poseCorrection)
    poseLab.fail("fixture save released")
    poseLab.startAutomatic(single=true,geometry=true)
    poseLab.togglePoseCorrection(); check(poseLab.poseCorrection() == poseCorrection)
    poseLab.cancelAutomatic(); check(poseLab.poseCorrection() == poseCorrection)
    poseLab.togglePoseCorrection(); check(!poseLab.poseCorrection().enabled && poseLab.configuration().custom == unchangedConfig.custom)
    poseLab.close()
    val reopened = FaceRegistrationLab(poseContext)
    check(reopened.poseCorrection().stereo && reopened.configuration().mode == 5)
    val stereoSettings = reopened.frameSettings()
    reopened.togglePoseCorrection()
    check(reopened.frameSettings() == stereoSettings) // Cannot stack DOWN40 on the paired mode.
    reopened.toggleStereoCalibration()
    check(reopened.configuration().mode == 4 && !reopened.poseCorrection().enabled)
    check(stereoSettings.first.mode == 5 && stereoSettings.second.stereo) // Immutable in-flight settings.
    reopened.toggleStereoCalibration()
    check(reopened.poseCorrection().stereo && reopened.configuration().mode == 5)
    reopened.startAutomatic(single=true, geometry=true)
    check(!reopened.stabilizeMesh())
    check(!reopened.poseCorrection().stereo)
    reopened.cancelAutomatic()
    check(reopened.stabilizeMesh())
    check(reopened.poseCorrection().stereo && reopened.configuration().mode == 5)
    reopened.adjust(IntrinsicParameter.FX, 1700f)
    check(reopened.configuration().mode == 4 && !reopened.poseCorrection().enabled)
    reopened.cycleMode()
    check(reopened.configuration().mode == 5 && reopened.poseCorrection().stereo)
    reopened.close()
    val recordedSamples = org.json.JSONArray(File(args[0], "pose-comparison-input.json").readText())
    val stereoProfile = JSONObject(File(args[0], "stereo-profile.json").readText())
    fun profileMatrix(key: String): FloatArray {
        val rows = stereoProfile.getJSONArray(key)
        return (0 until rows.length()).flatMap { r -> val row=rows.getJSONArray(r); (0 until row.length()).map { row.getDouble(it).toFloat() } }.toFloatArray()
    }
    check(LabStereoCalibration.headCorrection.contentEquals(profileMatrix("DHead")))
    check(LabStereoCalibration.sourceIntrinsics.contentEquals(profileMatrix("sourceIntrinsicsNativePixels")))
    check(LabStereoCalibration.workingIntrinsics.matches(profileMatrix("currentAffineWorkingIntrinsics")))
    rejected { LabCameraProfile.configuration(5, "unmatched-ROM") }
    val stereoCorrection = LabPoseCorrection(true, stereo=true)
    val producedSamples = org.json.JSONArray()
    for (i in 0 until recordedSamples.length()) {
        val sample = recordedSamples.getJSONObject(i)
        fun values(key: String): FloatArray = sample.getJSONArray(key).let { a -> FloatArray(a.length()) { a.getDouble(it).toFloat() } }
        val head = values("headToStageAtCapture")
        val optical = values("cameraToHead")
        val cameraService = values("cameraToTracking")
        val raw = FaceFrame(values("result"))
        val originalMatrix = StageRegistration.serviceToStage(head,optical,cameraService)
        val correctedMatrix = poseCorrection.serviceToStage(head,optical,cameraService)
        val current = raw.inStage(originalMatrix)
        val stereoMatrix = stereoCorrection.serviceToStage(head,optical,cameraService)
        val stereoFrame = raw.inStage(stereoMatrix, LabRegistrationEvidence(head,optical,stereoMatrix,poseCorrection=stereoCorrection,rawTransform=originalMatrix),stereoCorrection)
        val stageDelta = StageRegistration.multiply(StageRegistration.multiply(head,profileMatrix("DHead")),StageRegistration.inverseRigid(head))
        val independentVertices = StageRegistration.transformVertices(stageDelta,current.vertices)
        check(stereoFrame.vertices.zip(independentVertices.toList()).all { (a,b) -> abs(a-b)<2e-6 })
        val independentPose = StageRegistration.multiply(stageDelta,current.pose)
        check(stereoFrame.pose.zip(independentPose.toList()).all { (a,b) -> abs(a-b)<2e-6 })
        check(stereoFrame.withRawStageVertices().vertices.zip(current.vertices.toList()).all { (a,b) -> abs(a-b)<2e-6 })
        check(stereoFrame.withRawStageVertices().pose.zip(current.pose.toList()).all { (a,b) -> abs(a-b)<2e-6 })
        val corrected = raw.inStage(correctedMatrix, LabRegistrationEvidence(head,optical,correctedMatrix,poseCorrection=poseCorrection,rawTransform=originalMatrix),poseCorrection)
        check(raw.packet().contentEquals(values("result")))
        val expected = FloatArray(3) { -.040f*head[it*4+1] }
        for (v in 0 until 478) for (axis in 0..2) check(kotlin.math.abs(corrected.vertices[v*3+axis]-current.vertices[v*3+axis]-expected[axis]) < 5e-7)
        for (row in 0..3) for (col in 0..3) {
            val index=row*4+col
            check(kotlin.math.abs(corrected.pose[index]-current.pose[index]-(if(row<3 && col==3) expected[row] else 0f)) < 5e-7)
        }
        check(corrected.poseCorrection == poseCorrection && corrected.withAutomatic(auto.tag).poseCorrection == poseCorrection)
        check(corrected.withRawStageVertices().vertices.zip(current.vertices.toList()).all { (a,b) -> kotlin.math.abs(a-b) < 5e-7 })
        val renderedEvidence = corrected.registrationEvidence!!.json(true)
        check(renderedEvidence.getJSONArray("rigToStage").toString() == org.json.JSONArray(head.toList()).toString())
        check(renderedEvidence.getJSONArray("markers").toString() == LabProjectionReference.json(head,true).getJSONArray("markers").toString())
        check(renderedEvidence.getJSONObject("poseCorrection").getBoolean("enabled"))
        sample.put("stageResult", org.json.JSONArray(corrected.packet().toList()))
            .put("serviceToStage", org.json.JSONArray(correctedMatrix.toList()))
            .put("rawServiceToStage", org.json.JSONArray(originalMatrix.toList()))
            .put("poseCorrection", poseCorrection.json())
            .put("registrationEvidence", corrected.registrationEvidence!!.json(true))
        producedSamples.put(sample)
    }
    File(args[0], "pose-comparison-production.json").writeText(producedSamples.toString(2))
    println("PASS: current/down40 selection, queued/automatic locks, unchanged intrinsics, reopen default; production raw headset pose/vertex shift and immutable correction evidence")
    println("PASS: exact frozen stereo K/D, paired startup/toggle/capture restoration, immutable frame settings, every vertex and pose under recorded roll, raw-reference inverse")

    val reference = LabProjectionReference.json(identity)
    val referenceMesh = LabProjectionReference.mesh(123456)
    reference.put("meshPositions", org.json.JSONArray(referenceMesh.positions.toList()))
    reference.put("meshUv", org.json.JSONArray(referenceMesh.uv.toList()))
    reference.put("meshTriangles", org.json.JSONArray(referenceMesh.triangles))
    reference.put("sequence", 123456)
    reference.put("checksum", LabProjectionReference.checksum(123456))
    reference.put("codeCells", org.json.JSONArray((0..8).flatMap { r -> (0..11).map { col -> LabProjectionReference.codeCell(r, col, 123456) } }))
    File(args[0], "projection-reference.json").writeText(reference.toString(2))
    val rollReference = LabProjectionReference.json(identity, true)
    val rollMesh = LabProjectionReference.mesh(123456, true)
    rollReference.put("meshPositions", org.json.JSONArray(rollMesh.positions.toList()))
    rollReference.put("meshUv", org.json.JSONArray(rollMesh.uv.toList()))
    rollReference.put("meshTriangles", org.json.JSONArray(rollMesh.triangles))
    rollReference.put("sequence", 123456)
    File(args[0], "roll-projection-reference.json").writeText(rollReference.toString(2))
    val atlas = LabProjectionReference.atlas()
    File(args[0], "projection-atlas.ppm").outputStream().use { out ->
        out.write("P6\\n512 512\\n255\\n".toByteArray())
        atlas.forEach { pixel -> out.write(byteArrayOf((pixel ushr 16).toByte(), (pixel ushr 8).toByte(), pixel.toByte())) }
    }
    val registration = LabRegistrationEvidence(identity, identity, identity)
    check(olderFrame.inStage(identity, registration).withAutomatic(geometryRequests[1]).registrationEvidence === registration)
    // Two fresh samples plus an intervening old one retain the hold, without saving the old one.
    auto.start("skip-old", originalConfig, true, 0.0); auto.tick(15.0); auto.tick(23.0)
    check(auto.frame(autoFrame(auto, 23.0), true, true, 23.0) == null)
    val duplicate = autoFrame(auto, 23.5)
    check(auto.frame(duplicate, true, true, 23.5) == null)
    check(auto.frame(duplicate, false, true, 24.0) == null)
    val old = autoFrame(auto, 23.8)
    check(auto.frame(old, true, true, 24.8) == null && auto.ui.phase == "SETTLE")
    check(auto.frame(autoFrame(auto, 25.0), true, true, 25.0) == null && auto.ui.phase == "CLEAN_BEFORE")
    auto.stop()
    // Head motion on an old frame still breaks the hold.
    auto.start("old-motion", originalConfig, true, 0.0); auto.tick(15.0); auto.tick(23.0)
    auto.frame(autoFrame(auto, 23.0), true, true, 23.0)
    auto.frame(autoFrame(auto, 23.5), true, true, 23.5)
    auto.frame(autoFrame(auto, 23.8), true, false, 24.8)
    auto.frame(autoFrame(auto, 25.0), true, true, 25.0)
    check(auto.ui.phase == "SETTLE")
    auto.stop()
    // Face flags turning true on the same exposure, regressions, and collapsed geometry cannot
    // reach the lab renderer or authorize an export. Normal sample decoding stays unchanged.
    auto.start("geometry", originalConfig, true, 0.0); auto.tick(15.0); auto.tick(23.0)
    val validFace = autoFrame(auto, 23.0)
    val gate = LabFaceFrameGate()
    val noFace = FaceFrame(validFace.packet().also { it[1] = 0f }, validFace.labConfiguration)
    check(gate.rejection(noFace, 23.0) == null)
    check(gate.rejection(validFace, 23.0) != null)
    val freshFace = autoFrame(auto, 23.5)
    check(gate.rejection(freshFace, 23.5) == null && gate.rejection(freshFace, 23.5) != null)
    check(gate.rejection(validFace, 23.5) != null)
    check(LabFaceFrameGate().rejection(autoFrame(auto, 24.0, false), 24.0) != null)
    val collapsed = autoFrame(auto, 24.5).packet().also { p ->
        for (id in listOf(133,362,263,291,152)) for (axis in 0..2) p[FaceFrame.VERTEX_OFFSET+id*3+axis] = 0f
    }
    val corruptFace = FaceFrame(collapsed, auto.configuration, 24.5)
    check(corruptFace.hasFace && LabFaceFrameGate().rejection(corruptFace, 24.5) != null)
    check(!LabAutoCapture.markerGeometryValid(corruptFace.vertices))
    check(!LabAutoCapture.markerGeometryValid(FloatArray(478*3)))
    check(!LabAutoCapture.markerGeometryValid(freshFace.vertices.also { it[0] = Float.NaN }))
    check(auto.frame(corruptFace, true, true, 24.5) == null && auto.ui.phase == "SETTLE")
    rejected { LabAutoCapture.markerVertices(corruptFace.vertices) }
    check(LabAutoCapture.markerGeometryValid(freshFace.inStage(identity.copyOf().also { it[3]=1f; it[7]=2f }).vertices))
    // A service wall-clock fallback (including a no-face packet) must not poison the clock guard.
    val fallback = FaceFrame(freshFace.packet().also { p ->
        p[1] = 0f; p[2947] = 1793384960f; p[2948] = .7078192f; p[2976] = 0f
    }, freshFace.labConfiguration, 23.5)
    val recoveringGate = LabFaceFrameGate()
    check(recoveringGate.rejection(validFace, 23.0) == null)
    check(recoveringGate.rejection(fallback, 23.5) != null)
    check(recoveringGate.rejection(freshFace, 23.5) == null)
    check(recoveringGate.rejection(freshFace, 23.5) != null) // duplicate still rejected
    check(LabFaceFrameGate().rejection(FaceFrame(fallback.packet().also { it[1]=1f }, fallback.labConfiguration), 23.5) != null)
    check(LabFaceFrameGate().rejection(FaceFrame(freshFace.packet().also { it[2947]=Float.NaN }, freshFace.labConfiguration), 23.5) != null)
    // Three usable exposures may drift 10 mm each (20 mm overall) without requiring immobility.
    auto.stop(); auto.start("natural-drift", originalConfig, true, 0.0); auto.tick(15.0); auto.tick(23.0)
    for (n in 0..2) {
        val now = 23.0+n*.5
        val frame = autoFrame(auto, now)
        val drift = frame.packet().also { p ->
            for (id in LabAutoCapture.markerIds) p[FaceFrame.VERTEX_OFFSET+id*3] += n*.010f
        }
        check(auto.frame(FaceFrame(drift, auto.configuration, now), true, true, now) == null)
    }
    check(auto.ui.phase == "CLEAN_BEFORE")
    // Slow natural rotation fails the former two-second hold but passes a brief exposure.
    fun headPose(t: Double): FloatArray {
        val a = Math.toRadians(t*.75); val co = kotlin.math.cos(a).toFloat(); val si = kotlin.math.sin(a).toFloat()
        return floatArrayOf(co,-si,0f,(t*.005).toFloat(),si,co,0f,0f,0f,0f,1f,0f,0f,0f,0f,1f)
    }
    val naturalHead = (0..500).map { it*.01 to headPose(it*.01) }
    check(!LabMotion.measure(naturalHead, 1.0, 3.05).stable)
    check(LabMotion.measure(naturalHead, 2.95, 3.05).stable)
    val suddenHead = naturalHead.map { (t,p) -> t to p.copyOf().also { if (t>=3.0) it[3]+=.02f } }
    check(!LabMotion.measure(suddenHead, 2.95, 3.05).stable)
    auto.stop()
    auto.start("stale", originalConfig, true, 0.0); auto.tick(15.0); auto.tick(23.0)
    val stale = autoFrame(auto, 24.0)
    check(auto.frame(stale, true, true, 26.0) == null && auto.ui.phase == "SETTLE")
    for (t in 27..32) check(auto.frame(autoFrame(auto, t.toDouble()), true, false, t.toDouble()) == null)
    check(auto.ui.phase == "SETTLE")
    auto.stop()
    auto.start("timeout", originalConfig, true, 0.0); auto.tick(15.0); auto.tick(23.0)
    auto.tick(84.0); check(auto.ui.phase == "FAILED" && !auto.ui.active)
    auto.start("cancel", originalConfig, false, 0.0)
    check(auto.ui.total == 28); auto.stop(); check(auto.configuration == null && !auto.ui.active)
    val markerPoints = FloatArray(478*3) { it*.0001f }
    val markerMesh = LabAutoCapture.markerVertices(markerPoints)
    check(markerMesh.size == 144 && LabAutoCapture.markerTriangles.size == 192)
    for ((i,id) in LabAutoCapture.markerIds.withIndex()) for (axis in 0..2) {
        val center = (0..5).map { markerMesh[i*18+it*3+axis] }.average()
        check(kotlin.math.abs(center-markerPoints[id*3+axis]) < 1e-7)
    }
    val tagged = olderFrame.withAutomatic(requests[1]).inStage(identity)
    check(tagged.automatic == requests[1])
    println("PASS: 84-export intrinsics flow; 30-export binocular geometry flow; 3-export geometry check; constant C; production reference mesh/atlas; clock-fallback recovery, motion/freshness, scene acknowledgement, cancellation, marker centres and immutable tag/registration propagation")
    println("PASS: timeline badge/journal clock agreement; immutable frame revision through Stage conversion; visibility; close drains journal")
    println("PASS: profile roundtrip/rejection/archive/autoload; independent controls; queued revision/timeout/single save; stopped-camera value save; graph clock preservation; shipped freshness/K packet decoding")
}
''')
    cache = Path.home() / '.gradle/caches/modules-2/files-2.1'
    def jar(group, artifact, version):
        return next((cache / group / artifact / version).glob('*/*.jar'))
    stdlib = jar('org.jetbrains.kotlin', 'kotlin-stdlib', '2.0.21')
    compiler = [jar('org.jetbrains.kotlin', name, '2.0.21') for name in
        ('kotlin-compiler-embeddable', 'kotlin-script-runtime', 'kotlin-reflect', 'kotlin-daemon-embeddable')]
    coroutines = jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.6.4')
    compiler += [stdlib, jar('org.jetbrains', 'annotations', '13.0'),
                 jar('org.jetbrains.intellij.deps', 'trove4j', '1.0.20200330'), coroutines]
    android = Path.home() / 'Library/Android/sdk/platforms/android-35/android.jar'
    java = Path(os.environ.get('JAVA_HOME', '/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home')) / 'bin/java'
    classes = output / 'classes'
    cp = os.pathsep.join(map(str, [stdlib, coroutines, json_jar.resolve(), android]))
    subprocess.run([str(java), '-cp', os.pathsep.join(map(str, compiler)),
        'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-nowarn', '-no-stdlib', '-no-reflect',
        '-classpath', cp, '-d', str(classes), *map(str, output.glob('*.kt')),
        *[str(source / name) for name in ('LabIntrinsics.kt','LabCalibrationStore.kt','LabCameraProfile.kt','LabStereoCalibration.kt','CompactFaceDetector.kt',
                                        'LabGeometryProbe.kt','FaceOutputs.kt','FaceTrackingPacing.kt','StageRegistration.kt','FacePoseMeshStabilizer.kt','LabTimeline.kt','LabAutoCapture.kt','LabMotion.kt','LabProjectionReference.kt','LabRollCapture.kt','LabPoseCorrection.kt','LabBoardCapture.kt')]], check=True)
    subprocess.run([str(java), '-cp', str(classes)+os.pathsep+cp,
        'com.pico.spatial.ml.sample.facelandmarker.IntrinsicsFixtureKt', str(output)], check=True)
    (output / 'intrinsics-validation.json').write_text(json.dumps(dict(status='PASS',
        boundary='Production Kotlin methods and shipped JS with host Android adapters. No native runtime or physical alignment acceptance.',
        automatic_capture='PASS', profiles='PASS', frame_pinning='PASS', clock_reset='PASS', stopped_camera_save='PASS', packet_freshness_and_k='PASS'), indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    args = parser.parse_args()
    validate(args.output, args.json_jar)
