// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject

/** Board detection and measured dimensions belong to the offline observer, never the face fit. */
internal object LabBoardCapture {
    const val CHECK = "board-check-v1"
    const val VIEWS = "board-source-views-v1"
    const val TRIAL = "board-registration-v1"
    val kinds = listOf(CHECK, VIEWS, TRIAL)
    private val holds =
        listOf(
            "Near, about 0.6 m. Head level; board centred.",
            "Middle, about 1.2 m. Head level; board centred.",
            "Far, about 2 m. Head level; keep every square readable.",
            "Middle. LEFT ear toward LEFT shoulder about 15 degrees.",
            "Middle. RIGHT ear toward RIGHT shoulder about 15 degrees.",
            "Middle. Look slightly upward; keep the whole board visible.",
            "Middle. Look slightly downward; keep the whole board visible.",
            "Repeat middle distance with your head level.",
        )
    private val views =
        listOf(
            "Board centred; face it squarely.",
            "Board in the left image region.",
            "Board in the right image region.",
            "Board in the upper image region.",
            "Board in the lower image region.",
            "View the board from its left, about 20 degrees.",
            "View the board from its right, about 20 degrees.",
            "View the board from above, about 20 degrees.",
            "View the board from below, about 20 degrees.",
            "Closer; keep the entire board visible.",
            "Farther; keep every square readable.",
            "Oblique view with both horizontal and vertical angle.",
            "Validation: upper-left region, oblique view.",
            "Validation: lower-right region, oblique view.",
            "Validation: middle distance, view from the left.",
            "Validation: near, view from above.",
        )

    fun prompts(kind: String): List<String> =
        when (kind) {
            CHECK -> listOf(holds[1])
            VIEWS -> views
            TRIAL -> holds
            else -> error("Unknown board capture")
        }

    fun count(kind: String) = prompts(kind).size * if (kind == VIEWS) 1 else 3

    fun stationary(baseline: List<Float>, head: FloatArray?): Boolean =
        LabRollCapture.motion(baseline, head)?.let {
            it.displacement < .003f &&
                abs(it.yaw) < .3f &&
                abs(it.pitch) < .3f &&
                abs(it.roll) < .3f
        } == true

    fun metadata(tag: LabAutoTag): JSONObject =
        JSONObject()
            .put("kind", tag.boardKind)
            .put("innerCorners", JSONArray(listOf(8, 6)))
            .put("nominalSquareMetres", .020)
            .put("measuredSquareMetres", JSONObject.NULL)
            .put("measurementStatus", "required in host board specification before analysis")
            .put(
                "cornerIdentity",
                "label physical top-left outside pattern; confirm in source and both eyes",
            )
            .put("faceRequired", false)
            .put("boardDetection", "offline; capture completion does not certify board visibility")
            .put(
                "split",
                if (tag.boardKind == VIEWS) if (tag.pose < 12) "fit" else "validation"
                else "registration",
            )
            .put("exposureInHold", tag.boardExposure + 1)
            .put("distanceIsPrompt", true)
            .put("poseCorrection", "current")
            .put("sizeScale", 1)
}
