// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

/** Tongue evidence must persist; jaw opening alone never starts fire. */
internal class FaceDragonFireGate {
    private var generation = -1L
    private var capture = Double.NEGATIVE_INFINITY
    private var evidenceAt = Double.NEGATIVE_INFINITY
    private var pendingSince = Double.NaN
    private var samples = 0
    private var active = false

    fun reset() {
        capture = Double.NEGATIVE_INFINITY
        evidenceAt = Double.NEGATIVE_INFINITY
        pendingSince = Double.NaN
        samples = 0
        active = false
    }

    fun update(
        jaw: Float,
        tongue: Float?,
        captureSeconds: Double,
        readbackSeconds: Double,
        track: Long,
    ) {
        if (generation != track) {
            reset()
            generation = track
        }
        if (!captureSeconds.isFinite() || !readbackSeconds.isFinite() || captureSeconds <= capture)
            return
        capture = captureSeconds
        evidenceAt = readbackSeconds
        if (
            !jaw.isFinite() || jaw < .08f || tongue == null || !tongue.isFinite() || tongue < .30f
        ) {
            active = false
            pendingSince = Double.NaN
            samples = 0
            return
        }
        if (tongue >= .55f) {
            if (!pendingSince.isFinite()) pendingSince = captureSeconds
            samples++
            if (samples >= 3 && captureSeconds - pendingSince >= .10) active = true
        } else if (!active) {
            pendingSince = Double.NaN
            samples = 0
        }
    }

    fun burning(now: Double): Boolean {
        if (!now.isFinite() || now - evidenceAt !in 0.0..0.20) {
            active = false
            pendingSince = Double.NaN
            samples = 0
        }
        return active
    }
}
