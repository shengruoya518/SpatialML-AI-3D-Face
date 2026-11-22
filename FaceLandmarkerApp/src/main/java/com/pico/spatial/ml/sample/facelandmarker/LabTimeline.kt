// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.util.Log
import java.io.File
import java.time.Instant
import java.util.Locale
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject

internal data class LabMeshTime(
    val sequence: Int,
    val mode: Int,
    val revision: Int,
    val captureSeconds: Double,
    val readbackSeconds: Double?,
    val uploadNanos: Long,
    val visible: Boolean,
    val hasFace: Boolean,
    val intrinsics: List<Float>,
    val automatic: LabAutoTag? = null,
    val poseCorrection: LabPoseCorrection = LabPoseCorrection(),
    val stabilization: JSONObject? = null,
)

internal data class LabTimelineUi(
    val session: String,
    val tick: Long = 0,
    val elapsedSeconds: Double = 0.0,
    val cameraElapsedSeconds: Double? = null,
    val mesh: LabMeshTime? = null,
    val logging: Boolean = true,
) {
    fun text(): String {
        val camera = cameraElapsedSeconds?.let { String.format(Locale.US, "%.3f", it) } ?: "--"
        val frame = mesh?.let { "F${it.sequence} K${it.revision} M${it.mode}" } ?: "F-- K-- M--"
        val state =
            when {
                !logging -> "LOG ERROR"
                mesh == null -> "NO MESH"
                !mesh.hasFace -> "NO FACE"
                mesh.visible && mesh.automatic?.markers == true -> "MARKED T${mesh.automatic.trial}"
                mesh.visible -> "MESH"
                else -> "HIDDEN"
            }
        return String.format(
            Locale.US,
            "SYNC %s #%06d\nUI %.3f s | CAM %s s\n%s | %s · POS %s",
            session,
            tick,
            elapsedSeconds,
            camera,
            frame,
            state,
            mesh?.poseCorrection?.badge ?: "--",
        )
    }
}

