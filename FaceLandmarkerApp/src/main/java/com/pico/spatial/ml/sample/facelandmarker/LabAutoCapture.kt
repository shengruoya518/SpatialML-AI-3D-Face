// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.ceil
import kotlin.math.sqrt
import org.json.JSONArray
import org.json.JSONObject

internal data class LabAutoTag(
    val run: String,
    val trial: Int,
    val candidate: String,
    val pose: Int,
    val phase: String,
    val epoch: Int,
    val protocol: String = "intrinsics-v1",
    val poseLabel: String = "",
    val rollOnly: Boolean = false,
    val rollBaseline: List<Float> = emptyList(),
    val boardKind: String = "",
    val boardExposure: Int = 0,
) {
    val board
        get() = boardKind.isNotEmpty()

    val sideReferences
        get() = rollOnly || board

    val markers
        get() = phase == "MARKED"

    fun json(): JSONObject =
        JSONObject()
            .put("run", run)
            .put("trial", trial)
            .put("candidate", candidate)
            .put("pose", pose)
            .put("phase", phase)
            .put("epoch", epoch)
            .put("protocol", protocol)
            .put("poseLabel", poseLabel)
            .put(
                "captureSequence",
                if (board) boardKind else if (rollOnly) LabRollCapture.KIND else "standard",
            )
            .put("board", if (board) LabBoardCapture.metadata(this) else JSONObject.NULL)
            .put("rollBaselineHeadToStage", JSONArray(rollBaseline))
}

internal data class LabAutoUi(
    val active: Boolean = false,
    val run: String = "",
    val phase: String = "IDLE",
    val trial: Int = 0,
    val total: Int = 0,
    val candidate: String = "",
    val pose: Int = 0,
    val saved: Int = 0,
    val orientation: String = "",
    val message: String = "Start Spatial recording, then choose Board check for the short pilot.",
) {
    fun text(): String =
        if (active)
            "AUTO $trial/$total $candidate · $phase\n$message" +
                if (orientation.isEmpty()) "" else "\n$orientation"
        else message

    fun json(): JSONObject =
        JSONObject()
            .put("active", active)
            .put("run", run)
            .put("phase", phase)
            .put("trial", trial)
            .put("total", total)
            .put("candidate", candidate)
            .put("pose", pose)
            .put("saved", saved)
            .put("orientation", orientation)
            .put("message", message)
}

/** Lab-only guard, evaluated on every packet before presentation or capture authorization. */
internal class LabFaceFrameGate {
    private var lastExposure = Double.NEGATIVE_INFINITY

    fun rejection(frame: FaceFrame, now: Double): String? {
        // A wall-clock fallback must never advance the sensor-clock history, even without a face.
        if (now - frame.captureSeconds !in -.1..2.0) return "Waiting for a sensor camera timestamp…"
        val advancing = frame.captureSeconds > lastExposure
        lastExposure = maxOf(lastExposure, frame.captureSeconds)
        if (!frame.hasFace) return null
        return when {
            !advancing -> "Waiting for a face on a new camera exposure…"
            !frame.freshCameraFrame -> "Waiting for a fresh camera exposure…"
            !LabAutoCapture.markerGeometryValid(frame.vertices) ->
                "Waiting for distinct face marker vertices…"
            else -> null
        }
    }
}

/** Pure, bounded sequence. Its owner serializes calls. All time inputs are monotonic seconds. */
internal class LabAutoCapture {
    data class Candidate(val id: String, val focal: Float, val cy: Float) {
        val values
            get() =
                LabIntrinsics.modeC.let {
                    it.copy(fx = it.fx * focal, fy = it.fy * focal, cy = it.cy + cy)
                }
    }

    data class Trial(val pose: Int, val candidate: Candidate)

    var ui = LabAutoUi()
        private set

    var configuration: LabCameraConfiguration? = null
        private set

    var waitingExport = false
        private set

