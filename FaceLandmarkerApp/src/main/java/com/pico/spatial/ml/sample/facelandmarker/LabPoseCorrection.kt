// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import org.json.JSONArray
import org.json.JSONObject

/** Lab-only effective registration experiment; never persisted as optical calibration. */
internal data class LabPoseCorrection(
    val enabled: Boolean = false,
    val revision: Int = 0,
    val stereo: Boolean = false,
) {
    init {
        require(!stereo || enabled)
    }

    val label
        get() = if (stereo) "Stereo calibrated" else if (enabled) "Head down 40 mm" else "Current"

    val badge
        get() = if (stereo) "STEREO" else if (enabled) "DOWN40" else "CURRENT"

    fun forMode(mode: Int): LabPoseCorrection =
        when {
            mode == LabCameraProfile.STEREO_MODE && !stereo ->
                LabPoseCorrection(true, revision + 1, true)
            mode != LabCameraProfile.STEREO_MODE && stereo -> LabPoseCorrection(false, revision + 1)
            else -> this
        }

    fun matrix(): FloatArray =
        if (stereo) LabStereoCalibration.headCorrection
        else FloatArray(16) { if (it % 5 == 0) 1f else 0f }.also { if (enabled) it[7] = -0.040f }

    fun serviceToStage(head: FloatArray, optical: FloatArray, service: FloatArray): FloatArray =
        StageRegistration.serviceToStage(
            head,
            if (enabled) StageRegistration.multiply(matrix(), optical) else optical,
            service,
        )

    fun rawStageVertices(head: FloatArray, rendered: FloatArray): FloatArray =
        if (!enabled) rendered.copyOf()
        else if (stereo) StageRegistration.transformVertices(rawStageTransform(head), rendered)
        else FloatArray(rendered.size) { rendered[it] + .040f * head[(it % 3) * 4 + 1] }

    fun rawStageTransform(head: FloatArray): FloatArray =
        StageRegistration.multiply(
            StageRegistration.multiply(head, StageRegistration.inverseRigid(matrix())),
            StageRegistration.inverseRigid(head),
        )

    fun json(): JSONObject =
        JSONObject()
            .put(
                "id",
                if (stereo) LabStereoCalibration.ID
                else if (enabled) "head-down-40mm-v1" else "current",
            )
            .put("enabled", enabled)
            .put("revision", revision)
            .put("headTranslationMetres", JSONArray(listOf(matrix()[3], matrix()[7], matrix()[11])))
            .put("headCorrectionMatrix", JSONArray(matrix().toList()))
            .put("cameraRayScale", 1)
            .put("coordinateSpace", "capture-head metres; before head-to-Stage")
            .put("persisted", false)
}
