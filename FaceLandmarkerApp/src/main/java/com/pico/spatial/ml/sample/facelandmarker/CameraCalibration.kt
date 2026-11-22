// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.content.Context
import android.os.Build
import android.util.AtomicFile
import android.util.Log
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

internal data class CameraCalibrationReading(val matrix: FloatArray, val queried: Boolean)

internal object CameraCalibration {
    init {
        System.loadLibrary("face_camera_calibration")
    }

    private var cached: FloatArray? = null

    // PXRCaptureRelease stops the shared camera even for metadata-only clients. Persist the
    // factory optical matrix locally so app relaunch never preempts SpatialML just to query it.
    // Backup is disabled in the manifest; a ROM change invalidates this device-local cache.
    @Synchronized
    fun readLeftCameraToHead(context: Context): CameraCalibrationReading {
        cached?.let {
            return CameraCalibrationReading(it.copyOf(), false)
        }
        val file = AtomicFile(File(context.filesDir, "left-camera-to-head-v1.json"))
        val saved =
            runCatching {
                    val json = JSONObject(file.readFully().toString(Charsets.UTF_8))
                    require(
                        json.getInt("schema") == 1 &&
                            json.getString("fingerprint") == Build.FINGERPRINT
                    )
                    val array = json.getJSONArray("matrix")
                    require(array.length() == 16)
                    FloatArray(16) { array.getDouble(it).toFloat() }.also(::validate)
                }
                .getOrNull()
        if (saved != null) {
            cached = saved
            Log.i(FaceLandmarkerRunner.TAG, "camera_calibration source=device_cache")
            return CameraCalibrationReading(saved.copyOf(), false)
        }
        val matrix = queryLeftCameraToHead().also(::validate)
        val json =
            JSONObject()
                .put("schema", 1)
                .put("fingerprint", Build.FINGERPRINT)
                .put("matrix", JSONArray().apply { matrix.forEach { put(it.toDouble()) } })
        val stream = file.startWrite()
        try {
            stream.write(json.toString().toByteArray(Charsets.UTF_8))
            file.finishWrite(stream)
        } catch (error: Exception) {
            file.failWrite(stream)
            throw error
        }
        cached = matrix
        Log.i(FaceLandmarkerRunner.TAG, "camera_calibration source=native persisted=true")
        return CameraCalibrationReading(matrix.copyOf(), true)
    }

    private fun validate(matrix: FloatArray) {
        require(matrix.size == 16 && matrix.all(Float::isFinite)) {
            "Invalid optical camera calibration"
        }
        require(matrix.copyOfRange(12, 16).contentEquals(floatArrayOf(0f, 0f, 0f, 1f)))
        for (r in 0..2) for (c in 0..2) {
            val product = (0..2).sumOf { matrix[r * 4 + it].toDouble() * matrix[c * 4 + it] }
            require(kotlin.math.abs(product - if (r == c) 1.0 else 0.0) < .01)
        }
        require(listOf(3, 7, 11).all { kotlin.math.abs(matrix[it]) < .5f })
    }

    private external fun queryLeftCameraToHead(): FloatArray
}