    private var trials = emptyList<Trial>()
    private var index = 0
    private var epoch = 0
    private var phaseSince = 0.0
    private var sceneSince: Double? = null
    private var stableSince: Double? = null
    private var stableVertices: FloatArray? = null
    private var stableFrames = 0
    private var lastExposure = Double.NEGATIVE_INFINITY
    private var sceneSequence = -1
    private var sceneTag: LabAutoTag? = null
    private var timeoutAt = 0.0
    private var geometry = false
    private var rollOnly = false
    private var boardKind = ""
    private var boardExposure = 0
    private var boardAnchor = emptyList<Float>()
    private var rollBaseline = emptyList<Float>()
    private var baselineCandidate = emptyList<Float>()
    private val posePrompts
        get() =
            if (boardKind.isNotEmpty()) LabBoardCapture.prompts(boardKind)
            else if (rollOnly) LabRollCapture.prompts
            else if (geometry) LabProjectionReference.prompts else poses

    val tag: LabAutoTag?
        get() =
            if (ui.active && configuration != null)
                LabAutoTag(
                    ui.run,
                    index + 1,
                    ui.candidate,
                    ui.pose,
                    ui.phase,
                    epoch,
                    if (geometry) LabProjectionReference.PROTOCOL else "intrinsics-v1",
                    posePrompts[ui.pose],
                    rollOnly,
                    rollBaseline,
                    boardKind,
                    boardExposure,
                )
            else null

    fun start(
        run: String,
        original: LabCameraConfiguration,
        single: Boolean,
        now: Double,
        geometry: Boolean = false,
        rollOnly: Boolean = false,
        boardKind: String = "",
    ) {
        check(!ui.active && !waitingExport) { "An automatic capture is already running" }
        require(!rollOnly || !single) { "Roll trial requires all four holds" }
        require(boardKind.isEmpty() || boardKind in LabBoardCapture.kinds)
        require(boardKind.isEmpty() || !rollOnly)
        this.boardKind = boardKind
        boardExposure = 0
        this.geometry = geometry || rollOnly || boardKind.isNotEmpty()
        this.rollOnly = rollOnly
        rollBaseline = emptyList()
        baselineCandidate = emptyList()
        trials =
            if (boardKind.isNotEmpty()) posePrompts.indices.map { Trial(it, candidates.first()) }
            else if (single) listOf(Trial(0, candidates.first()))
            else if (this.geometry) posePrompts.indices.map { Trial(it, candidates.first()) }
            else
                (0..3).flatMap { pose ->
                    val ordered = if (pose % 2 == 0) candidates else candidates.reversed()
                    ordered.map { Trial(pose, it) }
                }
        index = 0
        lastExposure = Double.NEGATIVE_INFINITY
        configuration = original
        ui = LabAutoUi(active = true, run = run, total = trials.size)
        enter("COUNTDOWN", now, "Start Spatial recording. Capture begins in 15 s.")
    }

    fun tick(now: Double) {
        if (!ui.active) return
        if (now > timeoutAt) {
            stop("FAILED", "Capture timed out. Stop recording, then retry the selected test.")
            return
        }
        if (ui.phase == "COUNTDOWN") {
            val remaining = 15 - (now - phaseSince)
            if (remaining > 0)
                ui =
                    ui.copy(
                        message = "Start Spatial recording. Begins in ${ceil(remaining).toInt()} s."
                    )
            else beginTrial(now, true)
        } else if (ui.phase == "POSE" && now - phaseSince >= 8) {
            enter("SETTLE", now, holdPrompt(ui.pose))
        }
    }

    private fun holdPrompt(pose: Int) =
        if (boardKind.isNotEmpty())
            "${posePrompts[pose]} Keep the board fixed; hold your head still."
        else "${posePrompts[pose]}. Keep the face in view. Small movements are okay."

    private fun beginTrial(now: Double, newPose: Boolean) {
        boardExposure = 0
        val trial = trials[index]
        configuration =
            LabCameraConfiguration(
                if (boardKind.isNotEmpty()) 0 else LabCameraProfile.CUSTOM_MODE,
                if (boardKind.isNotEmpty()) checkNotNull(configuration).custom
                else trial.candidate.values,
                checkNotNull(configuration).revision + 1,
            )
        ui =
            ui.copy(
                trial = index + 1,
                candidate = if (boardKind.isNotEmpty()) "BOARD A" else trial.candidate.id,
                pose = trial.pose,
            )
        enter(if (newPose) "POSE" else "SETTLE", now, holdPrompt(trial.pose))
    }

