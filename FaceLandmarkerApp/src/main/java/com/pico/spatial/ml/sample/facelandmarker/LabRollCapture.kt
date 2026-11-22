// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import java.util.Locale
import kotlin.math.abs
import kotlin.math.asin
import kotlin.math.atan2
import kotlin.math.sqrt
import org.json.JSONArray
import org.json.JSONObject

/** Measured capture-head motion; prompt names never stand in for an actual rotation. */
internal object LabRollCapture {
    const val KIND = "roll-only-v1"
    const val LAYOUT = "roll-side-columns-v1"
    val targets = listOf(0f, 15f, -15f, 0f)
    val prompts =
        listOf(
            "Head upright. Face the subject at about 1 m. Hold still to set the baseline.",
            "LEFT ear toward LEFT shoulder, about 15 deg. Keep your nose pointed at the face.",
            "RIGHT ear toward RIGHT shoulder, about 15 deg. Keep your nose pointed at the face.",
            "Return your head upright to the starting position. Keep facing the subject.",
        )

    data class Motion(val yaw: Float, val pitch: Float, val roll: Float, val displacement: Float) {
        fun ready(pose: Int) = abs(roll - targets[pose]) <= 3f && abs(yaw) <= 5f && abs(pitch) <= 5f

        fun text(pose: Int): String =
            String.format(
                Locale.US,
                "Roll %+.1f / target %+.0f deg | turn %+.1f | nod %+.1f",
                roll,
                targets[pose],
                yaw,
                pitch,
            )

        fun json(pose: Int) =
            JSONObject()
                .put("yawDegrees", yaw.toDouble())
                .put("pitchDegrees", pitch.toDouble())
                .put("rollDegrees", roll.toDouble())
                .put("headDisplacementMetres", displacement.toDouble())
                .put("targetRollDegrees", targets[pose].toDouble())
                .put("orientationAccepted", ready(pose))
    }

    fun validHead(head: FloatArray?): Boolean {
        if (head == null || head.size != 16 || !head.all(Float::isFinite)) return false
        if ((12..15).any { abs(head[it] - if (it == 15) 1f else 0f) > .001f }) return false
        for (r in 0..2) for (c in 0..2) {
            val dot = (0..2).sumOf { (head[it * 4 + r] * head[it * 4 + c]).toDouble() }
            if (abs(dot - if (r == c) 1.0 else 0.0) > .001) return false
        }
        val determinant =
            head[0] * (head[5] * head[10] - head[6] * head[9]) -
                head[1] * (head[4] * head[10] - head[6] * head[8]) +
                head[2] * (head[4] * head[9] - head[5] * head[8])
        return abs(determinant - 1f) < .001f
    }

    fun motion(baseline: List<Float>, head: FloatArray?): Motion? {
        if (baseline.size != 16 || !validHead(head) || !validHead(baseline.toFloatArray()))
            return null
        val h = checkNotNull(head)
        // R_relative = R_baseline^T R_capture; intrinsic YXZ (yaw, pitch, roll).
        fun r(row: Int, column: Int) =
            (0..2).sumOf { (baseline[it * 4 + row] * h[it * 4 + column]).toDouble() }
        fun degrees(radians: Double) = Math.toDegrees(radians).toFloat()
        return Motion(
            degrees(atan2(r(0, 2), r(2, 2))),
            degrees(asin((-r(1, 2)).coerceIn(-1.0, 1.0))),
            degrees(atan2(r(1, 0), r(1, 1))),
            sqrt(
                    (0..2).sumOf {
                        val d = h[it * 4 + 3] - baseline[it * 4 + 3]
                        (d * d).toDouble()
                    }
                )
                .toFloat(),
        )
    }

    /** All reconstructed vertices must fit the independently defined central angular region. */
    fun faceClear(frame: FaceFrame): Boolean {
        val head = frame.registrationEvidence?.headToStage ?: return false
        if (!validHead(head) || !LabAutoCapture.markerGeometryValid(frame.vertices)) return false
        val vertices = frame.vertices
        return (0 until vertices.size / 3).all { point ->
            fun local(axis: Int) =
                (0..2).sumOf { r ->
                    (head[r * 4 + axis] * (vertices[point * 3 + r] - head[r * 4 + 3])).toDouble()
                }
            val depth = -local(2)
            depth >= .45 && abs(local(0) / depth) <= .25 && local(1) / depth in -0.30..0.24
        }
    }

    fun evidence(tag: LabAutoTag, head: FloatArray?): JSONObject? {
        if (!tag.rollOnly) return null
        return JSONObject()
            .put("sequence", KIND)
            .put("baselineHeadToStage", JSONArray(tag.rollBaseline))
            .put("baselineConvention", "first stable upright hold; capture-head-to-Stage")
            .put(
                "angleConvention",
                "inverse(baseline) * capture; YXZ yaw/pitch/roll; left ear down is positive roll",
            )
            .put("rollToleranceDegrees", 3)
            .put("yawPitchLimitDegrees", 5)
            .put("measured", motion(tag.rollBaseline, head)?.json(tag.pose) ?: JSONObject.NULL)
    }
}
