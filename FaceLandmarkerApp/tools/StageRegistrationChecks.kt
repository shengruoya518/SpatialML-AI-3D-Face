package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

/** Executable host checks for the production StageRegistration math, independent of Android. */
fun main() {
    fun pose(yaw: Float, pitch: Float, x: Float, y: Float, z: Float): FloatArray {
        val cy = cos(yaw)
        val sy = sin(yaw)
        val cx = cos(pitch)
        val sx = sin(pitch)
        return floatArrayOf(
            cy,
            sy * sx,
            sy * cx,
            x,
            0f,
            cx,
            -sx,
            y,
            -sy,
            cy * sx,
            cy * cx,
            z,
            0f,
            0f,
            0f,
            1f,
        )
    }
    // Known service->Stage registration with the meter-scale translation and yaw absent before.
    val expected = pose(.7f, -.2f, -1.1f, 1.3f, .6f)
    val optical = pose(.012f, -.018f, -.033f, .040f, -.035f)
    var maximum = 0f
    for (i in 0 until 40) {
        val headInService = pose(i * .025f, i * -.011f, i * .02f, .1f + i * .004f, -.1f)
        val headInStage = StageRegistration.multiply(expected, headInService)
        val cameraInService = StageRegistration.multiply(headInService, optical)
        val actual = StageRegistration.serviceToStage(headInStage, optical, cameraInService)
        for (k in actual.indices) maximum = maxOf(maximum, abs(actual[k] - expected[k]))
        // A fixed point and a small 3D face must stay in Stage as the headset pose changes.
        val vertices = floatArrayOf(.2f, .3f, -1.5f, .24f, .37f, -1.48f, .18f, .35f, -1.52f)
        val result = StageRegistration.transformVertices(actual, vertices)
        val target = StageRegistration.transformVertices(expected, vertices)
        for (k in result.indices) maximum = maxOf(maximum, abs(result[k] - target[k]))
    }
    check(maximum < 1e-5f) { "Stage registration error: $maximum m" }
    println(
        "PASS: production Kotlin registration preserves optical extrinsics, removes meter-scale origin/yaw errors, and stays invariant across 40 head poses; max error $maximum"
    )
}
