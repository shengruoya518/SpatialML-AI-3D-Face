// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.content.Context
import android.os.SystemClock
import android.util.Log
import com.pico.spatial.ml.securemr.SpatialMLInstance
import java.util.Locale
import kotlin.math.hypot
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield

internal class FaceLandmarkerRunner(
    context: Context,
    private val backend: Int,
    private val poses: StagePoseHistory,
    private val lab: FaceRegistrationLab? = null,
    private val helmetMode: Boolean = false,
) : AutoCloseable {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val mutableFrame = MutableStateFlow<FaceFrame?>(null)
    val frame = mutableFrame.asStateFlow()
    private val mutableStatus = MutableStateFlow("Initializing SpatialML…")
    val status = mutableStatus.asStateFlow()
    private val mutableOutputs =
        (lab?.requestedOutputs ?: MutableStateFlow(FaceOutputs.ALL)).also {
            if (helmetMode) it.value = FaceOutputs.HELMET
        }
    val outputs = mutableOutputs.asStateFlow()

    fun setOutputs(next: FaceOutputs) {
        require(
            !helmetMode ||
                next == FaceOutputs.HELMET ||
                next == FaceOutputs.ALL ||
                next == FaceOutputs.NONE
        )
        if (lab?.ui?.value?.locked == true || lab?.automaticUi?.value?.active == true) return
        mutableOutputs.value = next
        mutableFrame.value = null
    }

    private fun needsCalibrationEvidence(): Boolean =
        !helmetMode &&
            (lab?.ui?.value?.locked == true ||
                lab?.ui?.value?.showCaptureTools == true ||
                lab?.automaticUi?.value?.active == true)

    private fun effectiveOutputs(): FaceOutputs =
        if (helmetMode) {
            mutableOutputs.value
        } else if (needsCalibrationEvidence()) FaceOutputs.ALL else mutableOutputs.value

    @Volatile var sizeScale = 1f
    @Volatile var paused = false
    @Volatile var tongueRequested = false
    @Volatile private var reacquireRequested = false

    /**
     * The wearer's manual trim in capture-head metres (+X right, +Y up), applied before
     * head-to-Stage like [LabPoseCorrection] so it holds for any face at any head pose.
     */
    @Volatile var headShift: Pair<Float, Float> = 0f to 0f

    /** Drops the tracked face; the next frame runs the detector on whoever is in view. */
    fun reacquire() {
        reacquireRequested = true
    }

    private var started = false
    private var instance: SpatialMLInstance? = null

    fun start() {
        if (started) return
        started = true
        scope.launch {
            var graph: FaceLandmarkerGraph? = null
            try {
                awaitStageTracking()
                // Resolve optical metadata before connecting SpatialML. A cold PXRCapture query
                // can preempt an earlier client and trigger delayed native camera teardown.
                val calibration = CameraCalibration.readLeftCameraToHead(appContext)
                val leftCameraToHead = calibration.matrix
                Log.i(
                    TAG,
                    "camera_to_head_calibration matrix=${leftCameraToHead.contentToString()}",
                )
                mutableStatus.value = "Waiting for camera startup…"
                delay(if (calibration.queried) 8_000 else 1_500)
                // Keep the instance/connection alive until all native session handles are released.
                val connection = SpatialMLInstance.create(appContext)
                instance = connection
                withTimeout(15_000) { while (!connection.ready) delay(50) }
                graph = FaceLandmarkerGraph.create(appContext, backend, lab != null)
                check(connection.ready)
                Log.i(
                    TAG,
                    "pipeline_ready stage=full_space passthrough=mixed container=0x0x0 backend=$backend gpu_preprocessing=${BuildConfig.FACE_GPU_PREPROCESSING} rgb_first=${BuildConfig.FACE_GPU_SAMPLE_BYTES} preprocessing_backend=${SpatialMLGraphSession.PREPROCESSING_BACKEND} camera=${SpatialMLGraphSession.WIDTH}x${SpatialMLGraphSession.HEIGHT}",
                )
                val origin = SystemClock.elapsedRealtime()
                var sequence = 0
                var acquire = true
                var lastTime = origin
                var registrationLogged = false
                var lastCapture = Double.NEGATIVE_INFINITY
                var lastFreshAt = SystemClock.elapsedRealtime()
                var lastReadiness = ""
                val labFrameGate = LabFaceFrameGate()
                val stabilizer = FacePoseMeshStabilizer()
                var previousCalibration: LabCameraConfiguration? = null
                while (currentCoroutineContext().isActive) {
                    val activeGraph = checkNotNull(graph)
                    val evidenceRequested = needsCalibrationEvidence()
                    val pacing =
                        if (evidenceRequested) FaceTrackingPacing.LEGACY
                        else lab?.trackingPacing ?: FaceTrackingPacing.FAST
                    val selectedOutputs = effectiveOutputs()
                    if (paused || !selectedOutputs.any) {
                        mutableFrame.value = null
                        mutableStatus.value =
                            if (paused) "Paused" else "Select a face output to start tracking"
                        acquire = true
                        stabilizer.reset()
                        lastFreshAt = SystemClock.elapsedRealtime()
                        delay(50)
                        continue
                    }
                    if (reacquireRequested) {
                        reacquireRequested = false
                        mutableFrame.value = null
                        acquire = true
                        stabilizer.reset()
                    }
                    val frameSettings = lab?.frameSettings()
                    val frameCalibration = frameSettings?.first
                    val poseCorrection = frameSettings?.second ?: LabPoseCorrection()
                    frameCalibration?.let(activeGraph::setCalibration)
                    sequence += 1
                    val startedAt = SystemClock.elapsedRealtime()
                    val submitSeconds = System.nanoTime() * 1e-9
                    // Normal video follows MediaPipe's landmark ROI. Evidence captures retain
                    // detector-per-frame behavior and a changed calibration forces acquisition.
                    val acquireFrame =
                        acquire || evidenceRequested || frameCalibration != previousCalibration
                    val selectedTongue =
                        helmetMode &&
                            tongueRequested &&
                            selectedOutputs.blendshapes &&
                            !evidenceRequested
                    previousCalibration = frameCalibration
                    activeGraph.submit(
                        sequence,
                        (startedAt - origin) / 1000f,
                        if (lab != null) 1f else sizeScale.coerceIn(.5f, 1.5f),
                        acquireFrame,
                        selectedOutputs,
                        evidenceRequested,
                        selectedTongue,
                    )
                    // One frame in flight. A stale snapshot never authorizes the next capture.
                    val values =
                        withTimeout(15_000) {
                            readCompletedFaceResult(
                                sequence,
                                { activeGraph.resultComplete(sequence) },
                                pollMillis = pacing.pollMillis,
                                read = activeGraph::readResult,
                            )
                        }
                    val tongueConfidence = activeGraph.readTongue(sequence)
                    val readbackSeconds = System.nanoTime() * 1e-9
                    val headAtReadback = poses.atCapture(readbackSeconds)
                    val evidence = activeGraph.calibrationEvidence
                    val raw =
                        FaceFrame(
                            if (evidence) values
                            else FaceOutputPacket.decode(values, selectedOutputs),
                            frameCalibration,
                            readbackSeconds,
                            outputs = selectedOutputs,
                        )
                    val decodedSeconds = System.nanoTime() * 1e-9
                    val frameRejection =
                        if (lab != null && selectedOutputs.mesh)
                            labFrameGate.rejection(raw, readbackSeconds)
                        else null
                    val captureAge = System.nanoTime() * 1e-9 - raw.captureSeconds
                    val advancingCapture =
                        raw.captureSeconds > lastCapture && captureAge in -.1..2.0
                    if (advancingCapture) {
                        if (lastCapture == Double.NEGATIVE_INFINITY)
                            Log.i(
                                TAG,
                                "camera_stream_ready seq=$sequence capture=${raw.captureSeconds} age=$captureAge",
                            )
                        lastCapture = raw.captureSeconds
                        lastFreshAt = SystemClock.elapsedRealtime()
                    }
                    check(SystemClock.elapsedRealtime() - lastFreshAt < 3_000) {
                        "Camera stream stopped supplying fresh frames. Retry camera capture."
                    }
                    val exposureMotion =
                        if (evidence)
                            LabMotion.measure(
                                poses.snapshot(raw.captureSeconds - .2, readbackSeconds),
                                raw.captureSeconds - .05,
                                raw.captureSeconds + .05,
                            )
                        else LabMotion(false, 0.0, 0.0)
                    val headToStage = poses.atCapture(raw.captureSeconds)
                    val registered =
                        if (!selectedOutputs.spatial) raw.withPoseCorrection(poseCorrection)
                        else if (headToStage != null) {
                            val (right, up) = headShift
                            val transform =
                                poseCorrection.serviceToStage(
                                    headToStage,
                                    leftCameraToHead.copyOf().also {
                                        it[3] += right
                                        it[7] += up
                                    },
                                    raw.captureCameraPose,
                                )
                            if (raw.hasFace && !registrationLogged) {
                                Log.i(
                                    TAG,
                                    "stage_registration seq=$sequence capture=${raw.captureSeconds} head=${headToStage.contentToString()} service_camera=${raw.captureCameraPose.contentToString()} service_to_stage=${transform.contentToString()}",
                                )
                                registrationLogged = true
                            }
                            raw.inStage(
                                transform,
                                if (lab?.geometryCaptureActive == true)
                                    LabRegistrationEvidence(
                                        headToStage,
                                        leftCameraToHead,
                                        transform,
                                        exposureMotion,
                                        poseCorrection,
                                        StageRegistration.serviceToStage(
                                            headToStage,
                                            leftCameraToHead,
                                            raw.captureCameraPose,
                                        ),
                                    )
                                else null,
                                poseCorrection,
                            )
                        } else null
                    val next = registered ?: raw
                    val registeredSeconds = System.nanoTime() * 1e-9
                    lab?.pipelineFrame(
                        raw,
                        submitSeconds,
                        readbackSeconds,
                        acquireFrame,
                        frameRejection,
                        exposureMotion,
                        values.size * 4,
                        if (evidence) values[1] else values[4],
                        values.all(Float::isFinite),
                        evidence,
                        decodedSeconds,
                        registeredSeconds,
                        poseCorrection,
                        pacing,
                    )
                    val autoSave =
                        lab?.takeIf { evidence }
                            ?.automaticFrame(
                                registered,
                                advancingCapture && raw.freshCameraFrame && frameRejection == null,
                                exposureMotion.stable,
                                readbackSeconds,
                            )
                    val presented =
                        registered
                            ?.takeIf { frameRejection == null }
                            ?.withAutomatic(
                                if (evidence) lab?.automaticTag(frameCalibration) else null
                            )
                    val eligiblePresentation =
                        presented?.takeIf {
                            selectedOutputs == effectiveOutputs() &&
                                (lab == null || frameSettings == lab.frameSettings())
                        }
                    val filterStartedSeconds = System.nanoTime() * 1e-9
                    val displayFrame =
                        if (
                            eligiblePresentation?.hasFace == true &&
                                selectedOutputs.spatial &&
                                eligiblePresentation.freshCameraFrame &&
                                (lab?.stabilizeMesh() ?: helmetMode) &&
                                eligiblePresentation.automatic == null &&
                                !evidence
                        ) {
                            val filtered =
                                stabilizer.update(
                                    eligiblePresentation.vertices,
                                    eligiblePresentation.geometryPose,
                                    eligiblePresentation.captureSeconds,
                                    eligiblePresentation.trackingIdentity,
                                    Triple(
                                        frameCalibration,
                                        poseCorrection,
                                        if (helmetMode) FaceOutputs.HELMET else selectedOutputs,
                                    ),
                                )
                            eligiblePresentation.withPresentationGeometry(filtered)
                        } else {
                            // Streaming effects retain the filter through brief rejected/missing
                            // frames. Its own capture-gap/identity/configuration guards still reset
                            // on reacquisition. Raw calibration paths preserve their reset
                            // behavior.
                            if (!helmetMode || evidence || !(lab?.stabilizeMesh() ?: helmetMode))
                                stabilizer.reset()
                            eligiblePresentation
                        }
                    val filterCompletedSeconds = System.nanoTime() * 1e-9
                    displayFrame?.recordTongue(tongueConfidence)
                    displayFrame?.recordPublication(
                        registeredSeconds,
                        filterStartedSeconds,
                        filterCompletedSeconds,
                        pacing,
                    )
                    mutableFrame.value = displayFrame
                    acquire = raw.needsDetection
                    lab?.let { diagnostics ->
                        val calibration = checkNotNull(frameCalibration)
                        val reason =
                            when {
                                !evidence -> "Ready for One check or Full trial"
                                frameRejection != null -> frameRejection
                                !advancingCapture -> "Waiting for an advancing camera timestamp…"
                                !raw.freshCameraFrame -> "Waiting for a fresh camera exposure…"
                                registered == null -> "Waiting for the capture-time head pose…"
                                calibration.mode == LabCameraProfile.CUSTOM_MODE &&
                                    !calibration.custom.matches(raw.effectiveIntrinsics) ->
                                    "Waiting for matching camera values…"
                                calibration.mode == LabCameraProfile.STEREO_MODE &&
                                    !LabStereoCalibration.workingIntrinsics.matches(
                                        raw.effectiveIntrinsics
                                    ) -> "Waiting for stereo camera values…"
                                !raw.hasFace &&
                                    diagnostics.automaticTag(calibration)?.board != true &&
                                    diagnostics.ui.value.step !=
                                        FaceRegistrationLab.STEPS.lastIndex ->
                                    "Waiting for a measured face…"
                                else -> "Ready"
                            }
                        val usable = evidence && reason == "Ready"
                        diagnostics.markFrame(
                            calibration,
                            sequence,
                            usable,
                            reason,
                            raw.effectiveIntrinsics,
                            raw.hasFace,
                            poseCorrection,
                        )
                        val state = diagnostics.ui.value
                        val readiness =
                            "$reason mode=${calibration.mode} revision=${calibration.revision} pending=${state.pending}"
                        if (readiness != lastReadiness) {
                            Log.i(
                                TAG,
                                "registration_lab_readiness seq=$sequence $readiness capture_advancing=$advancingCapture capture_fresh=${raw.freshCameraFrame} measured=${raw.hasFace} registered=${registered != null} step=${state.step} ready_frames=${state.readyFrames}",
                            )
                            lastReadiness = readiness
                        }
                        // Consume a queued request only after this frame is known to be usable.
                        // Preview readbacks must not delay the next candidate while a save waits.
                        val saveRequest =
                            autoSave ?: diagnostics.takeSave(calibration, usable, reason)
                        if (
                            saveRequest != null ||
                                (evidence &&
                                    !diagnostics.ui.value.locked &&
                                    diagnostics.previewDue())
                        ) {
                            if (saveRequest != null) {
                                val settleMillis =
                                    ((raw.captureSeconds + .1 - System.nanoTime() * 1e-9) * 1000)
                                        .toLong()
                                if (settleMillis > 0) delay(settleMillis)
                                diagnostics.imageCaptured()
                            }
                            activeGraph.submitCapture()
                            withTimeout(15_000) {
                                while (!activeGraph.captureReady(sequence)) delay(5)
                            }
                            // One frame remains in flight until every diagnostic read has settled.
                            try {
                                val capture = activeGraph.readCapture(sequence)
                                val after = System.nanoTime() * 1e-9
                                if (saveRequest != null) {
                                    diagnostics.save(
                                        saveRequest,
                                        capture,
                                        raw,
                                        presented,
                                        headToStage,
                                        leftCameraToHead,
                                        headAtReadback,
                                        poses.atCapture(after),
                                        poses.snapshot(raw.captureSeconds - .6, after),
                                        readbackSeconds,
                                        after,
                                        submitSeconds,
                                    )
                                }
                                if (diagnostics.ui.value.showCaptureTools)
                                    diagnostics.publishPreview(capture, raw)
                            } catch (cancel: CancellationException) {
                                throw cancel
                            } catch (error: Exception) {
                                diagnostics.fail(error.message ?: "Export failed")
                                Log.w(TAG, "registration_lab_capture_rejected seq=$sequence", error)
                            }
                        }
                    }
                    val now = SystemClock.elapsedRealtime()
                    mutableStatus.value =
                        if (frameRejection != null) frameRejection
                        else if (raw.hasFace && registered == null)
                            "Waiting for the matching head pose…"
                        else if (next.hasFace)
                            String.format(
                                Locale.US,
                                "Tracking · detection %.0f%% · presence %.0f%% · %.1f Hz",
                                next.detection * 100,
                                next.presence * 100,
                                1000f / (now - lastTime).coerceAtLeast(1),
                            )
                        else "Looking for a face…"
                    if (sequence == 1 || sequence % 100 == 0)
                        Log.i(
                            TAG,
                            "face_frame seq=$sequence visible=${presented?.hasFace == true} detected=${raw.hasFace} registered=${registered != null} acquire=$acquire presence=${next.presence} capture=${raw.captureSeconds} capture_fresh=${raw.freshCameraFrame} capture_age_s=$captureAge capture_age_at_submit_s=${submitSeconds - raw.captureSeconds} outputs=${selectedOutputs.mask} readback_bytes=${values.size * 4} calibration_evidence=$evidence frame_readback_s=${readbackSeconds - submitSeconds} reprojection_px=${raw.maxReprojectionErrorPixels()} elapsed_ms=${now - startedAt}",
                        )
                    lastTime = now
                    // The service already limits progress to one completed frame at a time.
                    // Yield for cancellation/fairness without adding a fixed streaming delay.
                    if (pacing.idleMillis > 0) delay(pacing.idleMillis) else yield()
                }
            } catch (cancellation: CancellationException) {
                currentCoroutineContext().ensureActive()
                // withTimeout cancels its child scope, while external disposal cancels this scope.
                mutableStatus.value =
                    "SpatialML error: timed out waiting for the service or a complete face frame"
                lab?.fail(mutableStatus.value, fatal = true)
                Log.e(TAG, mutableStatus.value, cancellation)
            } catch (error: Exception) {
                mutableFrame.value = null
                mutableStatus.value =
                    "SpatialML error: ${error.message ?: error.javaClass.simpleName}"
                lab?.fail(mutableStatus.value, fatal = true)
                Log.e(TAG, mutableStatus.value, error)
            } finally {
                withContext(NonCancellable + Dispatchers.Default) { graph?.close() }
                instance = null
                mutableFrame.value = null
            }
        }
    }

    override fun close() {
        scope.cancel()
    }

    private suspend fun awaitStageTracking() {
        mutableStatus.value = "Waiting for Full Space head tracking…"
        while (!poses.ready) delay(50)
        Log.i(TAG, "stage_tracking_ready")
    }

    companion object {
        const val TAG = "FaceLandmarker"
    }
}

