// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.content.Context
import android.os.Build
import android.util.AtomicFile
import java.io.File
import java.time.Instant
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject

/** Small value-only profiles; saving does not require a camera or a measured face. */
internal class LabCalibrationStore(context: Context) {
    private val cache = AtomicFile(File(context.filesDir, "face-intrinsics-calibration-v1.json"))
    private val profiles =
        File(context.getExternalFilesDir(null) ?: context.filesDir, "RegistrationLabProfiles")

    fun load(): LabIntrinsics? =
        if (!cache.baseFile.exists()) null
        else decode(JSONObject(cache.readFully().toString(Charsets.UTF_8)))

    fun save(values: LabIntrinsics): File {
        val json = encode(values)
        val bytes = json.toString(2).toByteArray(Charsets.UTF_8)
        check(profiles.isDirectory || profiles.mkdirs()) { "Cannot create calibration directory" }
        val archive =
            File(
                profiles,
                "calibration-${Instant.now().toString().replace(':', '-')}-${UUID.randomUUID().toString().take(6)}.json",
            )
        write(AtomicFile(archive), bytes)
        write(AtomicFile(File(profiles, "saved-calibration.json")), bytes)
        write(cache, bytes)
        return archive
    }

    companion object {
        fun encode(values: LabIntrinsics): JSONObject =
            JSONObject()
                .put("schema", 1)
                .put("profileType", "custom-virtual-camera")
                .put("savedAtUtc", Instant.now().toString())
                .put("fingerprint", Build.FINGERPRINT)
                .put("nativeWidth", 3248)
                .put("nativeHeight", 2464)
                .put("coordinateSpace", "virtual-image-pixels")
                .put("basePreset", "C: Renderer trial")
                .put("fx", values.fx.toDouble())
                .put("fy", values.fy.toDouble())
                .put("cx", values.cx.toDouble())
                .put("cy", values.cy.toDouble())
                .put("cameraIntrinsics", floats(values.matrix()))
                .put("imageTransform", floats(LabCameraProfile.preservedImageAffine))

        fun decode(json: JSONObject): LabIntrinsics {
            require(
                json.getInt("schema") == 1 &&
                    json.getString("profileType") == "custom-virtual-camera"
            )
            require(json.getString("fingerprint") == Build.FINGERPRINT) {
                "Saved profile belongs to another ROM"
            }
            require(json.getInt("nativeWidth") == 3248 && json.getInt("nativeHeight") == 2464)
            require(json.getString("coordinateSpace") == "virtual-image-pixels")
            val values =
                LabIntrinsics(
                    json.getDouble("fx").toFloat(),
                    json.getDouble("fy").toFloat(),
                    json.getDouble("cx").toFloat(),
                    json.getDouble("cy").toFloat(),
                )
            require(values.matches(array(json.getJSONArray("cameraIntrinsics"))))
            val affine = array(json.getJSONArray("imageTransform"))
            require(affine.contentEquals(LabCameraProfile.preservedImageAffine)) {
                "Saved profile uses another image transform"
            }
            return values
        }

        private fun array(json: JSONArray) =
            FloatArray(json.length()) { json.getDouble(it).toFloat() }

        private fun floats(values: FloatArray) =
            JSONArray().apply { values.forEach { put(it.toDouble()) } }

        private fun write(file: AtomicFile, bytes: ByteArray) {
            val stream = file.startWrite()
            try {
                stream.write(bytes)
                file.finishWrite(stream)
            } catch (error: Exception) {
                file.failWrite(stream)
                throw error
            }
        }
    }
}
