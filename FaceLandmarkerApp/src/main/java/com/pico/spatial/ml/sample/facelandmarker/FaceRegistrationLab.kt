// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Build
import android.util.Base64
import android.util.Log
import java.io.File
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject

internal data class LabCapture(
    val source: ByteArray,
    val detector: ByteArray,
    val model: ByteArray,
    val modelLandmarks: FloatArray,
    val cropAffine: FloatArray,
    val captureFrame: FloatArray,
    val intrinsics: FloatArray,
    val serviceIntrinsics: FloatArray,
    val imageTransform: FloatArray,
    val mode: Int,
    val geometry: LabGeometryProbe,
    val calibrationRevision: Int = 0,
)

internal data class LabUi(
    val mode: Int = 0,
    val appliedMode: Int = -1,
    val readyFrames: Int = 0,
    val step: Int = 0,
    val meshStyle: Int = 0,
    val showModel: Boolean = true,
    val pending: Boolean = false,
    val saving: Boolean = false,
    val stopped: Boolean = false,
    val count: Int = 0,
    val acceptedCount: Int = 0,
    val repeatCount: Int = 0,
    val sequence: Int = 0,
    val message: String = "Starting registration lab…",
    val custom: LabIntrinsics = LabIntrinsics.modeC,
    val revision: Int = 0,
    val appliedRevision: Int = -1,
    val showCaptureTools: Boolean = false,
    val selectedParameter: IntrinsicParameter = IntrinsicParameter.FX,
    val adjustmentStep: Float = 5f,
    val profileBusy: Boolean = false,
    val savedProfileAvailable: Boolean = false,
    val profileMessage: String = "Start from C. Save values when the mesh aligns.",
    val poseCorrection: LabPoseCorrection = LabPoseCorrection(),
    val appliedPoseCorrection: LabPoseCorrection = LabPoseCorrection(),
    val stabilizeMesh: Boolean = true,
) {
    val locked
        get() = pending || saving || stopped || profileBusy

    val ready
        get() =
            !locked &&
                mode == appliedMode &&
                revision == appliedRevision &&
                poseCorrection == appliedPoseCorrection &&
                readyFrames >= 1
}

internal data class LabPreview(
    val sequence: Int,
    val mode: Int,
    val model: Bitmap,
    val source: Bitmap,
)

internal data class LabSaveRequest(
    val step: Int,
    val meshStyle: Int,
    val configuration: LabCameraConfiguration,
    val automatic: LabAutoTag? = null,
    val poseCorrection: LabPoseCorrection = LabPoseCorrection(),
)