/** Wait for terminal publication in every mode before reading a possibly published prefix. */
internal suspend fun readCompletedFaceResult(
    sequence: Int,
    complete: () -> Boolean,
    pollMillis: Long = 2,
    read: () -> FloatArray,
): FloatArray {
    require(pollMillis in 1..10)
    while (!complete()) delay(pollMillis)
    var snapshot = read()
    while (snapshot[0] != sequence.toFloat()) {
        delay(pollMillis)
        snapshot = read()
    }
    return snapshot
}

/**
 * One atomic capture. The raw service packet is rebased before it is exposed to Stage rendering.
 */
internal class FaceFrame(
    private val values: FloatArray,
    val labConfiguration: LabCameraConfiguration? = null,
    val readbackSeconds: Double? = null,
    val automatic: LabAutoTag? = null,
    val outputs: FaceOutputs = FaceOutputs.ALL,
    val registrationEvidence: LabRegistrationEvidence? = null,
    val poseCorrection: LabPoseCorrection = LabPoseCorrection(),
    val presentationStabilization: org.json.JSONObject? = null,
) {
    init {
        require(values.size == RESULT_SIZE && values[0].isFinite())
    }

    // Written once before StateFlow publication; consumers never mutate the timing object.
    var presentationTiming: org.json.JSONObject? = null
        private set

    var tongueConfidence: Float? = null
        private set

    fun recordTongue(confidence: Float?) {
        require(confidence == null || (confidence.isFinite() && confidence in 0f..1f))
        tongueConfidence = confidence
    }

    fun recordPublication(
        registered: Double,
        filterStarted: Double,
        filterCompleted: Double,
        pacing: FaceTrackingPacing,
    ) {
        check(presentationTiming == null)
        presentationTiming =
            org.json
                .JSONObject()
                .put("registeredSeconds", registered)
                .put("filterStartedSeconds", filterStarted)
                .put("filterCompletedSeconds", filterCompleted)
                .put("publishedSeconds", System.nanoTime() * 1e-9)
                .put("trackingPacing", pacing.name.lowercase())
                .put("poseBeforeOcclusion", pacing != FaceTrackingPacing.LEGACY)
    }

    fun packet(): FloatArray = values.copyOf()

    fun withAutomatic(tag: LabAutoTag?) =
        FaceFrame(
            values,
            labConfiguration,
            readbackSeconds,
            tag,
            outputs,
            registrationEvidence,
            poseCorrection,
            presentationStabilization,
        )

    fun withPoseCorrection(correction: LabPoseCorrection) =
        FaceFrame(
            values,
            labConfiguration,
            readbackSeconds,
            automatic,
            outputs,
            registrationEvidence,
            correction,
            presentationStabilization,
        )

    fun withRawStageVertices(): FaceFrame {
        val head = registrationEvidence?.headToStage ?: return this
        val raw = values.copyOf()
        poseCorrection.rawStageVertices(head, vertices).copyInto(raw, VERTEX_OFFSET)
        if (outputs.spatial && poseCorrection.enabled)
            StageRegistration.multiply(poseCorrection.rawStageTransform(head), geometryPose)
                .copyInto(raw, POSE_OFFSET)
        return FaceFrame(
            raw,
            labConfiguration,
            readbackSeconds,
            automatic,
            outputs,
            registrationEvidence,
            LabPoseCorrection(),
        )
    }

    val sequence = values[0].toInt()
    val hasFace = values[1] > 0 && values.all(Float::isFinite)
    val detection = values[2]
    val presence = values[3]
    val trackingState = values[TRACKING_OFFSET + 4]
    val trackingFailureReason = values[TRACKING_OFFSET + 6]
    val trackingIdentity = values[TRACKING_OFFSET + 7]
    val poseStatus = values[TRACKING_OFFSET + 26]
    val needsDetection = !hasFace || values[TRACKING_OFFSET + 25] > 0
    val freshCameraFrame = values[TRACKING_OFFSET + 30] > 0
    val effectiveIntrinsics: FloatArray
        get() =
            floatArrayOf(
                values[TRACKING_OFFSET + 12],
                0f,
                values[TRACKING_OFFSET + 14],
                0f,
                values[TRACKING_OFFSET + 13],
                values[TRACKING_OFFSET + 15],
                0f,
                0f,
                1f,
            )

    val vertices: FloatArray
        get() =
            if (outputs.mesh) values.copyOfRange(VERTEX_OFFSET, BLENDSHAPE_OFFSET)
            else FloatArray(0)

    val landmarks: FloatArray
        get() = if (outputs.mesh) values.copyOfRange(4, VERTEX_OFFSET) else FloatArray(0)

    val blendshapes: FloatArray
        get() =
            if (outputs.blendshapes) values.copyOfRange(BLENDSHAPE_OFFSET, POSE_OFFSET)
            else FloatArray(0)

    val pose: FloatArray
        get() =
            if (outputs.pose) values.copyOfRange(POSE_OFFSET, POSE_OFFSET + 16) else FloatArray(0)

    // The internal spatial pose is needed to stabilize a mesh even with the pose UI disabled.
    val geometryPose: FloatArray
        get() =
            if (outputs.spatial) values.copyOfRange(POSE_OFFSET, POSE_OFFSET + 16)
            else FloatArray(0)

    fun withPresentationGeometry(filtered: FacePoseMeshStabilizer.Result): FaceFrame {
        val result = values.copyOf()
        if (outputs.mesh) filtered.vertices.copyInto(result, VERTEX_OFFSET)
        if (outputs.spatial) filtered.pose.copyInto(result, POSE_OFFSET)
        val metadata =
            org.json
                .JSONObject()
                .put("enabled", true)
                .put("algorithm", "pose-and-local-shape-v2")
                .put("responseProfile", FacePoseMeshStabilizer.RESPONSE_PROFILE)
                .put("space", "Stage pose; shape in face-local metres")
                .put("poseAlpha", filtered.poseAlpha)
                .put("shapeAlpha", filtered.shapeAlpha)
                .put("correctionRmsMetres", filtered.correctionRmsMetres)
                .put("reason", filtered.reason)
                .put("rawPose", org.json.JSONArray(geometryPose.toList()))
                .put("displayPose", org.json.JSONArray(filtered.pose.toList()))
        return FaceFrame(
            result,
            labConfiguration,
            readbackSeconds,
            automatic,
            outputs,
            registrationEvidence,
            poseCorrection,
            metadata,
        )
    }

    val captureCameraPose: FloatArray
        get() = values.copyOfRange(2978, RESULT_SIZE)

    val captureSeconds: Double
        get() = values[TRACKING_OFFSET + 1].toDouble() + values[TRACKING_OFFSET + 2].toDouble()

    /**
     * Check the final service mesh against the measured landmarks in the same left-camera frame.
     */
    fun maxReprojectionErrorPixels(): Double? {
        if (!hasFace || !outputs.mesh) return null
        val identity = floatArrayOf(1f, 0f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 0f, 1f)
        val cameraPoints =
            StageRegistration.transformVertices(
                StageRegistration.serviceToStage(identity, identity, captureCameraPose),
                vertices,
            )
        val fx = values[TRACKING_OFFSET + 12].toDouble()
        val fy = values[TRACKING_OFFSET + 13].toDouble()
        val cx = values[TRACKING_OFFSET + 14].toDouble()
        val cy = values[TRACKING_OFFSET + 15].toDouble()
        if (fx <= 0 || fy <= 0) return null
        return (0 until 478).maxOf { index ->
            val j = index * 3
            val depth = -cameraPoints[j + 2].toDouble()
            if (depth <= 0) Double.POSITIVE_INFINITY
            else {
                val x = cx + fx * cameraPoints[j] / depth
                val y = cy - fy * cameraPoints[j + 1] / depth
                hypot(
                    x - values[4 + j] * SpatialMLGraphSession.WIDTH,
                    y - values[5 + j] * SpatialMLGraphSession.HEIGHT,
                )
            }
        }
    }

    fun inStage(
        serviceToStage: FloatArray,
        evidence: LabRegistrationEvidence? = registrationEvidence,
        correction: LabPoseCorrection = poseCorrection,
    ): FaceFrame {
        val result = values.copyOf()
        if (hasFace) {
            if (outputs.mesh)
                StageRegistration.transformVertices(serviceToStage, vertices)
                    .copyInto(result, VERTEX_OFFSET)
            if (outputs.spatial)
                StageRegistration.multiply(serviceToStage, geometryPose)
                    .copyInto(result, POSE_OFFSET)
        }
        return FaceFrame(
            result,
            labConfiguration,
            readbackSeconds,
            automatic,
            outputs,
            evidence,
            correction,
            presentationStabilization,
        )
    }

    companion object {
        const val RESULT_SIZE = 2994
        const val VERTEX_OFFSET = 1438
        const val BLENDSHAPE_OFFSET = 2872
        const val POSE_OFFSET = 2924
        const val TRACKING_OFFSET = 2946
    }
}
