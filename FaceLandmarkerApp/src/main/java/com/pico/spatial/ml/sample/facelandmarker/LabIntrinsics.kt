// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

/** Geometry intrinsics in the lab's 3248 x 2464 virtual image, after the fixed C image affine. */
internal data class LabIntrinsics(val fx: Float, val fy: Float, val cx: Float, val cy: Float) {
    init {
        require(fx.isFinite() && fy.isFinite() && cx.isFinite() && cy.isFinite())
        require(fx in 250f..6000f && fy in 250f..6000f)
        require(cx in 0f..3248f && cy in 0f..2464f)
    }

    fun matrix(): FloatArray = floatArrayOf(fx, 0f, cx, 0f, fy, cy, 0f, 0f, 1f)

    fun value(parameter: IntrinsicParameter): Float =
        when (parameter) {
            IntrinsicParameter.FX -> fx
            IntrinsicParameter.FY -> fy
            IntrinsicParameter.CX -> cx
            IntrinsicParameter.CY -> cy
        }

    fun adjusted(parameter: IntrinsicParameter, value: Float): LabIntrinsics {
        require(value.isFinite())
        val bounded = value.coerceIn(parameter.range)
        return when (parameter) {
            IntrinsicParameter.FX -> copy(fx = bounded)
            IntrinsicParameter.FY -> copy(fy = bounded)
            IntrinsicParameter.CX -> copy(cx = bounded)
            IntrinsicParameter.CY -> copy(cy = bounded)
        }
    }

    fun matches(matrix: FloatArray): Boolean =
        matrix.size == 9 &&
            matrix.all(Float::isFinite) &&
            matrix().zip(matrix).all { (expected, actual) ->
                kotlin.math.abs(expected - actual) < .001f
            }

    companion object {
        val modeC = LabIntrinsics(1746.4712668f, 1746.4712668f, 1623.5f, 1231.5f)
    }
}

internal enum class IntrinsicParameter(
    val label: String,
    val range: ClosedFloatingPointRange<Float>,
) {
    FX("fx", 250f..6000f),
    FY("fy", 250f..6000f),
    CX("cx", 0f..3248f),
    CY("cy", 0f..2464f),
}

/** Immutable frame-boundary request. Revision also distinguishes an edit away and back. */
internal data class LabCameraConfiguration(
    val mode: Int,
    val custom: LabIntrinsics,
    val revision: Int,
)
