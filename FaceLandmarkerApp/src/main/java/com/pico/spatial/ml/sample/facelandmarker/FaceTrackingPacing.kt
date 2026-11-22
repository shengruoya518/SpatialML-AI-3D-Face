// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

/** Scheduling only: every profile retains one in-flight frame and terminal publication checks. */
internal enum class FaceTrackingPacing(val idleMillis: Long, val pollMillis: Long) {
    LEGACY(10, 2),
    FAST(0, 2),
    EAGER(0, 1);

    companion object {
        fun parse(value: String?): FaceTrackingPacing =
            entries.firstOrNull { it.name.equals(value, ignoreCase = true) }
                ?: throw IllegalArgumentException("Expected latency profile legacy, fast or eager")
    }
}
