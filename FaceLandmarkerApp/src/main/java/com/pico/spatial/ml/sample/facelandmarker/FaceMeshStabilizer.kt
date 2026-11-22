// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Presentation-only adaptive low-pass, after capture-time registration into Stage metres. One blend
 * weight for the entire mesh avoids giving neighbouring vertices different delays. Never feed the
 * result back into inference, pose fitting, calibration or diagnostic exports.
 */
internal class FaceMeshStabilizer {
    data class Result(
        val vertices: FloatArray,
        val alpha: Float,
        val cutoffHz: Double,
        val correctionRmsMetres: Double,
        val reason: String,
    )

    private var previousRaw: FloatArray? = null
    private var filtered: FloatArray? = null
    private var velocity: FloatArray? = null
    private var time = Double.NaN
    private var identity = Float.NaN
    private var context: Any? = null

    fun reset() {
        previousRaw = null
        filtered = null
        velocity = null
        time = Double.NaN
        context = null
    }

    fun update(
        vertices: FloatArray,
        captureSeconds: Double,
        trackingIdentity: Float,
        configuration: Any,
    ): Result {
        require(vertices.isNotEmpty() && vertices.size % 3 == 0 && vertices.all(Float::isFinite))
        require(captureSeconds.isFinite() && trackingIdentity.isFinite())
        val raw = previousRaw
        val old = filtered
        val dt = captureSeconds - time
        val reason =
            when {
                raw == null || old == null -> "first_frame"
                raw.size != vertices.size -> "topology"
                context != configuration -> "configuration"
                identity != trackingIdentity -> "identity"
                dt <= 0 || dt > MAX_GAP_SECONDS -> "capture_gap"
                rmsDifference(raw, vertices) > RESET_DISTANCE_METRES -> "large_jump"
                else -> null
            }
        if (reason != null) {
            previousRaw = vertices.copyOf()
            filtered = vertices.copyOf()
            velocity = FloatArray(vertices.size)
            time = captureSeconds
            identity = trackingIdentity
            context = configuration
            return Result(vertices.copyOf(), 1f, 0.0, 0.0, reason)
        }
        val derivativeAlpha = alpha(DERIVATIVE_CUTOFF_HZ, dt)
        val speeds = DoubleArray(vertices.size / 3)
        val v = checkNotNull(velocity)
        for (i in vertices.indices) {
            val measured = (vertices[i] - checkNotNull(raw)[i]) / dt
            v[i] += (derivativeAlpha * (measured - v[i])).toFloat()
            speeds[i / 3] += v[i].toDouble() * v[i]
        }
        speeds.sort()
        // A high percentile also responds to local mouth/eyebrow movement without one noisy
        // landmark opening the filter for the whole mesh. Units remain metres/second.
        val speed = sqrt(speeds[((speeds.size - 1) * .95).toInt()])
        val cutoff = (MIN_CUTOFF_HZ + SPEED_COEFFICIENT * speed).coerceAtMost(MAX_CUTOFF_HZ)
        var weight = alpha(cutoff, dt)
        var maxDifference = 0.0
        for (point in speeds.indices) {
            var squared = 0.0
            for (axis in 0..2) {
                val i = point * 3 + axis
                val delta = vertices[i].toDouble() - checkNotNull(old)[i]
                squared += delta * delta
            }
            maxDifference = max(maxDifference, sqrt(squared))
        }
        // Bound lag during an abrupt turn/expression as well as releasing for sustained motion.
        if (maxDifference > MAX_CORRECTION_METRES)
            weight = max(weight, 1.0 - MAX_CORRECTION_METRES / maxDifference)
        val result =
            FloatArray(vertices.size) { i ->
                val previous = checkNotNull(old)[i]
                previous + (weight * (vertices[i] - previous)).toFloat()
            }
        previousRaw = vertices.copyOf()
        filtered = result.copyOf()
        time = captureSeconds
        return Result(result, weight.toFloat(), cutoff, rmsDifference(result, vertices), "filtered")
    }

    private fun alpha(cutoff: Double, dt: Double) = 1.0 - exp(-2.0 * PI * cutoff * dt)

    private fun rmsDifference(a: FloatArray, b: FloatArray): Double =
        sqrt(a.indices.sumOf { i -> (a[i].toDouble() - b[i]).let { it * it } } / (a.size / 3))

    companion object {
        const val MIN_CUTOFF_HZ = 1.5
        const val MAX_CUTOFF_HZ = 20.0
        const val DERIVATIVE_CUTOFF_HZ = 1.0
        const val SPEED_COEFFICIENT = 20.0
        const val MAX_GAP_SECONDS = .25
        const val RESET_DISTANCE_METRES = .15
        const val MAX_CORRECTION_METRES = .02
    }
}
