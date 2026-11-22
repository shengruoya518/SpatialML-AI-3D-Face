// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import org.json.JSONArray
import org.json.JSONObject

/** One global read contains nested producer, fit and mesh snapshots from one submitted frame. */
internal class LabGeometryProbe(values: FloatArray, sequence: Int, mode: Int) {
    val mesh = unpack(values, meshFields)
    val fit = unpack(checkNotNull(mesh["upstream"]), fitFields)
    val producer = unpack(checkNotNull(fit["upstream"]), producerFields)

    init {
        require(values.all(Float::isFinite)) { "Non-finite lab geometry snapshot" }
        for (snapshot in listOf(producer, fit, mesh)) {
            require(snapshot.getValue("command")[0] == sequence.toFloat()) {
                "Geometry snapshot sequence mismatch; repeat"
            }
            require(
                snapshot.getValue("captureFrame").contentEquals(producer.getValue("captureFrame"))
            ) {
                "Geometry snapshot camera timestamp mismatch; repeat"
            }
        }
        require(producer.getValue("mode")[0] == mode.toFloat()) { "Geometry mode mismatch" }
        require(mesh.getValue("result")[0] == sequence.toFloat()) { "Geometry result is stale" }
    }

    /** Exact finite numeric equality. Signed zero has the same geometry and packet meaning. */
    fun resultMatches(result: FloatArray): Boolean {
        val captured = mesh.getValue("result")
        return captured.size == result.size &&
            captured.indices.all { sameFiniteValue(captured[it], result[it]) }
    }

    fun resultDifference(result: FloatArray): JSONObject {
        val captured = mesh.getValue("result")
        val compared = minOf(captured.size, result.size)
        val changed = (0 until compared).filter { !sameFiniteValue(captured[it], result[it]) }
        val signedZeros =
            (0 until compared).filter {
                captured[it].toRawBits() and Int.MAX_VALUE == 0 &&
                    result[it].toRawBits() and Int.MAX_VALUE == 0 &&
                    captured[it].toRawBits() != result[it].toRawBits()
            }
        return JSONObject()
            .put("snapshotElements", captured.size)
            .put("readbackElements", result.size)
            .put("numericMismatchCount", changed.size)
            .put("signedZeroDifferenceCount", signedZeros.size)
            .put("signedZeroIndices", JSONArray(signedZeros))
            .put(
                "firstMismatches",
                JSONArray().apply {
                    changed.take(32).forEach { index ->
                        put(
                            JSONObject()
                                .put("index", index)
                                .put("snapshot", captured[index].toDouble())
                                .put("readback", result[index].toDouble())
                                .put(
                                    "snapshotBits",
                                    Integer.toHexString(captured[index].toRawBits()),
                                )
                                .put("readbackBits", Integer.toHexString(result[index].toRawBits()))
                        )
                    }
                },
            )
    }

    fun json(result: FloatArray): JSONObject =
        JSONObject().apply {
            put("schema", 1)
            put(
                "contract",
                "Nested snapshots at producer, fit and mesh completion; one global read. Identity checks do not establish native intermediate correctness.",
            )
            put("producer", json(producer))
            put("fit", json(fit))
            put("mesh", json(mesh))
            put("resultMatchesReadback", resultMatches(result))
            put(
                "rawMatchesFit",
                mesh.getValue("modelLandmarks").contentEquals(fit.getValue("modelLandmarks")),
            )
            put("roiMatchesFit", mesh.getValue("roi").contentEquals(fit.getValue("roi")))
            put(
                "fitPoseMatchesMesh",
                mesh.getValue("fitPose").contentEquals(fit.getValue("fitPose")),
            )
        }

    companion object {
        private fun sameFiniteValue(a: Float, b: Float): Boolean {
            val first = a.toRawBits()
            val second = b.toRawBits()
            return first and 0x7f800000 != 0x7f800000 &&
                second and 0x7f800000 != 0x7f800000 &&
                (first == second || first and Int.MAX_VALUE == 0 && second and Int.MAX_VALUE == 0)
        }

        val producerFields =
            linkedMapOf(
                "command" to 4,
                "captureFrame" to 6,
                "roi" to 6,
                "cropAffine" to 6,
                "cameraIntrinsics" to 9,
                "serviceIntrinsics" to 9,
                "imageTransform" to 9,
                "cameraToTracking" to 16,
                "mode" to 1,
            )

        private fun fields(points: Int, fitPoints: Int, resultSize: Int, upstreamSize: Int) =
            linkedMapOf(
                "command" to 4,
                "captureFrame" to 6,
                "roi" to 6,
                "cropAffine" to 6,
                "modelLandmarks" to 1434,
                "projected" to points * 3,
                "firstTargets" to fitPoints * 3,
                "secondTargets" to fitPoints * 3,
                "metricVerticesCm" to points * 3,
                "fitPose" to 16,
                "rawWorldPose" to 16,
                "filteredWorldPose" to 16,
                "firstScale" to 1,
                "secondScale" to 1,
                "depthOffset" to 1,
                "cameraIntrinsics" to 9,
                "cameraToTracking" to 16,
                "result" to resultSize,
                "upstream" to upstreamSize,
            )

        // All 33 positive-weight fit points, in the canonical asset's ascending index order.
        val fitFields = fields(33, 33, 1, producerFields.values.sum())
        val meshFields = fields(478, 1, FaceFrame.RESULT_SIZE, fitFields.values.sum())

        private fun unpack(values: FloatArray, fields: Map<String, Int>): Map<String, FloatArray> {
            require(values.size == fields.values.sum()) { "Lab snapshot length mismatch" }
            var offset = 0
            return fields.mapValues { (_, count) ->
                values.copyOfRange(offset, offset + count).also { offset += count }
            }
        }

        private fun json(fields: Map<String, FloatArray>) =
            JSONObject().apply {
                fields
                    .filterKeys { it != "upstream" }
                    .forEach { (key, values) ->
                        put(key, JSONArray().apply { values.forEach { put(it.toDouble()) } })
                    }
            }
    }
}
