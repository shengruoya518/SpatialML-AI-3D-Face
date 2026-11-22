// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

/** All matrices are row-major and multiply column vectors; no handedness change is needed. */
internal object StageRegistration {
    fun serviceToStage(
        headToStage: FloatArray,
        leftCameraToHead: FloatArray,
        leftCameraToService: FloatArray,
    ): FloatArray =
        multiply(multiply(headToStage, leftCameraToHead), inverseRigid(leftCameraToService))

    fun multiply(a: FloatArray, b: FloatArray): FloatArray =
        FloatArray(16) { index ->
            val row = index / 4
            val column = index % 4
            (0..3).sumOf { (a[row * 4 + it] * b[it * 4 + column]).toDouble() }.toFloat()
        }

    fun transformVertices(matrix: FloatArray, vertices: FloatArray): FloatArray =
        FloatArray(vertices.size) { index ->
            val row = index % 3
            val point = index / 3 * 3
            matrix[row * 4 + 3] +
                matrix[row * 4] * vertices[point] +
                matrix[row * 4 + 1] * vertices[point + 1] +
                matrix[row * 4 + 2] * vertices[point + 2]
        }

    fun inverseRigid(matrix: FloatArray): FloatArray {
        require(matrix.size == 16 && matrix.all(Float::isFinite))
        for (r in 0..2) for (c in 0..2) {
            val dot = (0..2).sumOf { (matrix[it * 4 + r] * matrix[it * 4 + c]).toDouble() }
            require(kotlin.math.abs(dot - if (r == c) 1.0 else 0.0) < .001) {
                "Capture camera matrix is not a rigid transform"
            }
        }
        val result = FloatArray(16)
        for (r in 0..2) {
            for (c in 0..2) result[r * 4 + c] = matrix[c * 4 + r]
            result[r * 4 + 3] =
                -(0..2).sumOf { (result[r * 4 + it] * matrix[it * 4 + 3]).toDouble() }.toFloat()
        }
        result[15] = 1f
        return result
    }
}
