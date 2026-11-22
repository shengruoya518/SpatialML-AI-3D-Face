// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.acos
import kotlin.math.sqrt

/** Motion at callback-arrival times. Coverage requires samples bracketing both window ends. */
internal data class LabMotion(val covered: Boolean, val metres: Double, val degrees: Double) {
    val stable: Boolean
        get() = covered && metres < .01 && degrees < 1

    companion object {
        fun measure(
            samples: List<Pair<Double, FloatArray>>,
            from: Double,
            until: Double,
        ): LabMotion {
            val first = samples.indexOfLast { it.first <= from }
            val last = samples.indexOfFirst { it.first >= until }
            if (first < 0 || last < first) return LabMotion(false, 0.0, 0.0)
            val window = samples.subList(first, last + 1)
            val covered = window.zipWithNext().all { it.second.first - it.first.first <= .1 }
            val reference = window.first().second
            var translation = 0.0
            var angle = 0.0
            for ((_, sample) in window) {
                translation =
                    maxOf(
                        translation,
                        sqrt(
                            listOf(3, 7, 11).sumOf {
                                val d = (sample[it] - reference[it]).toDouble()
                                d * d
                            }
                        ),
                    )
                val trace =
                    (0..2).sumOf { c ->
                        (0..2).sumOf { r -> sample[r * 4 + c].toDouble() * reference[r * 4 + c] }
                    }
                angle = maxOf(angle, Math.toDegrees(acos(((trace - 1) / 2).coerceIn(-1.0, 1.0))))
            }
            return LabMotion(covered, translation, angle)
        }
    }
}