    private fun enter(phase: String, now: Double, message: String) {
        epoch++
        phaseSince = now
        timeoutAt = now + 60
        sceneSince = null
        sceneSequence = -1
        sceneTag = null
        stableSince = null
        stableVertices = null
        boardAnchor = emptyList()
        stableFrames = 0
        waitingExport = false
        ui = ui.copy(phase = phase, message = message)
    }

    fun sceneApplied(tag: LabAutoTag?, sequence: Int, now: Double) {
        if (tag == null || tag != this.tag) return
        sceneTag = tag
        sceneSequence = sequence
        if (sceneSince == null) sceneSince = now
    }

    fun sceneMatches(tag: LabAutoTag, sequence: Int) = sceneTag == tag && sceneSequence == sequence

    /** Called once per completed inference, before publishing its immutable presentation tag. */
    fun frame(frame: FaceFrame?, usable: Boolean, headStable: Boolean, now: Double): LabAutoTag? {
        tick(now)
        if (!ui.active) return null
        if (boardKind.isNotEmpty()) return boardFrame(frame, usable, headStable, now)
        val head = frame?.registrationEvidence?.headToStage
        if (rollOnly) {
            val measured = LabRollCapture.motion(rollBaseline, head)
            ui =
                ui.copy(
                    orientation =
                        measured?.text(ui.pose)
                            ?: if (LabRollCapture.validHead(head))
                                "Hold upright to establish the starting angle."
                            else "Waiting for measured head tracking."
                )
        }
        if (ui.phase in listOf("COUNTDOWN", "POSE") || waitingExport) return null
        // Old/repeated exposures add no evidence and cannot authorize a save. Preserve a valid
        // hold across them, but still reset for head motion, invalid geometry or changed values.
        if (
            frame != null &&
                frame.hasFace &&
                headStable &&
                frame.labConfiguration == configuration &&
                checkNotNull(configuration).custom.matches(frame.effectiveIntrinsics) &&
                markerGeometryValid(frame.vertices) &&
                now >= frame.captureSeconds &&
                (frame.captureSeconds <= lastExposure || now - frame.captureSeconds > .9)
        ) {
            lastExposure = maxOf(lastExposure, frame.captureSeconds)
            return null
        }
        val ready =
            frame != null &&
                frame.hasFace &&
                usable &&
                headStable &&
                frame.labConfiguration == configuration &&
                frame.captureSeconds > lastExposure &&
                now - frame.captureSeconds in 0.0..0.9 &&
                markerGeometryValid(frame.vertices) &&
                checkNotNull(configuration).custom.matches(frame.effectiveIntrinsics)
        if (frame != null && now - frame.captureSeconds in -.1..2.0)
            lastExposure = maxOf(lastExposure, frame.captureSeconds)
        if (!ready) {
            stableSince = null
            stableVertices = null
            stableFrames = 0
            val reason =
                when {
                    frame == null -> "Waiting for capture-time tracking."
                    !frame.hasFace -> "Waiting for a measured face."
                    !headStable -> "Pause briefly for a clear exposure."
                    !markerGeometryValid(frame.vertices) -> "Waiting for distinct face markers."
                    else -> "Waiting for a new frame with matching camera values."
                }
            ui = ui.copy(message = "${posePrompts[ui.pose]}. $reason")
            return null
        }
        if (rollOnly) {
            val reason =
                when {
                    !LabRollCapture.validHead(head) -> "Waiting for measured head tracking."
                    !LabRollCapture.faceClear(checkNotNull(frame)) ->
                        "Centre the whole face and keep about 1 m away; markers need a clear border."
                    else -> null
                }
            var orientationReady = reason == null
            if (orientationReady && rollBaseline.isEmpty()) {
                val change = LabRollCapture.motion(baselineCandidate, head)
                if (
                    change == null ||
                        change.displacement > .015f ||
                        kotlin.math.abs(change.yaw) > 2f ||
                        kotlin.math.abs(change.pitch) > 2f ||
                        kotlin.math.abs(change.roll) > 2f
                ) {
                    baselineCandidate = checkNotNull(head).toList()
                    stableSince = null
                    stableVertices = null
                    stableFrames = 0
                }
            } else if (orientationReady) {
                orientationReady = LabRollCapture.motion(rollBaseline, head)?.ready(ui.pose) == true
            }
            if (!orientationReady) {
                stableSince = null
                stableVertices = null
                stableFrames = 0
                if (rollBaseline.isEmpty()) baselineCandidate = emptyList()
                ui =
                    ui.copy(
                        message =
                            "${posePrompts[ui.pose]} " +
                                (reason ?: "Match the roll target; keep turn and nod within 5 deg.")
                    )
                return null
            }
        }
        val vertices = checkNotNull(frame).vertices
        val anchor = stableVertices
        val moved =
            anchor != null &&
                markerIds.any { id ->
                    sqrt(
                        (0..2).sumOf { c ->
                            val d = (vertices[id * 3 + c] - anchor[id * 3 + c]).toDouble()
                            d * d
                        }
                    ) > .012
                }
        if (stableSince == null || moved) {
            stableSince = now
            stableVertices = vertices
            stableFrames = 0
        }
        // Small natural drift is measured between usable exposures, rather than accumulating
        // against the first point forever. Large steps still restart the brief capture window.
        stableVertices = vertices
        stableFrames++
        ui = ui.copy(message = "${posePrompts[ui.pose]}. Stay relaxed — capturing automatically.")
        if (stableFrames < 3 || now - checkNotNull(stableSince) < .8) return null
        if (ui.phase == "SETTLE") {
            if (rollOnly && rollBaseline.isEmpty()) {
                rollBaseline = baselineCandidate.toList()
                check(rollBaseline.size == 16)
            }
            enter("CLEAN_BEFORE", now, "${posePrompts[ui.pose]}. Stay relaxed.")
            return null
        }
        val shown = sceneSince ?: return null
        if (now - shown < if (ui.phase == "MARKED") 3.0 else 2.0) return null
        waitingExport = true
        ui = ui.copy(message = "${posePrompts[ui.pose]}. Saving this view automatically.")
        return tag
    }

