// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.exp
import kotlin.math.max

/**
 * An independent neutral mask with named expression targets, driven by the model's coefficients.
 */
internal class FaceMaskGeometry(canonical: FloatArray, names: List<String>) {
    val neutral = FloatArray(468 * 3) { canonical[it / 3 * 4 + it % 3] * .01f }
    private val channels = names.withIndex().associate { it.value to it.index }

    fun coefficient(weights: FloatArray, name: String): Float =
        channels[name]?.let { weights.getOrNull(it) }?.takeIf { it.isFinite() }?.coerceIn(0f, 1f)
            ?: 0f

    private val targetNames =
        listOf(
            "jawOpen",
            "mouthSmileRight",
            "mouthSmileLeft",
            "eyeBlinkRight",
            "eyeBlinkLeft",
            "browInnerUp",
            "browOuterUpRight",
            "browOuterUpLeft",
            "browDownRight",
            "browDownLeft",
        )
    // Precompute the spatial targets once; per-frame deformation is a weighted sum only.
    private val targets =
        targetNames.map { name ->
            FloatArray(neutral.size) { index ->
                val point = index / 3
                val axis = index % 3
                val x = neutral[point * 3]
                val y = neutral[point * 3 + 1]
                when {
                    name == "jawOpen" -> {
                        val lower = ((-.018f - y) / .075f).coerceIn(0f, 1f)
                        when (axis) {
                            1 -> -.035f * lower
                            2 -> .008f * lower
                            else -> 0f
                        }
                    }
                    name.startsWith("mouthSmile") -> {
                        val influence =
                            influence(x, y, if (name.endsWith("Right")) 61 else 291, .025f)
                        when (axis) {
                            0 -> (if (x < 0) -1 else 1) * .009f * influence
                            1 -> .012f * influence
                            else -> 0f
                        }
                    }
                    name.startsWith("eyeBlink") && axis == 1 -> {
                        val upper = if (name.endsWith("Right")) 159 else 386
                        val lower = if (name.endsWith("Right")) 145 else 374
                        val middle = (neutral[upper * 3 + 1] + neutral[lower * 3 + 1]) * .5f
                        -(y - middle) * influence(x, y, upper, .018f)
                    }
                    name.startsWith("brow") && axis == 1 -> {
                        val influence =
                            when {
                                name == "browInnerUp" ->
                                    influence(x, y, 105, .023f) + influence(x, y, 334, .023f)
                                else ->
                                    influence(x, y, if (name.endsWith("Right")) 105 else 334, .023f)
                            }
                        .009f * (if (name.startsWith("browDown")) -1 else 1) * influence
                    }
                    else -> 0f
                }
            }
        }

    fun deform(weights: FloatArray): FloatArray {
        val result = neutral.copyOf()
        for (index in result.indices) if (index % 3 == 2) result[index] += .004f
        for (target in targetNames.indices) {
            val name = targetNames[target]
            var weight = coefficient(weights, name)
            if (name == "jawOpen") weight *= 1f - coefficient(weights, "mouthClose")
            if (weight == 0f) continue
            for (index in result.indices) result[index] += weight * targets[target][index]
        }
        return result
    }

    private fun influence(x: Float, y: Float, point: Int, radius: Float): Float {
        val dx = x - neutral[point * 3]
        val dy = y - neutral[point * 3 + 1]
        return exp(-(dx * dx + dy * dy) / max(1e-8f, radius * radius))
    }
}
