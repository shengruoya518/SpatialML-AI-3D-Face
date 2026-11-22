// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.min
import kotlin.math.tan

/** Matches Unity's explicit Swan experiment, never an automatically applied calibration. */
internal object LabCameraProfile {
    const val MODE_COUNT = 6
    const val CUSTOM_MODE = 4
    const val STEREO_MODE = 5
    const val MEASURED_PROFILE = "checkerboard-2026-10-28-pinhole-exploratory"
    val measuredSourceIntrinsics: FloatArray
        get() =
            floatArrayOf(2642.704699f, 0f, 1672.376919f, 0f, 2036.955265f, 1230.337555f, 0f, 0f, 1f)

    const val FINGERPRINT =
        "Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys"
    val identity: FloatArray
        get() = floatArrayOf(1f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f)

    val preservedImageAffine: FloatArray
        get() = floatArrayOf(.7673501372337341f, 0f, 377.70703125f, 0f, 1f, 0f, 0f, 0f, 1f)

    fun configuration(mode: Int, fingerprint: String): Pair<FloatArray, FloatArray> {
        require(mode in 0 until MODE_COUNT)
        if (mode == 0) return identity to FloatArray(9)
        require(fingerprint == FINGERPRINT) {
            "B/C/D/custom trials are only defined for Swan ROM 20261014024400"
        }
        if (mode == CUSTOM_MODE) return preservedImageAffine to LabIntrinsics.modeC.matrix()
        if (mode == STEREO_MODE)
            return preservedImageAffine to LabStereoCalibration.sourceIntrinsics
        val width = SpatialMLGraphSession.WIDTH.toDouble()
        val height = SpatialMLGraphSession.HEIGHT.toDouble()
        require(width == 3248.0 && height == 2464.0)
        val radians = Math.PI / 180
        val halfFov = 70.400002 * .5
        val fx = width / (tan((halfFov - 5) * radians) + tan((halfFov + 5) * radians))
        val fy = height / (2 * tan(halfFov * radians))
        val cx = (width - 1) * .5
        val cy = (height - 1) * .5
        val focal = min(fx, fy)
        val sx = focal / fx
        val sy = focal / fy
        val affine = doubleArrayOf(sx, 0.0, cx * (1 - sx), 0.0, sy, cy * (1 - sy), 0.0, 0.0, 1.0)
        val trial = doubleArrayOf(focal, 0.0, cx, 0.0, focal, cy, 0.0, 0.0, 1.0)
        if (mode == 3) {
            // Preserve the exact float32 B affine used by the returned captures.
            return preservedImageAffine to measuredSourceIntrinsics
        }
        return affine.map(Double::toFloat).toFloatArray() to
            trial.map(Double::toFloat).toFloatArray()
    }
}