    private fun boardFrame(
        frame: FaceFrame?,
        usable: Boolean,
        headStable: Boolean,
        now: Double,
    ): LabAutoTag? {
        if (ui.phase in listOf("COUNTDOWN", "POSE") || waitingExport) return null
        val head = frame?.registrationEvidence?.headToStage
        val ready =
            frame != null &&
                usable &&
                headStable &&
                frame.labConfiguration == configuration &&
                frame.labConfiguration?.mode == 0 &&
                !frame.poseCorrection.enabled &&
                frame.freshCameraFrame &&
                now - frame.captureSeconds in 0.0..0.9 &&
                LabRollCapture.validHead(head)
        if (ready && checkNotNull(frame).captureSeconds <= lastExposure) return null
        if (frame != null && now - frame.captureSeconds in -.1..2.0)
            lastExposure = maxOf(lastExposure, frame.captureSeconds)
        if (!ready) {
            stableSince = null
            boardAnchor = emptyList()
            stableFrames = 0
            ui =
                ui.copy(
                    message =
                        holdPrompt(ui.pose) + " Waiting for a fresh frame and still head tracking."
                )
            return null
        }
        if (stableSince == null || !LabBoardCapture.stationary(boardAnchor, head)) {
            stableSince = now
            boardAnchor = checkNotNull(head).toList()
            stableFrames = 0
        }
        stableFrames++
        ui =
            ui.copy(
                message = holdPrompt(ui.pose) + " Board visibility will be checked after export."
            )
        if (stableFrames < 3 || now - checkNotNull(stableSince) < .8) return null
        if (ui.phase == "SETTLE") {
            enter(
                if (boardKind == LabBoardCapture.VIEWS) "SOURCE" else "MARKED",
                now,
                holdPrompt(ui.pose),
            )
            return null
        }
        val shown = sceneSince ?: return null
        if (now - shown < 2) return null
        waitingExport = true
        ui = ui.copy(message = holdPrompt(ui.pose) + " Saving exposure ${boardExposure + 1}.")
        return tag
    }