/** Video-readable labels and an offline journal. Upload completion is not display presentation. */
internal class LabTimeline(sessionFolder: File, val originNanos: Long = System.nanoTime()) :
    AutoCloseable {
    val sessionId = sessionFolder.name
    val file = File(sessionFolder, "timeline.jsonl")
    private val mutableUi = MutableStateFlow(LabTimelineUi(sessionId.substringAfterLast('-')))
    val ui = mutableUi.asStateFlow()
    private val queue = Channel<String>(256)
    @Volatile private var failure: String? = null
    private var closed = false
    private var tickId = 0L
    private var mesh: LabMeshTime? = null

    init {
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                check(sessionFolder.isDirectory || sessionFolder.mkdirs()) {
                    "Cannot create timeline directory"
                }
                check(file.createNewFile()) { "Timeline already exists" }
                file.bufferedWriter().use { writer ->
                    for (line in queue) {
                        writer.write(line)
                        writer.newLine()
                        writer.flush()
                    }
                }
            } catch (error: Exception) {
                failure = error.message ?: "Timeline write failed"
                queue.cancel()
                Log.w(FaceLandmarkerRunner.TAG, "registration_lab_timeline_failed", error)
            }
        }
        record(
            JSONObject()
                .put("event", "session")
                .put("schema", 1)
                .put("session", sessionId)
                .put("originNanos", originNanos)
                .put("utcAtStart", Instant.now().toString())
                .put("clock", "System.nanoTime; seconds relative to originNanos")
                .put("uiTickPeriodMillis", 100)
                .put(
                    "timingBoundary",
                    "UI state generation and mesh upload completion; not display presentation",
                )
        )
        tick(originNanos)
    }

    private fun relative(nanos: Long) = (nanos - originNanos) * 1e-9

    private fun meshJson(value: LabMeshTime?): Any =
        value?.let {
            JSONObject()
                .put("frame", it.sequence)
                .put("mode", it.mode)
                .put("revision", it.revision)
                .put("captureSeconds", it.captureSeconds)
                .put("captureRelativeSeconds", it.captureSeconds - originNanos * 1e-9)
                .put("readbackSeconds", it.readbackSeconds ?: JSONObject.NULL)
                .put("uploadNanos", it.uploadNanos)
                .put("uploadRelativeSeconds", relative(it.uploadNanos))
                .put("visible", it.visible)
                .put("hasFace", it.hasFace)
                .put("intrinsics", org.json.JSONArray(it.intrinsics))
                .put("automatic", it.automatic?.json() ?: JSONObject.NULL)
                .put("poseCorrection", it.poseCorrection.json())
                .put("meshStabilization", it.stabilization ?: JSONObject.NULL)
        } ?: JSONObject.NULL

    private fun record(value: JSONObject) {
        if (queue.trySend(value.toString()).isFailure)
            failure = failure ?: "Timeline queue unavailable"
    }

    @Synchronized
    fun event(name: String, details: JSONObject) {
        if (!closed)
            record(
                JSONObject()
                    .put("event", name)
                    .put("monotonicNanos", System.nanoTime())
                    .put("details", details)
            )
    }

    @Synchronized
    fun tick(nowNanos: Long = System.nanoTime()) {
        if (closed) return
        tickId += 1
        val next =
            LabTimelineUi(
                session = mutableUi.value.session,
                tick = tickId,
                elapsedSeconds = relative(nowNanos),
                cameraElapsedSeconds = mesh?.captureSeconds?.minus(originNanos * 1e-9),
                mesh = mesh,
                logging = failure == null,
            )
        record(
            JSONObject()
                .put("event", "ui_tick")
                .put("tick", tickId)
                .put("monotonicNanos", nowNanos)
                .put("relativeSeconds", next.elapsedSeconds)
                .put("mesh", meshJson(mesh))
        )
        mutableUi.value = next.copy(logging = failure == null)
    }

    @Synchronized
    fun meshApplied(
        frame: FaceFrame?,
        visible: Boolean,
        nowNanos: Long = System.nanoTime(),
        stabilization: JSONObject? = null,
    ) {
        if (closed) return
        mesh =
            frame
                ?.takeIf {
                    it.captureSeconds.isFinite() && it.effectiveIntrinsics.all(Float::isFinite)
                }
                ?.labConfiguration
                ?.let {
                    LabMeshTime(
                        frame.sequence,
                        it.mode,
                        it.revision,
                        frame.captureSeconds,
                        frame.readbackSeconds,
                        nowNanos,
                        visible,
                        frame.hasFace,
                        frame.effectiveIntrinsics.toList(),
                        frame.automatic,
                        frame.poseCorrection,
                        stabilization,
                    )
                }
        record(
            JSONObject()
                .put("event", "scene_update_complete")
                .put("monotonicNanos", nowNanos)
                .put("mesh", meshJson(mesh))
        )
        tick(nowNanos)
    }

    @Synchronized
    fun visibilityChanged(visible: Boolean) {
        if (closed || mesh?.visible == visible) return
        mesh = mesh?.copy(visible = visible)
        record(
            JSONObject()
                .put("event", "visibility")
                .put("monotonicNanos", System.nanoTime())
                .put("mesh", meshJson(mesh))
        )
        tick()
    }

    @Synchronized
    fun reference(): JSONObject =
        JSONObject()
            .put("session", sessionId)
            .put("originNanos", originNanos)
            .put("file", file.name)
            .put("tick", tickId)
            .put("mesh", meshJson(mesh))
            .put("logging", failure == null)
            .put("error", failure ?: JSONObject.NULL)

    @Synchronized
    override fun close() {
        if (closed) return
        closed = true
        record(JSONObject().put("event", "close").put("monotonicNanos", System.nanoTime()))
        queue.close() // Drain pending rows on the IO worker; do not cancel it on UI disposal.
    }
}
