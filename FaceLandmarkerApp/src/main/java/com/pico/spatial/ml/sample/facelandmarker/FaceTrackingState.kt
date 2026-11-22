// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

/** A retained measurement, shared by every effect and the independently paced surface uploader. */
internal data class TrackedFace(
    val frame: FaceFrame,
    val generation: Long,
    val localVertices: FloatArray,
    val expressions: FloatArray,
)

/** Brief misses do not revoke a good pose. Only a fresh, advancing measurement extends its life. */
internal class FaceTrackingState {
    private var latest: TrackedFace? = null
    private var generation = 0L

    fun offer(frame: FaceFrame?, now: Double): TrackedFace? {
        val readback = frame?.readbackSeconds ?: return null
        if (!now.isFinite() || !readback.isFinite() || now - readback !in 0.0..HOLD_SECONDS)
            return null
        if (!frame.hasFace || !frame.outputs.pose || !frame.outputs.mesh || !frame.freshCameraFrame)
            return null
        if (!frame.captureSeconds.isFinite() || !frame.trackingIdentity.isFinite()) return null
        val old = latest
        if (
            old != null &&
                (readback <= checkNotNull(old.frame.readbackSeconds) ||
                    frame.captureSeconds <= old.frame.captureSeconds)
        )
            return null
        FaceHelmetPose.decompose(frame.pose)
        val local = FaceOcclusionGeometry.localVertices(frame.vertices, frame.pose)
        if (
            old == null ||
                now - checkNotNull(old.frame.readbackSeconds) > HOLD_SECONDS ||
                frame.trackingIdentity != old.frame.trackingIdentity ||
                frame.labConfiguration != old.frame.labConfiguration ||
                frame.poseCorrection != old.frame.poseCorrection
        )
            generation++
        return TrackedFace(frame, generation, local, frame.blendshapes).also { latest = it }
    }

    fun current(now: Double): TrackedFace? {
        val face = latest ?: return null
        if (
            !now.isFinite() || now - checkNotNull(face.frame.readbackSeconds) !in 0.0..HOLD_SECONDS
        ) {
            clear()
            return null
        }
        return face
    }

    fun clear() {
        latest = null
        generation++
    }

    companion object {
        const val HOLD_SECONDS = .35
    }
}