    fun saved(tag: LabAutoTag, now: Double) {
        if (!ui.active || tag != this.tag || !waitingExport) return
        ui = ui.copy(saved = ui.saved + 1)
        if (boardKind.isNotEmpty()) {
            boardExposure++
            if (boardKind != LabBoardCapture.VIEWS && boardExposure < 3) {
                enter("MARKED", now, holdPrompt(ui.pose))
            } else {
                index++
                if (index == trials.size)
                    stop(
                        "DONE",
                        "Board capture complete. Stop recording. Board visibility still needs offline checking.",
                    )
                else beginTrial(now, true)
            }
            return
        }
        when (ui.phase) {
            "CLEAN_BEFORE" ->
                enter("MARKED", now, "${posePrompts[ui.pose]}. Markers are visible. Stay relaxed.")
            "MARKED" ->
                enter(
                    "CLEAN_AFTER",
                    now,
                    "${posePrompts[ui.pose]}. Keep the face in view for the final clear view.",
                )
            "CLEAN_AFTER" -> {
                val oldPose = ui.pose
                index++
                if (index == trials.size)
                    stop(
                        "DONE",
                        "Capture complete. Stop recording. Evidence is saved on this headset.",
                    )
                else beginTrial(now, trials[index].pose != oldPose)
            }
        }
    }

    fun stop(
        phase: String = "CANCELLED",
        message: String = "Capture cancelled. Starting values restored.",
    ) {
        waitingExport = false
        configuration = null
        ui = ui.copy(active = false, phase = phase, message = message)
    }

    companion object {
        val markerIds = listOf(33, 133, 362, 263, 1, 61, 291, 152)
        const val markerRadius = .003f

        /** Selected anatomical points must be distinct; distances are invariant under rebasing. */
        fun markerGeometryValid(vertices: FloatArray): Boolean =
            vertices.size == 478 * 3 &&
                vertices.all(Float::isFinite) &&
                markerIds.indices.all { a ->
                    (a + 1 until markerIds.size).all { b ->
                        (0..2).sumOf { c ->
                            val d =
                                (vertices[markerIds[a] * 3 + c] - vertices[markerIds[b] * 3 + c])
                                    .toDouble()
                            d * d
                        } > .001 * .001
                    }
                }

        val markerTriangles: List<Int> =
            markerIds.indices.flatMap { n ->
                listOf(4, 0, 2, 4, 2, 1, 4, 1, 3, 4, 3, 0, 5, 2, 0, 5, 1, 2, 5, 3, 1, 5, 0, 3).map {
                    it + n * 6
                }
            }

        fun markerVertices(stage: FloatArray): FloatArray {
            require(markerGeometryValid(stage)) { "Face marker vertices are invalid or collapsed" }
            val axes = listOf(0 to 1f, 0 to -1f, 1 to 1f, 1 to -1f, 2 to 1f, 2 to -1f)
            return FloatArray(markerIds.size * 18) { i ->
                val id = markerIds[i / 18]
                val local = i % 18
                val axis = axes[local / 3]
                stage[id * 3 + local % 3] +
                    if (local % 3 == axis.first) axis.second * markerRadius else 0f
            }
        }

        val poses =
            listOf(
                "Face forward, about 1 m away",
                "Face turned left, about 1 m away",
                "Face turned right, about 1 m away",
                "Face forward, about 2 m away",
            )
        val candidates =
            listOf(
                Candidate("C", 1f, 0f),
                Candidate("F98", .98f, 0f),
                Candidate("F97", .97f, 0f),
                Candidate("Y40", 1f, -40f),
                Candidate("Y75", 1f, -75f),
                Candidate("Y110", 1f, -110f),
                Candidate("C-repeat", 1f, 0f),
            )

        fun markersJson(frame: FaceFrame): JSONArray =
            JSONArray().apply {
                val vertices = frame.vertices
                markerIds.forEach { id ->
                    put(
                        JSONObject()
                            .put("landmark", id)
                            .put(
                                "stageMetres",
                                JSONArray((0..2).map { vertices[id * 3 + it].toDouble() }),
                            )
                    )
                }
            }
    }
}