/** Serial frame-boundary capture protocol. UI requests never mutate an in-flight graph. */
internal class FaceRegistrationLab(context: Context, val helmetMode: Boolean = false) :
    AutoCloseable {
    private val appContext = context.applicationContext
    private val commands =
        object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                val outcome = runCatching { handleCommand(intent) }
                val response = remoteStatus().put("accepted", outcome.isSuccess)
                outcome.exceptionOrNull()?.let { response.put("error", it.message) }
                resultCode = if (outcome.isSuccess) 0 else 1
                resultData =
                    "FACE_LAB_V1:" +
                        Base64.encodeToString(response.toString().toByteArray(), Base64.NO_WRAP)
            }
        }

    @Synchronized
    private fun handleCommand(intent: Intent) {
        val command = intent.getStringExtra("command")
        if (command == "status") return
        if (command == "occlusion_probe") {
            check(helmetMode) { "The depth probe requires the face effects renderer" }
            val mode = intent.getStringExtra("value")
            require(mode in listOf("off", "baseline", "depth")) {
                "Expected off, baseline or depth"
            }
            occlusionProbe.value = checkNotNull(mode)
            timeline.event("occlusion_probe_requested", JSONObject().put("mode", mode))
            return
        }
        check(!helmetMode || command == "outputs" || command == "latency") {
            "Helmet mode uses pose and face occlusion; calibration capture controls belong to the registration lab"
        }
        if (command == "auto_cancel") {
            cancelAutomatic()
            return
        }
        if (
            command in
                listOf("auto_start", "auto_check", "auto_geometry", "geometry_check", "auto_roll")
        ) {
            startAutomatic(
                command in listOf("auto_check", "geometry_check"),
                command in listOf("auto_geometry", "geometry_check", "auto_roll"),
                command == "auto_roll",
            )
            return
        }
        check(!automatic.ui.active) { "Automatic capture is running. Cancel it before editing." }
        val state = mutableUi.value
        check(trialsAvailable) { "Calibration is unavailable on this ROM" }
        if (command == "save_values") check(!state.profileBusy) { "Profile operation in progress" }
        else check(!state.locked) { state.message }
        when (command) {
            "latency" -> {
                trackingPacing = FaceTrackingPacing.parse(intent.getStringExtra("value"))
                timeline.event(
                    "tracking_pacing",
                    JSONObject().put("profile", trackingPacing.name.lowercase()),
                )
            }
            "outputs" -> {
                val mask = intent.getStringExtra("value")?.toIntOrNull()
                require(mask != null && mask in 0..7) { "Expected output mask 0..7" }
                require(
                    !helmetMode ||
                        mask == 0 ||
                        mask == FaceOutputs.HELMET.mask ||
                        mask == FaceOutputs.ALL.mask
                ) {
                    "Face effects support pose/mesh (mask 3), expressions (mask 7), or off (mask 0)"
                }
                requestedOutputs.value = FaceOutputs(mask)
            }
            "save" -> queueSave()
            "step" -> nextStep()
            "mode" -> cycleMode()
            "mesh" -> cycleMesh()
            "pose_correction" -> togglePoseCorrection()
            "save_values" -> saveValues()
            "load_values" -> loadValues()
            "reset_c" -> resetToC()
            "tools" -> toggleTools()
            "set" -> {
                val parameter =
                    IntrinsicParameter.entries.firstOrNull {
                        it.label == intent.getStringExtra("parameter")
                    }
                val value = intent.getStringExtra("value")?.toFloatOrNull()
                require(parameter != null && value != null && value.isFinite()) {
                    "Expected fx, fy, cx or cy and a finite pixel value"
                }
                require(value in parameter.range) { "Value is outside the allowed range" }
                adjust(parameter, value)
            }
            else -> error("Unknown calibration command")
        }
    }

    val requestedOutputs = MutableStateFlow(if (helmetMode) FaceOutputs.HELMET else FaceOutputs.ALL)
    val occlusionProbe = MutableStateFlow("off")
    @Volatile
    var trackingPacing = FaceTrackingPacing.FAST
        private set

    private var lastHelmetPose: JSONObject? = null

    @Synchronized
    fun helmetApplied(details: JSONObject) {
        lastHelmetPose = details
        timeline.event("helmet_pose_applied", details)
    }

    private var lastOutputFrame: FaceFrame? = null
    private var lastReadbackBytes = 0
    private var lastCalibrationEvidence = false
    private var lastFrameIntrinsics: LabIntrinsics? = null
    private var lastFrameNanos = 0L
    private var lastFrameHasFace = false

    @Synchronized
    private fun remoteStatus(): JSONObject {
        val state = mutableUi.value
        fun values(v: LabIntrinsics) =
            JSONObject()
                .put("fx", v.fx.toDouble())
                .put("fy", v.fy.toDouble())
                .put("cx", v.cx.toDouble())
                .put("cy", v.cy.toDouble())
        return JSONObject()
            .put("schema", 1)
            .put("renderer", if (helmetMode) "helmet" else "face_mesh")
            .put("helmet", lastHelmetPose ?: JSONObject.NULL)
            .put("requestedOutputMask", requestedOutputs.value.mask)
            .put("appliedOutputMask", lastOutputFrame?.outputs?.mask ?: JSONObject.NULL)
            .put("resultReadbackBytes", lastReadbackBytes)
            .put("calibrationEvidence", lastCalibrationEvidence)
            .put("trackingPacing", trackingPacing.name.lowercase())
            .put(
                "outputProbe",
                lastOutputFrame?.let { frame ->
                    JSONObject()
                        .put("frame", frame.sequence)
                        .put("pose", JSONArray(frame.pose))
                        .put("vertexCount", frame.vertices.size / 3)
                        .put("blendshapes", JSONArray(frame.blendshapes))
                        .put(
                            "maxReprojectionErrorPixels",
                            frame.maxReprojectionErrorPixels()?.takeIf { it.isFinite() }
                                ?: JSONObject.NULL,
                        )
                } ?: JSONObject.NULL,
            )
            .put("mode", state.mode)
            .put("modeLabel", MODES[state.mode])
            .put("revision", state.revision)
            .put("values", values(state.custom))
            .put("appliedMode", state.appliedMode)
            .put("appliedRevision", state.appliedRevision)
            .put("appliedValues", lastFrameIntrinsics?.let(::values) ?: JSONObject.NULL)
            .put("frame", state.sequence)
            .put(
                "frameAgeSeconds",
                if (lastFrameNanos == 0L) JSONObject.NULL
                else (System.nanoTime() - lastFrameNanos) * 1e-9,
            )
            .put("hasFace", lastFrameHasFace)
            .put("trackingState", lastOutputFrame?.trackingState?.takeIf { it.isFinite() })
            .put(
                "trackingFailureReason",
                lastOutputFrame?.trackingFailureReason?.takeIf { it.isFinite() },
            )
            .put("trackingIdentity", lastOutputFrame?.trackingIdentity?.takeIf { it.isFinite() })
            .put("presence", lastOutputFrame?.presence?.takeIf { it.isFinite() })
            .put("detection", lastOutputFrame?.detection?.takeIf { it.isFinite() })
            .put("poseStatus", lastOutputFrame?.poseStatus?.takeIf { it.isFinite() })
            .put("locked", state.locked)
            .put("poseCorrection", state.poseCorrection.json())
            .put("appliedPoseCorrection", state.appliedPoseCorrection.json())
            .put("stopped", state.stopped)
            .put("trialsAvailable", trialsAvailable)
            .put("profileBusy", state.profileBusy)
            .put("savedProfileAvailable", state.savedProfileAvailable)
            .put("message", state.message)
            .put("profileMessage", state.profileMessage)
            .put("timeline", timeline.reference())
            .put("automatic", automatic.ui.json())
    }

    private val root = File(checkNotNull(context.getExternalFilesDir(null)), "RegistrationLab")
    private val session =
        File(
            root,
            Instant.now().toString().replace(':', '-') + "-" + UUID.randomUUID().toString().take(6),
        )
    private val calibrationStore = LabCalibrationStore(context)
    val timeline = LabTimeline(session)
    private val automatic = LabAutoCapture()
    private val mutableAutomaticUi = MutableStateFlow(automatic.ui)
    val automaticUi = mutableAutomaticUi.asStateFlow()
    val geometryCaptureActive: Boolean
        @Synchronized get() = automatic.tag?.protocol == LabProjectionReference.PROTOCOL

    private var automaticOriginal: LabCameraConfiguration? = null
    private var automaticOriginalCorrection: LabPoseCorrection? = null
    private var automaticOriginalPreview: Boolean? = null
    private var automaticLastState = ""
    private var automaticExport: LabAutoTag? = null
    private val savedReading = runCatching { calibrationStore.load() }
    private val mutableUi =
        MutableStateFlow(
            LabUi(
                mode =
                    if (Build.FINGERPRINT == LabCameraProfile.FINGERPRINT)
                        LabCameraProfile.STEREO_MODE
                    else 0,
                poseCorrection =
                    if (Build.FINGERPRINT == LabCameraProfile.FINGERPRINT)
                        LabPoseCorrection(true, stereo = true)
                    else LabPoseCorrection(),
                custom = savedReading.getOrNull() ?: LabIntrinsics.modeC,
                savedProfileAvailable = savedReading.getOrNull() != null,
                profileMessage =
                    if (savedReading.isFailure)
                        "Saved values could not be loaded. Using stereo calibration."
                    else if (savedReading.getOrNull() != null)
                        "Stereo calibration active. Previous custom values preserved."
                    else "Stereo calibration active.",
            )
        )
    val ui = mutableUi.asStateFlow()
    private val mutablePreview = MutableStateFlow<LabPreview?>(null)
    val preview = mutablePreview.asStateFlow()
    val trialsAvailable = Build.FINGERPRINT == LabCameraProfile.FINGERPRINT
    private var saveAfter = 0.0
    private var queuedConfiguration: LabCameraConfiguration? = null
    private val profileScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var lastPreview = 0.0
    private val packageName = context.packageName

    init {
        // Local shell helper for repeatable capture, restricted to callers with Android DUMP.
        val filter = IntentFilter("$packageName.COMMAND")
        if (Build.VERSION.SDK_INT >= 33)
            appContext.registerReceiver(
                commands,
                filter,
                "android.permission.DUMP",
                null,
                Context.RECEIVER_EXPORTED,
            )
        else appContext.registerReceiver(commands, filter, "android.permission.DUMP", null)
        profileScope.launch {
            while (true) {
                delay(100)
                synchronized(this@FaceRegistrationLab) {
                    automatic.tick(System.nanoTime() * 1e-9)
                    publishAutomatic()
                }
            }
        }
    }

    override fun close() {
        cancelAutomatic()
        appContext.unregisterReceiver(commands)
        mutableUi.value = mutableUi.value.copy(poseCorrection = LabPoseCorrection())
        timeline.close()
        profileScope.cancel()
    }

    @Synchronized
    fun configuration(): LabCameraConfiguration =
        automatic.configuration
            ?: mutableUi.value.let { LabCameraConfiguration(it.mode, it.custom, it.revision) }

    @Synchronized fun poseCorrection(): LabPoseCorrection = mutableUi.value.poseCorrection

    @Synchronized
    fun stabilizeMesh(): Boolean =
        mutableUi.value.let {
            it.stabilizeMesh && !it.locked && !it.showCaptureTools && !automatic.ui.active
        }

    @Synchronized
    fun toggleMeshStabilization() {
        val state = mutableUi.value
        if (!state.locked && !automatic.ui.active)
            mutableUi.value = state.copy(stabilizeMesh = !state.stabilizeMesh)
    }

    /** One immutable camera/correction pair for the entire inference and render operation. */
    @Synchronized
    fun frameSettings(): Pair<LabCameraConfiguration, LabPoseCorrection> =
        configuration() to mutableUi.value.poseCorrection

    @Synchronized
    fun toggleStereoCalibration() {
        val s = mutableUi.value
        if (s.locked || automatic.ui.active || !trialsAvailable) return
        val mode =
            if (s.mode == LabCameraProfile.STEREO_MODE) LabCameraProfile.CUSTOM_MODE
            else LabCameraProfile.STEREO_MODE
        mutableUi.value =
            s.copy(
                mode = mode,
                poseCorrection = s.poseCorrection.forMode(mode),
                revision = s.revision + 1,
                readyFrames = 0,
                message = "Applying ${MODES[mode]}…",
            )
        mutablePreview.value = null
    }

    @Synchronized
    fun togglePoseCorrection() {
        val state = mutableUi.value
        if (state.locked || automatic.ui.active || !trialsAvailable || state.poseCorrection.stereo)
            return
        val next =
            state.poseCorrection.copy(
                enabled = !state.poseCorrection.enabled,
                revision = state.poseCorrection.revision + 1,
            )
        mutableUi.value =
            state.copy(poseCorrection = next, readyFrames = 0, message = "Applying ${next.label}…")
        timeline.event("pose_correction_selected", next.json())
    }

    @Synchronized
    fun adjust(parameter: IntrinsicParameter, value: Float) {
        val s = mutableUi.value
        if (s.locked || !trialsAvailable || !value.isFinite()) return
        val next = s.custom.adjusted(parameter, value)
        if (next == s.custom && s.mode == LabCameraProfile.CUSTOM_MODE) return
        mutableUi.value =
            s.copy(
                mode = LabCameraProfile.CUSTOM_MODE,
                poseCorrection = s.poseCorrection.forMode(LabCameraProfile.CUSTOM_MODE),
                custom = next,
                revision = s.revision + 1,
                readyFrames = 0,
                message = "Applying camera values…",
                profileMessage = "Unsaved changes",
            )
    }

    @Synchronized
    fun cycleParameter() {
        val s = mutableUi.value
        if (!s.locked)
            mutableUi.value =
                s.copy(
                    selectedParameter =
                        IntrinsicParameter.entries[
                                (s.selectedParameter.ordinal + 1) % IntrinsicParameter.entries.size]
                )
    }

    @Synchronized
    fun cycleAdjustmentStep() {
        val s = mutableUi.value
        if (!s.locked)
            mutableUi.value =
                s.copy(
                    adjustmentStep =
                        when (s.adjustmentStep) {
                            .5f -> 5f
                            5f -> 25f
                            else -> .5f
                        }
                )
    }

    @Synchronized
    fun resetToC() {
        val s = mutableUi.value
        if (!s.locked && trialsAvailable)
            mutableUi.value =
                s.copy(
                    mode = LabCameraProfile.CUSTOM_MODE,
                    poseCorrection = s.poseCorrection.forMode(LabCameraProfile.CUSTOM_MODE),
                    custom = LabIntrinsics.modeC,
                    revision = s.revision + 1,
                    readyFrames = 0,
                    message = "Applying C starting values…",
                    profileMessage = "C starting values. Save to keep them.",
                )
    }

    @Synchronized
    fun toggleTools() {
        val s = mutableUi.value
        if (s.locked) return
        val returningToCustom =
            s.showCaptureTools &&
                trialsAvailable &&
                s.mode != LabCameraProfile.CUSTOM_MODE &&
                s.mode != LabCameraProfile.STEREO_MODE
        mutableUi.value =
            s.copy(
                showCaptureTools = !s.showCaptureTools,
                mode = if (returningToCustom) LabCameraProfile.CUSTOM_MODE else s.mode,
                poseCorrection =
                    s.poseCorrection.forMode(
                        if (returningToCustom) LabCameraProfile.CUSTOM_MODE else s.mode
                    ),
                revision = s.revision + if (returningToCustom) 1 else 0,
                readyFrames = if (returningToCustom) 0 else s.readyFrames,
            )
    }

    @Synchronized
    fun saveValues() {
        val s = mutableUi.value
        if (s.profileBusy || !trialsAvailable) return
        if (s.mode == LabCameraProfile.STEREO_MODE) {
            mutableUi.value =
                s.copy(
                    profileMessage =
                        "Stereo calibration is built in. Previous custom values are unchanged."
                )
            return
        }
        val values = s.custom
        mutableUi.value = s.copy(profileBusy = true, profileMessage = "Saving calibration…")
        profileScope.launch {
            val result = runCatching { calibrationStore.save(values) }
            synchronized(this@FaceRegistrationLab) {
                val current = mutableUi.value
                mutableUi.value =
                    current.copy(
                        profileBusy = false,
                        savedProfileAvailable = result.isSuccess || current.savedProfileAvailable,
                        profileMessage =
                            if (result.isSuccess) "Calibration saved on this headset."
                            else "Could not save calibration: ${result.exceptionOrNull()?.message}",
                    )
            }
            result
                .onSuccess {
                    Log.i(
                        FaceLandmarkerRunner.TAG,
                        "registration_lab_values_saved fx=${values.fx} fy=${values.fy} cx=${values.cx} cy=${values.cy} path=$it",
                    )
                }
                .onFailure {
                    Log.w(FaceLandmarkerRunner.TAG, "registration_lab_values_save_failed", it)
                }
        }
    }

    @Synchronized
    fun loadValues() {
        val s = mutableUi.value
        if (s.locked || !trialsAvailable) return
        mutableUi.value = s.copy(profileBusy = true, profileMessage = "Loading calibration…")
        profileScope.launch {
            val result = runCatching {
                checkNotNull(calibrationStore.load()) { "No saved calibration" }
            }
            synchronized(this@FaceRegistrationLab) {
                val current = mutableUi.value
                mutableUi.value =
                    result.fold(
                        onSuccess = {
                            current.copy(
                                profileBusy = false,
                                custom = it,
                                mode = LabCameraProfile.CUSTOM_MODE,
                                poseCorrection =
                                    current.poseCorrection.forMode(LabCameraProfile.CUSTOM_MODE),
                                revision = current.revision + 1,
                                readyFrames = 0,
                                savedProfileAvailable = true,
                                message = "Applying saved values…",
                                profileMessage = "Loaded saved calibration.",
                            )
                        },
                        onFailure = {
                            current.copy(
                                profileBusy = false,
                                profileMessage = "Could not load calibration: ${it.message}",
                            )
                        },
                    )
            }
        }
    }

    @Synchronized
    fun cycleMode() {
        val s = mutableUi.value
        if (!s.locked && trialsAvailable) {
            mutableUi.value =
                s.copy(
                    mode = (s.mode + 1) % LabCameraProfile.MODE_COUNT,
                    poseCorrection =
                        s.poseCorrection.forMode((s.mode + 1) % LabCameraProfile.MODE_COUNT),
                    readyFrames = 0,
                    revision = s.revision + 1,
                    message = "Switching camera mode…",
                )
            mutablePreview.value = null
        }
    }

    @Synchronized
    fun nextStep() {
        val s = mutableUi.value
        if (!s.locked) mutableUi.value = s.copy(step = (s.step + 1) % STEPS.size, readyFrames = 0)
    }

    @Synchronized
    fun cycleMesh() {
        val s = mutableUi.value
        if (!s.locked) mutableUi.value = s.copy(meshStyle = (s.meshStyle + 1) % 3)
    }

    @Synchronized
    fun togglePreview() {
        val s = mutableUi.value
        mutableUi.value = s.copy(showModel = !s.showModel)
    }

    @Synchronized
    fun queueSave() {
        val s = mutableUi.value
        if (s.locked || s.count >= 100) return
        saveAfter = System.nanoTime() * 1e-9 + 1
        queuedConfiguration = configuration()
        mutableUi.value =
            s.copy(
                pending = true,
                message = "Capture queued. Hold still for the next usable frame…",
            )
    }

    @Synchronized
    fun markFrame(
        configuration: LabCameraConfiguration,
        sequence: Int,
        fresh: Boolean,
        reason: String,
        intrinsics: FloatArray? = null,
        hasFace: Boolean = false,
        correction: LabPoseCorrection = poseCorrection(),
    ) {
        lastFrameIntrinsics =
            intrinsics
                ?.takeIf { it.size == 9 }
                ?.let { runCatching { LabIntrinsics(it[0], it[4], it[2], it[5]) }.getOrNull() }
        lastFrameNanos = System.nanoTime()
        lastFrameHasFace = hasFace
        val s = mutableUi.value
        val matches = configuration == this.configuration() && correction == s.poseCorrection
        val count = if (fresh && matches) 1 else 0
        mutableUi.value =
            s.copy(
                appliedMode = configuration.mode,
                appliedRevision = configuration.revision,
                appliedPoseCorrection = correction,
                readyFrames = count,
                sequence = sequence,
                message =
                    if (s.locked) s.message
                    else if (!matches) "Applying camera values or mesh position…"
                    else if (count > 0) "Ready. Capture sample to record this view." else reason,
            )
    }

    @Synchronized
    fun takeSave(
        configuration: LabCameraConfiguration,
        eligible: Boolean,
        reason: String,
    ): LabSaveRequest? {
        val s = mutableUi.value
        if (!s.pending || System.nanoTime() * 1e-9 < saveAfter) return null
        val requested = checkNotNull(queuedConfiguration)
        if (
            !eligible || requested != configuration || s.appliedPoseCorrection != s.poseCorrection
        ) {
            if (System.nanoTime() * 1e-9 > saveAfter + 15) {
                fail("No usable frame: $reason. Calibration values can still be saved.")
            } else mutableUi.value = s.copy(message = "Capture queued: $reason")
            return null
        }
        mutableUi.value =
            s.copy(
                pending = false,
                saving = true,
                message = "Capturing… hold still until Image captured",
            )
        queuedConfiguration = null
        return LabSaveRequest(s.step, s.meshStyle, requested, poseCorrection = s.poseCorrection)
    }

    @Synchronized
    fun imageCaptured() {
        val s = mutableUi.value
        if (s.saving)
            mutableUi.value =
                s.copy(
                    message =
                        if (automatic.ui.active) "Image captured. Keep still for the next phase."
                        else "Image captured. You may move; exporting…"
                )
    }

    @Synchronized
    fun toggleDiagnosticPreview() {
        val state = mutableUi.value
        if (state.locked || automatic.ui.active) return
        mutableUi.value = state.copy(showCaptureTools = !state.showCaptureTools)
    }

    fun previewDue(): Boolean =
        mutableUi.value.showCaptureTools && System.nanoTime() * 1e-9 - lastPreview >= 1.0

    @Synchronized
    fun fail(message: String, fatal: Boolean = false) {
        val s = mutableUi.value
        queuedConfiguration = null
        if (automatic.ui.active) automatic.stop("FAILED", "Capture stopped: $message")
        automaticExport = null
        publishAutomatic()
        mutableUi.value =
            mutableUi.value.copy(
                pending = false,
                saving = false,
                stopped = fatal,
                repeatCount = s.repeatCount + if (s.saving || s.pending) 1 else 0,
                message = if (fatal) "Stopped: $message" else "Save failed: $message",
            )
    }

    @Synchronized
    fun startAutomatic(
        single: Boolean,
        geometry: Boolean = false,
        rollOnly: Boolean = false,
        boardKind: String = "",
    ) {
        require(boardKind.isEmpty() || boardKind in LabBoardCapture.kinds)
        require(boardKind.isEmpty() || !rollOnly)
        check(
            trialsAvailable &&
                !mutableUi.value.locked &&
                !automatic.ui.active &&
                automaticExport == null
        ) {
            "Wait for the current operation before starting automatic capture"
        }
        check(
            mutableUi.value.count +
                (if (boardKind.isNotEmpty()) LabBoardCapture.count(boardKind)
                else if (rollOnly) LabRollCapture.prompts.size * 3
                else if (single) 3
                else if (geometry) LabProjectionReference.prompts.size * 3 else 84) <= 100
        ) {
            "Start a new app session for this capture sequence"
        }
        check(timeline.ui.value.logging) { "Timeline logging is unavailable" }
        automaticOriginal = configuration()
        automaticOriginalCorrection =
            mutableUi.value.poseCorrection.takeIf { boardKind.isNotEmpty() || it.stereo }
        if (boardKind.isNotEmpty()) {
            automaticOriginalPreview = mutableUi.value.showCaptureTools
            mutableUi.value =
                mutableUi.value.copy(
                    poseCorrection =
                        LabPoseCorrection(false, mutableUi.value.poseCorrection.revision + 1),
                    readyFrames = 0,
                )
        } else {
            mutableUi.value =
                mutableUi.value.copy(
                    poseCorrection =
                        mutableUi.value.poseCorrection.forMode(LabCameraProfile.CUSTOM_MODE),
                    readyFrames = 0,
                )
        }
        automatic.start(
            UUID.randomUUID().toString().take(8),
            checkNotNull(automaticOriginal),
            single,
            System.nanoTime() * 1e-9,
            geometry,
            rollOnly,
            boardKind,
        )
        mutableUi.value = mutableUi.value.copy(showCaptureTools = false)
        publishAutomatic()
    }

    @Synchronized
    fun cancelAutomatic() {
        if (automatic.ui.active) automatic.stop()
        publishAutomatic()
    }

    @Synchronized
    private fun publishAutomatic() {
        if (automatic.ui.active && !timeline.ui.value.logging)
            automatic.stop("FAILED", "Evidence logging failed. Stop recording and reopen this app.")
        if (!automatic.ui.active)
            automaticOriginal?.let { original ->
                val s = mutableUi.value
                mutableUi.value =
                    s.copy(
                        mode = original.mode,
                        custom = original.custom,
                        revision = maxOf(s.revision, original.revision) + 1,
                        readyFrames = 0,
                    )
                automaticOriginalCorrection?.let { correction ->
                    mutableUi.value =
                        mutableUi.value.copy(
                            poseCorrection =
                                correction.copy(
                                    revision = mutableUi.value.poseCorrection.revision + 1
                                )
                        )
                }
                automaticOriginalPreview?.let { preview ->
                    mutableUi.value = mutableUi.value.copy(showCaptureTools = preview)
                }
                automaticOriginalPreview = null
                automaticOriginalCorrection = null
                automaticOriginal = null
            }
        automatic.configuration?.let { c ->
            mutableUi.value =
                mutableUi.value.copy(mode = c.mode, custom = c.custom, revision = c.revision)
        }
        mutableAutomaticUi.value = automatic.ui
        val key =
            "${automatic.ui.run}/${automatic.ui.trial}/${automatic.ui.phase}/${automatic.ui.saved}"
        if (key != automaticLastState) {
            automaticLastState = key
            timeline.event("automatic_state", automatic.ui.json())
        }
    }

    @Synchronized
    fun automaticTag(configuration: LabCameraConfiguration?): LabAutoTag? =
        automatic.tag?.let {
            if (configuration == automatic.configuration) it else it.copy(phase = "APPLYING")
        }

    @Synchronized
    fun pipelineFrame(
        frame: FaceFrame,
        submitSeconds: Double,
        readbackSeconds: Double,
        detector: Boolean,
        rejection: String?,
        exposureMotion: LabMotion,
        readbackBytes: Int,
        nativeFaceValidity: Float,
        nativePacketFinite: Boolean,
        calibrationEvidence: Boolean,
        decodedSeconds: Double,
        registeredSeconds: Double,
        correction: LabPoseCorrection = LabPoseCorrection(),
        pacing: FaceTrackingPacing = FaceTrackingPacing.LEGACY,
    ) {
        lastOutputFrame = frame
        lastReadbackBytes = readbackBytes
        lastCalibrationEvidence = calibrationEvidence
        timeline.event(
            "pipeline_frame",
            JSONObject()
                .put("frame", frame.sequence)
                .put("captureSeconds", frame.captureSeconds)
                .put("submitSeconds", submitSeconds)
                .put("readbackSeconds", readbackSeconds)
                .put("submitToReadbackSeconds", readbackSeconds - submitSeconds)
                .put("outputMask", frame.outputs.mask)
                .put("trackingPacing", pacing.name.lowercase())
                .put("frameIdleMillis", pacing.idleMillis)
                .put("completionPollMillis", pacing.pollMillis)
                .put("poseCorrection", correction.json())
                .put("resultSchema", if (calibrationEvidence) 1 else 2)
                .put("readbackBytes", readbackBytes)
                .put("calibrationEvidence", calibrationEvidence)
                .put("appDecodeSeconds", decodedSeconds - readbackSeconds)
                .put("appRegistrationSeconds", registeredSeconds - decodedSeconds)
                .put("cameraAgeAtReadbackSeconds", readbackSeconds - frame.captureSeconds)
                .put("detector", detector)
                .put("hasFace", frame.hasFace)
                .put("nativeFaceValidity", nativeFaceValidity.takeIf { it.isFinite() })
                .put("nativePacketFinite", nativePacketFinite)
                .put("presence", frame.presence.takeIf { it.isFinite() })
                .put("detection", frame.detection.takeIf { it.isFinite() })
                .put("trackingState", frame.trackingState.takeIf { it.isFinite() })
                .put("trackingFailureReason", frame.trackingFailureReason.takeIf { it.isFinite() })
                .put("trackingIdentity", frame.trackingIdentity.takeIf { it.isFinite() })
                .put("poseStatus", frame.poseStatus.takeIf { it.isFinite() })
                .put("freshCameraFrame", frame.freshCameraFrame)
                .put("rejection", rejection ?: JSONObject.NULL)
                .put("exposureMotionCovered", exposureMotion.covered)
                .put("exposureMotionMetres", exposureMotion.metres)
                .put("exposureMotionDegrees", exposureMotion.degrees)
                .put("exposureStable", exposureMotion.stable),
        )
    }

    @Synchronized
    fun automaticFrame(
        frame: FaceFrame?,
        usable: Boolean,
        headStable: Boolean,
        now: Double,
    ): LabSaveRequest? {
        val tag =
            automatic.frame(
                frame,
                usable && frame?.poseCorrection == mutableUi.value.poseCorrection,
                headStable,
                now,
            )
        publishAutomatic()
        if (tag == null) return null
        automaticExport = tag
        mutableUi.value =
            mutableUi.value.copy(
                saving = true,
                message = "Automatic capture exporting. Keep still.",
            )
        return LabSaveRequest(
            tag.pose,
            if (tag.markers && !tag.board) 3 else 2,
            checkNotNull(frame?.labConfiguration),
            tag,
            checkNotNull(frame).poseCorrection,
        )
    }

    @Synchronized
    fun sceneApplied(
        frame: FaceFrame?,
        visible: Boolean,
        uploadedGeometry: JSONObject? = null,
        stabilization: JSONObject? = null,
        uploadTiming: JSONObject? = null,
    ) {
        timeline.meshApplied(frame, visible, stabilization = stabilization)
        uploadTiming?.let {
            check(frame != null && it.getInt("frame") == frame.sequence)
            timeline.event("mesh_upload_timing", it.put("visible", visible))
        }
        if (
            frame?.automatic?.protocol == LabProjectionReference.PROTOCOL &&
                uploadedGeometry != null
        ) {
            timeline.event(
                "projection_reference",
                uploadedGeometry
                    .put("frame", frame.sequence)
                    .put("captureSeconds", frame.captureSeconds)
                    .put("automatic", frame.automatic.json())
                    .put(
                        "rollCapture",
                        LabRollCapture.evidence(
                            frame.automatic,
                            frame.registrationEvidence?.headToStage,
                        ) ?: JSONObject.NULL,
                    )
                    .put(
                        "faceClearRegionAccepted",
                        if (frame.automatic.rollOnly) LabRollCapture.faceClear(frame)
                        else JSONObject.NULL,
                    )
                    .put(
                        "faceMarkers",
                        if (frame.automatic.board) JSONArray()
                        else LabAutoCapture.markersJson(frame),
                    )
                    .put("poseCorrection", frame.poseCorrection.json())
                    .put(
                        "rawFaceMarkers",
                        if (frame.automatic.board) JSONArray()
                        else LabAutoCapture.markersJson(frame.withRawStageVertices()),
                    )
                    .put(
                        "timingBoundary",
                        "mesh replacement completed; frame code identifies displayed payload",
                    ),
            )
        }
        frame?.automatic?.let { tag ->
            automatic.sceneApplied(tag, frame.sequence, System.nanoTime() * 1e-9)
            timeline.event(
                "automatic_scene",
                tag.json()
                    .put("frame", frame.sequence)
                    .put("visible", visible)
                    .put("configurationRevision", frame.labConfiguration?.revision)
                    .put("poseCorrection", frame.poseCorrection.json())
                    .put("captureSeconds", frame.captureSeconds)
                    .put(
                        "rollCapture",
                        LabRollCapture.evidence(tag, frame.registrationEvidence?.headToStage)
                            ?: JSONObject.NULL,
                    )
                    .put(
                        "markers",
                        if (tag.markers && visible && !tag.board) LabAutoCapture.markersJson(frame)
                        else JSONArray(),
                    ),
            )
        }
    }

    @Synchronized
    private fun automaticSceneMatches(tag: LabAutoTag, sequence: Int): Boolean =
        automatic.sceneMatches(tag, sequence)

    suspend fun publishPreview(capture: LabCapture, raw: FaceFrame) =
        withContext(Dispatchers.Default) {
            val model = rgbBitmap(capture.model, 256, 256)
            val sourceFull = rgbBitmap(capture.source, 1624, 1232)
            val source = Bitmap.createScaledBitmap(sourceFull, 406, 308, true)
            sourceFull.recycle()
            if (raw.hasFace) {
                val paint =
                    Paint().apply {
                        color = Color.GREEN
                        isAntiAlias = true
                    }
                val modelCanvas = Canvas(model)
                val sourceCanvas = Canvas(source)
                val landmarks = raw.landmarks
                for (i in 0 until 478) {
                    modelCanvas.drawCircle(
                        capture.modelLandmarks[i * 3],
                        capture.modelLandmarks[i * 3 + 1],
                        1f,
                        paint,
                    )
                    // Trial A is diagonal+translation, so invert without rounding source landmarks.
                    val x =
                        (landmarks[i * 3] * 3248 - capture.imageTransform[2]) /
                            capture.imageTransform[0]
                    val y =
                        (landmarks[i * 3 + 1] * 2464 - capture.imageTransform[5]) /
                            capture.imageTransform[4]
                    sourceCanvas.drawCircle(x / 8, y / 8, 1f, paint)
                }
            }
            mutablePreview.value = LabPreview(raw.sequence, capture.mode, model, source)
            lastPreview = System.nanoTime() * 1e-9
        }

    suspend fun save(
        request: LabSaveRequest,
        capture: LabCapture,
        raw: FaceFrame,
        stage: FaceFrame?,
        headAtCapture: FloatArray?,
        cameraToHead: FloatArray,
        headAtReadback: FloatArray?,
        headAfterReadback: FloatArray?,
        poseSamples: List<Pair<Double, FloatArray>>,
        readbackSeconds: Double,
        exportCompletedSeconds: Double,
        submitSeconds: Double,
    ) =
        withContext(Dispatchers.IO) {
            require(
                capture.mode == request.configuration.mode &&
                    capture.calibrationRevision == request.configuration.revision
            ) {
                "Capture used different camera settings; repeat"
            }
            if (capture.mode == LabCameraProfile.CUSTOM_MODE)
                require(request.configuration.custom.matches(capture.intrinsics)) {
                    "Capture intrinsics did not match requested calibration; repeat"
                }
            require(capture.captureFrame[3] > 0 && capture.captureFrame[4] == 0f) {
                "Camera frame was stale; repeat"
            }
            require(stage != null && headAtCapture != null) {
                "Matching Stage head pose unavailable; repeat"
            }
            require(stage.poseCorrection == request.poseCorrection) {
                "Capture used a different mesh position; repeat"
            }
            require(
                raw.hasFace || request.automatic?.board == true || request.step == STEPS.lastIndex
            ) {
                "No measured face; repeat when tracking"
            }
            require(raw.packet().all(Float::isFinite)) { "Non-finite result packet" }
            val exposure =
                LabMotion.measure(poseSamples, raw.captureSeconds - .05, raw.captureSeconds + .05)
            val export =
                LabMotion.measure(
                    poseSamples,
                    raw.captureSeconds - .5,
                    exportCompletedSeconds - .05,
                )
            val rawTransform =
                StageRegistration.serviceToStage(headAtCapture, cameraToHead, raw.captureCameraPose)
            val transform =
                request.poseCorrection.serviceToStage(
                    headAtCapture,
                    cameraToHead,
                    raw.captureCameraPose,
                )
            val json =
                JSONObject().apply {
                    put("schema", 3)
                    put("calibrationRevision", request.configuration.revision)
                    put(
                        "customCalibration",
                        if (capture.mode == LabCameraProfile.CUSTOM_MODE)
                            LabCalibrationStore.encode(request.configuration.custom)
                        else JSONObject.NULL,
                    )
                    put("app", "Kotlin Face Registration Lab")
                    put("package", packageName)
                    put("utc", Instant.now().toString())
                    put("fingerprint", Build.FINGERPRINT)
                    put("session", session.name)
                    put("sequence", raw.sequence)
                    put("timeline", timeline.reference())
                    put("mode", capture.mode)
                    put("modeLabel", MODES[capture.mode])
                    put(
                        "step",
                        request.automatic?.poseLabel?.takeIf { it.isNotEmpty() }
                            ?: STEPS[request.step],
                    )
                    put("meshStyle", MESH_STYLES[request.meshStyle])
                    put("sourceWidth", 1624)
                    put("sourceHeight", 1232)
                    put("nativeWidth", 3248)
                    put("nativeHeight", 2464)
                    put("sourceScale", .5)
                    put(
                        "sourceStream",
                        JSONObject()
                            .put("nativeWidth", 3248)
                            .put("nativeHeight", 2464)
                            .put("savedWidth", 1624)
                            .put("savedHeight", 1232)
                            .put("mode", capture.mode)
                            .put("compactVst", BuildConfig.FACE_COMPACT_VST_PIPELINE)
                            .put("retainedVst", BuildConfig.FACE_RETAINED_VST_PIPELINE)
                            .put("gpuPreprocessing", BuildConfig.FACE_GPU_PREPROCESSING)
                            .put("fusedControls", BuildConfig.FACE_FUSED_CONTROL_MODELS)
                            .put("note", "source export before imageTransform; RGB uint8"),
                    )
                    put("pixels", "RGB uint8, top-left origin; model input = pixel / 255")
                    put(
                        "coordinates",
                        "Row-major column-vector matrices; right-handed metres. result vertices/pose are service Local. stageResult vertices/pose are Stage. No Unity Z reflection.",
                    )
                    put(
                        "poseTiming",
                        "Camera pose uses capture timestamp. Stage history uses System.nanoTime at public HMD callback arrival, not hardware timestamps; timing error remains possible.",
                    )
                    put("monotonicSecondsAtReadback", readbackSeconds)
                    put("monotonicSecondsAtSubmit", submitSeconds)
                    put("frameReadbackLatencySeconds", readbackSeconds - submitSeconds)
                    put("cameraAgeAtSubmitSeconds", submitSeconds - raw.captureSeconds)
                    put("cameraAgeAtReadbackSeconds", readbackSeconds - raw.captureSeconds)
                    put("captureSeconds", raw.captureSeconds)
                    put("stereoEnabled", false)
                    put(
                        "eyeProjectionStatus",
                        "UNAVAILABLE: public per-eye render matrices are not provided by this Kotlin capture path",
                    )
                    put("sizeScale", 1)
                    put(
                        "boardCapture",
                        request.automatic?.takeIf { it.board }?.let(LabBoardCapture::metadata)
                            ?: JSONObject.NULL,
                    )
                    put(
                        "registrationEvidence",
                        stage.registrationEvidence?.json(request.automatic?.sideReferences == true)
                            ?: JSONObject.NULL,
                    )
                    put("headHistoryCovered", export.covered)
                    put("headMovementMetres", export.metres)
                    put("headMovementDegrees", export.degrees)
                    put("headStableDuringReadback", export.stable)
                    put(
                        "exposureWindowSeconds",
                        JSONArray(listOf(raw.captureSeconds - .05, raw.captureSeconds + .05)),
                    )
                    put("exposureHistoryCovered", exposure.covered)
                    put("headMovementAtExposureMetres", exposure.metres)
                    put("headMovementAtExposureDegrees", exposure.degrees)
                    put("headStableAtExposure", exposure.stable)
                    put("monotonicSecondsAfterExport", exportCompletedSeconds)
                    put(
                        "captureAcceptance",
                        if (exposure.stable) "EXPOSURE_STABLE"
                        else "REPEAT_EXPOSURE_MOTION_OR_HISTORY",
                    )
                    put("geometryProbe", capture.geometry.json(raw.packet()))
                    put(
                        "cameraProfile",
                        if (capture.mode == LabCameraProfile.STEREO_MODE) LabStereoCalibration.ID
                        else if (capture.mode == 3) LabCameraProfile.MEASURED_PROFILE
                        else MODES[capture.mode],
                    )
                    put(
                        "measuredSourceIntrinsics",
                        if (capture.mode == LabCameraProfile.STEREO_MODE)
                            floats(LabStereoCalibration.sourceIntrinsics)
                        else if (capture.mode == 3)
                            floats(LabCameraProfile.measuredSourceIntrinsics)
                        else JSONObject.NULL,
                    )
                    put("captureFrame", floats(capture.captureFrame))
                    put("result", floats(raw.packet()))
                    put("stageResult", floats(stage.packet()))
                    put("modelLandmarks", floats(capture.modelLandmarks))
                    put("cropAffine", floats(capture.cropAffine))
                    put("imageTransform", floats(capture.imageTransform))
                    put("cameraIntrinsics", floats(capture.intrinsics))
                    put("serviceIntrinsics", floats(capture.serviceIntrinsics))
                    put("cameraToTracking", floats(raw.captureCameraPose))
                    put("cameraToHead", floats(cameraToHead))
                    put("headToStageAtCapture", floats(headAtCapture))
                    put("serviceToStage", floats(transform))
                    put("rawServiceToStage", floats(rawTransform))
                    put("poseCorrection", request.poseCorrection.json())
                    put("headToStageAtReadback", headAtReadback?.let(::floats) ?: JSONObject.NULL)
                    put(
                        "headToStageAfterReadback",
                        headAfterReadback?.let(::floats) ?: JSONObject.NULL,
                    )
                    put(
                        "headPoseHistory",
                        JSONArray().apply {
                            poseSamples.forEach { (time, pose) ->
                                put(
                                    JSONObject()
                                        .put("seconds", time)
                                        .put("headToStage", floats(pose))
                                )
                            }
                        },
                    )
                }
            request.automatic?.let { tag ->
                require(exposure.stable) { "Head moved during automatic exposure" }
                if (tag.board) {
                    require(!request.poseCorrection.enabled && capture.mode == 0) {
                        "Board capture requires Mode A and Current position"
                    }
                    require(
                        LabRollCapture.validHead(headAtCapture) &&
                            LabRollCapture.validHead(cameraToHead)
                    ) {
                        "Invalid board capture transforms"
                    }
                }
                if (tag.rollOnly) {
                    require(
                        LabRollCapture.motion(
                                tag.rollBaseline,
                                stage.registrationEvidence?.headToStage,
                            )
                            ?.ready(tag.pose) == true
                    ) {
                        "Roll capture is outside its measured orientation target"
                    }
                    require(LabRollCapture.faceClear(stage)) {
                        "Face overlaps the reserved reference border"
                    }
                    json.put(
                        "rollCapture",
                        LabRollCapture.evidence(tag, stage.registrationEvidence?.headToStage),
                    )
                }
                val packet = raw.packet()
                val difference = capture.geometry.resultDifference(packet)
                if (!capture.geometry.resultMatches(packet)) {
                    val folder = File(session, "RejectedCaptures").apply { mkdirs() }
                    val rejected = File(folder, "${tag.run}-frame${raw.sequence}.json")
                    json
                        .put("captureAcceptance", "REJECTED_GEOMETRY_SNAPSHOT")
                        .put("automatic", tag.json())
                        .put("snapshotDifference", difference)
                    rejected.writeText(json.toString(2))
                    timeline.event(
                        "automatic_capture_rejected",
                        tag.json()
                            .put("frame", raw.sequence)
                            .put("difference", difference)
                            .put("path", "RejectedCaptures/${rejected.name}"),
                    )
                    throw IllegalArgumentException(
                        "Capture frames did not match. Try One check again."
                    )
                }
                json.put("snapshotDifference", difference)
                withTimeout(5_000) { while (!automaticSceneMatches(tag, raw.sequence)) delay(10) }
                require(stage.automatic == tag) { "Automatic scene tag mismatch" }
                json.put(
                    "automatic",
                    tag.json()
                        .put(
                            "markers",
                            if (tag.board) JSONArray() else LabAutoCapture.markersJson(stage),
                        )
                        .put("markerRadiusMetres", LabAutoCapture.markerRadius.toDouble())
                        .put("poseLabelIsPrompt", true),
                )
            }
            val count = mutableUi.value.count + 1
            val folder =
                File(session, "%03d-mode%d-step%d".format(count, capture.mode, request.step + 1))
            val pending = File(folder.path + ".pending")
            check(pending.mkdirs()) { "Cannot create capture directory" }
            writePpm(File(pending, "source.ppm"), capture.source, 1624, 1232)
            writePpm(File(pending, "detector.ppm"), capture.detector, 256, 256)
            writePpm(File(pending, "landmarker.ppm"), capture.model, 256, 256)
            File(pending, "sample.json").writeText(json.toString(2))
            check(pending.renameTo(folder)) { "Cannot finalize capture" }
            synchronized(this@FaceRegistrationLab) {
                val s = mutableUi.value
                mutableUi.value =
                    s.copy(
                        count = count,
                        acceptedCount = s.acceptedCount + if (exposure.stable) 1 else 0,
                        repeatCount = s.repeatCount + if (exposure.stable) 0 else 1,
                        saving = false,
                        message =
                            "Saved %03d. ".format(count) +
                                if (exposure.stable) "Exposure accepted. Ready for next sample."
                                else if (!exposure.covered) "Exposure history incomplete; repeat."
                                else "Head moved at exposure; repeat.",
                    )
            }
            synchronized(this@FaceRegistrationLab) {
                request.automatic?.let { tag ->
                    timeline.event(
                        "automatic_capture_saved",
                        tag.json()
                            .put("frame", raw.sequence)
                            .put("folder", folder.name)
                            .put("exposureStable", exposure.stable),
                    )
                    automaticExport = null
                    automatic.saved(tag, System.nanoTime() * 1e-9)
                    publishAutomatic()
                }
            }
            Log.i(
                FaceLandmarkerRunner.TAG,
                "registration_lab_saved seq=${raw.sequence} mode=${capture.mode} exposure_stable=${exposure.stable} export_stable=${export.stable} path=$folder",
            )
        }

    companion object {
        val MODES =
            listOf(
                "A: Service",
                "B: Aspect only",
                "C: Renderer trial",
                "D: Measured trial",
                "Custom: adjustable",
                "Stereo calibrated",
            )
        val STEPS =
            listOf(
                "Face front - 1 m",
                "Face looks left - 1 m",
                "Face looks right - 1 m",
                "Face front - 2 m",
                "Checkerboard calibration",
            )
        val MESH_STYLES = listOf("Wireframe", "Solid", "Hidden", "Markers")

        private fun floats(values: FloatArray) =
            JSONArray().apply { values.forEach { put(it.toDouble()) } }

        private fun writePpm(path: File, pixels: ByteArray, width: Int, height: Int) {
            require(pixels.size == width * height * 3)
            path.outputStream().use {
                it.write("P6\n$width $height\n255\n".toByteArray(Charsets.US_ASCII))
                it.write(pixels)
            }
        }

        private fun rgbBitmap(pixels: ByteArray, width: Int, height: Int): Bitmap {
            require(pixels.size == width * height * 3)
            val colors =
                IntArray(width * height) { i ->
                    Color.rgb(
                        pixels[i * 3].toInt() and 255,
                        pixels[i * 3 + 1].toInt() and 255,
                        pixels[i * 3 + 2].toInt() and 255,
                    )
                }
            val original = Bitmap.createBitmap(colors, width, height, Bitmap.Config.ARGB_8888)
            return original.copy(Bitmap.Config.ARGB_8888, true).also { original.recycle() }
        }
    }
}
