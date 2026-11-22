// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.content.Context
import com.pico.spatial.ml.sample.facelandmarker.SpatialMLGraphSession.Companion.ARITHMETIC
import com.pico.spatial.ml.sample.facelandmarker.SpatialMLGraphSession.Companion.CAMERA_TO_WORLD
import com.pico.spatial.ml.sample.facelandmarker.SpatialMLGraphSession.Companion.HEIGHT
import com.pico.spatial.ml.sample.facelandmarker.SpatialMLGraphSession.Companion.SVD
import com.pico.spatial.ml.sample.facelandmarker.SpatialMLGraphSession.Companion.VST
import com.pico.spatial.ml.sample.facelandmarker.SpatialMLGraphSession.Companion.WIDTH
import com.pico.spatial.ml.sample.facelandmarker.SpatialMLGraphSession.GraphPipeline
import com.pico.spatial.ml.sample.facelandmarker.SpatialMLGraphSession.GraphTensor
import org.json.JSONObject

/**
 * Camera, tracking state and shared fit checks stay in SpatialML. Selected final outputs are read
 * back for app-only geometry/rendering; calibration retains the full service evidence path.
 */
internal class FaceLandmarkerGraph
private constructor(
    private val context: Context,
    backend: Int,
    private val lab: Boolean,
    private val session: SpatialMLGraphSession,
) : AutoCloseable {
    private val command = session.global(1, 4)
    private val result = session.global(1, FaceFrame.RESULT_SIZE)
    private val trackState = session.global(1, 24)
    private val roi = session.global(1, 6)
    private val affine = session.global(2, 3)
    private val frame = session.global(1, 6)
    private val intrinsics = session.global(3, 3)
    private val cameraToStage = session.global(4, 4)
    private val detectorInfo = session.global(1, 3)
    private val retainedVstPipeline = BuildConfig.FACE_RETAINED_VST_PIPELINE
    private val compactVstPipeline = BuildConfig.FACE_COMPACT_VST_PIPELINE
    private val fusedControlModels = BuildConfig.FACE_FUSED_CONTROL_MODELS
    private val compactDetectorMapping =
        if (compactVstPipeline)
            session.global(1, 4, CompactFaceDetector.toImage(LabCameraProfile.identity))
        else null
    private val image = if (retainedVstPipeline) null else session.globalImage()
    private val detectorImage =
        when {
            retainedVstPipeline -> session.globalImage(256, 256)
            compactVstPipeline ->
                // The shipped VST resize reverses non-square destination dimensions on each
                // access. Acquire a square view; the GPU model restores the logical 336x256
                // detector view before cropping. The ROI mapping also includes lab calibration.
                session.globalImage(CompactFaceDetector.VST_SIZE, CompactFaceDetector.VST_SIZE)
            else -> null
        }
    private val frameToken = if (retainedVstPipeline) session.globalTimestamp() else null
    private val raw = session.global(1, 1434)
    private val validity = session.global(1, 2)
    private val depth = session.global(1, 1)
    private val pose = session.global(4, 4)
    private val worldPose = session.global(4, 4)
    private val rawWorldPose = session.global(4, 4)
    private val poseState = session.global(1, 24)
    private val poseStatus = session.global(1, 1)
    private val diagnostics = session.global(1, 32)
    private val firstScale = session.global(1, 1)
    private val secondScale = session.global(1, 1)
    private val geometry = FaceGeometry.load(context)
    private val serviceIntrinsics =
        if (lab || fusedControlModels) session.global(3, 3) else intrinsics
    private val imageTransform = if (lab) session.global(3, 3, LabCameraProfile.identity) else null
    private val labMode = if (lab) session.global(1, 1) else null
    private val trialIntrinsics = if (lab) session.global(3, 3) else null
    private val detectorCrop =
        if (lab && !compactVstPipeline) detectorImage ?: session.globalImage(256, 256) else null
    private val compactDetectorCrop =
        if (lab && compactVstPipeline) session.globalImage(256, 256, float = true) else null
    private val modelCrop = if (lab && !fusedControlModels) session.globalImage(256, 256) else null
    private val normalizedModelCrop =
        if (lab && fusedControlModels) session.globalImage(256, 256, float = true) else null
    private val tongueImage = normalizedModelCrop ?: session.globalImage(256, 256, float = true)
    private val tongueResult = session.global(1, 2)
    private var submittedTongue = false
    private val sourceCapture = if (lab) session.globalImage(1624, 1232) else null
    private val captureSequence = if (lab) session.global(1, 1) else null
    private val completedSequence = session.global(1, 1)
    private val producerProbe =
        if (lab || fusedControlModels)
            session.global(1, LabGeometryProbe.producerFields.values.sum())
        else null
    private val sampleAffine = if (fusedControlModels) session.global(2, 3) else null
    private val fitProbe =
        if (lab) session.global(1, LabGeometryProbe.fitFields.values.sum()) else null
    private val meshProbe =
        if (lab) session.global(1, LabGeometryProbe.meshFields.values.sum()) else null
    private var capture: GraphPipeline? = null
    private var lastRun = 0L
    var calibrationMode = -1
        private set

    var calibrationRevision = -1
        private set

    private var appliedCustom: LabIntrinsics? = null

    var diagnosticImageTransform = LabCameraProfile.identity
        private set

    private val settings =
        floatArrayOf(
            WIDTH.toFloat(),
            HEIGHT.toFloat(),
            .25f,
            .5f,
            1f,
            .35f,
            .45f,
            .1f,
            .25f,
            if (lab) 1f else 0f,
            .75f,
        )
    private lateinit var acquisition: GraphPipeline
    private lateinit var tracking: GraphPipeline
    private lateinit var common: GraphPipeline
    private lateinit var mesh: GraphPipeline
    private lateinit var expressions: GraphPipeline
    private lateinit var tongue: GraphPipeline
    private val scores = session.global(1, 52)
    private val outputPipelines = mutableMapOf<FaceOutputs, Pair<GraphPipeline, GraphTensor>>()
    var submittedOutputs = FaceOutputs.ALL
        private set

    var calibrationEvidence = false
        private set

    init {
        try {
            require(!(retainedVstPipeline && compactVstPipeline)) {
                "Retained and compact adjacent VST pipelines are mutually exclusive"
            }
            require(!fusedControlModels || compactVstPipeline) {
                "Fused control models require the compact adjacent-VST detector contract"
            }
            acquisition = buildProducer(true, backend)
            tracking = buildProducer(false, backend)
            common = buildCommon(backend)
            if (lab) mesh = buildMesh(backend)
            expressions = buildExpressions(backend)
            tongue = buildTongue()
            for (mask in 1..7) {
                val outputs = FaceOutputs(mask)
                val packet = session.global(1, outputs.packetSize)
                outputPipelines[outputs] = buildOutput(outputs, packet) to packet
            }
            if (lab) {
                capture =
                    session.pipeline(context).apply {
                        val halfScale = floats(2, 3, floatArrayOf(.5f, 0f, 0f, 0f, .5f, 0f))
                        if (retainedVstPipeline)
                            namedOp(
                                SpatialMLGraphSession.RETAINED_VST_AFFINE,
                                mapOf(
                                    "frame token" to checkNotNull(frameToken),
                                    "affine" to halfScale,
                                ),
                                mapOf("image" to checkNotNull(sourceCapture)),
                            )
                        else
                            op(
                                SpatialMLGraphSession.APPLY_AFFINE,
                                listOf(halfScale, checkNotNull(image)),
                                listOf(checkNotNull(sourceCapture)),
                            )
                        completionMarker(checkNotNull(captureSequence))
                    }
                setCalibration(LabCameraConfiguration(0, LabIntrinsics.modeC, 0))
            }
        } catch (error: Throwable) {
            session.close()
            throw error
        }
    }

    private fun buildProducer(acquire: Boolean, backend: Int): GraphPipeline =
        session.pipeline(context).apply {
            val timestamp = timestamp()
            val config = floats(1, settings.size, settings)
            val controlTransform = imageTransform ?: floats(3, 3, LabCameraProfile.identity)
            val controlTrial = trialIntrinsics ?: serviceIntrinsics
            val controlMode = labMode ?: floats(1, 1, floatArrayOf(0f))
            val detectorAffine =
                if (!compactVstPipeline && (retainedVstPipeline || acquire))
                    sourceAffine(
                        floats(
                            2,
                            3,
                            if (lab)
                                floatArrayOf(
                                    256f / WIDTH,
                                    0f,
                                    0f,
                                    0f,
                                    256f / WIDTH,
                                    (256f - 256f * HEIGHT / WIDTH) / 2f,
                                )
                            else floatArrayOf(256f / WIDTH, 0f, 0f, 0f, 256f / HEIGHT, 0f),
                        )
                    )
                else null
            when {
                retainedVstPipeline ->
                    namedOp(
                        SpatialMLGraphSession.RETAINED_VST_ACCESS,
                        mapOf("detector affine" to checkNotNull(detectorAffine)),
                        mapOf(
                            "detector image" to checkNotNull(detectorImage),
                            "frame token" to checkNotNull(frameToken),
                            "timestamp" to timestamp,
                            "camera matrix" to serviceIntrinsics,
                        ),
                    )
                compactVstPipeline && acquire -> {
                    // The compact detector view and full landmark view are deliberately adjacent.
                    // Their independent timestamps remain available in native tracing; the fused
                    // control contract uses the full-view timestamp and calibration.
                    namedOp(
                        VST,
                        emptyMap(),
                        mapOf(
                            "left image" to checkNotNull(detectorImage),
                            "timestamp" to timestamp(),
                            "camera matrix" to floats(3, 3),
                        ),
                    )
                    namedOp(
                        VST,
                        emptyMap(),
                        mapOf(
                            "left image" to checkNotNull(image),
                            "timestamp" to timestamp,
                            "camera matrix" to serviceIntrinsics,
                        ),
                    )
                }
                else ->
                    namedOp(
                        VST,
                        emptyMap(),
                        mapOf(
                            "left image" to checkNotNull(image),
                            "timestamp" to timestamp,
                            "camera matrix" to serviceIntrinsics,
                        ),
                    )
            }
            if (lab && !fusedControlModels)
                script(
                    "lab_camera",
                    mapOf(
                        "serviceIntrinsics" to serviceIntrinsics,
                        "imageTransform" to checkNotNull(imageTransform),
                        "trialIntrinsics" to checkNotNull(trialIntrinsics),
                        "labMode" to checkNotNull(labMode),
                    ),
                    mapOf("intrinsics" to intrinsics),
                )
            // Resolve the calibrated left optical camera at the VST timestamp, inside this same
            // producer.
            namedOp(
                CAMERA_TO_WORLD,
                mapOf("timestamp" to timestamp),
                mapOf("left" to cameraToStage),
            )
            var fine: GraphTensor? = null
            var coarse: GraphTensor? = null
            var fineScore: GraphTensor? = null
            var coarseScore: GraphTensor? = null
            if (acquire) {
                val input =
                    when {
                        compactVstPipeline ->
                            compactDetectorInput(checkNotNull(detectorImage), compactDetectorCrop)
                        retainedVstPipeline -> normalizeRgb(checkNotNull(detectorImage))
                        else ->
                            preprocess(
                                checkNotNull(image),
                                checkNotNull(detectorAffine),
                                detectorCrop,
                                detector = true,
                            )
                    }
                fine = floats(512, 16)
                coarse = floats(384, 16)
                fineScore = floats(512, 1)
                coarseScore = floats(384, 1)
                model(
                    "face_detector",
                    mapOf("image" to input),
                    mapOf(
                        "box_coords_1" to checkNotNull(fine),
                        "box_coords_2" to checkNotNull(coarse),
                        "box_scores_1" to checkNotNull(fineScore),
                        "box_scores_2" to checkNotNull(coarseScore),
                    ),
                    backend,
                )
            }
            if (fusedControlModels) {
                val inputs =
                    linkedMapOf<String, GraphTensor>().apply {
                        if (acquire) {
                            put("boxes_fine", checkNotNull(fine))
                            put("boxes_coarse", checkNotNull(coarse))
                            put("scores_fine", checkNotNull(fineScore))
                            put("scores_coarse", checkNotNull(coarseScore))
                        }
                        put("settings", config)
                        put("timestamp", timestamp)
                        put("command", command)
                        put("track_state", trackState)
                        put("service_intrinsics", serviceIntrinsics)
                        put("image_transform", controlTransform)
                        put("trial_intrinsics", controlTrial)
                        put("lab_mode", controlMode)
                        put("left_camera_to_xr", cameraToStage)
                        if (acquire)
                            put(
                                "detector_to_source",
                                // This legacy model input name denotes the working image space.
                                // Landmark sampling composes its crop with imageTransform, so
                                // detector coordinates must already be in that calibrated space.
                                checkNotNull(compactDetectorMapping),
                            )
                    }
                val outputs =
                    linkedMapOf(
                        "intrinsics" to intrinsics,
                        "roi" to roi,
                        "affine" to affine,
                        "sample_affine" to checkNotNull(sampleAffine),
                        "frame" to frame,
                        "next_track_state" to trackState,
                    )
                if (acquire) outputs["detector_info"] = detectorInfo
                outputs["producer_snapshot"] = checkNotNull(producerProbe)
                model(
                    if (acquire) "face_detector_control" else "face_roi_control",
                    inputs,
                    outputs,
                    0,
                )
            } else {
                if (acquire)
                    script(
                        "decode_detection",
                        mapOf(
                            "boxesFine" to checkNotNull(fine),
                            "boxesCoarse" to checkNotNull(coarse),
                            "scoresFine" to checkNotNull(fineScore),
                            "scoresCoarse" to checkNotNull(coarseScore),
                            "settings" to config,
                            "timestamp" to timestamp,
                            "trackState" to trackState,
                        ),
                        mapOf("roi" to roi, "affine" to affine, "detectorInfo" to detectorInfo),
                    )
                script(
                    "prepare_roi",
                    mapOf(
                        "timestamp" to timestamp,
                        "settings" to config,
                        "command" to command,
                        "trackState" to trackState,
                        "roi" to roi,
                    ),
                    mapOf(
                        "trackState" to trackState,
                        "roi" to roi,
                        "affine" to affine,
                        "frame" to frame,
                    ),
                )
                if (lab)
                    script(
                        "lab_frame_snapshot",
                        mapOf(
                            "command" to command,
                            "frame" to frame,
                            "roi" to roi,
                            "affine" to affine,
                            "intrinsics" to intrinsics,
                            "serviceIntrinsics" to serviceIntrinsics,
                            "imageTransform" to checkNotNull(imageTransform),
                            "leftCameraToXr" to cameraToStage,
                            "labMode" to checkNotNull(labMode),
                        ),
                        mapOf("snapshot" to checkNotNull(producerProbe)),
                    )
            }
        }

    private fun buildCommon(backend: Int): GraphPipeline =
        session.pipeline(context).apply {
            val config = floats(1, settings.size, settings)
            val presence = floats(1, 1)
            val landmarkInput =
                if (retainedVstPipeline) {
                    val tile = image(SpatialMLGraphSession.LANDMARK_TILE_SIZE)
                    val tileAffine = floats(2, 3)
                    namedOp(
                        SpatialMLGraphSession.RETAINED_VST_ROI,
                        mapOf(
                            "frame token" to checkNotNull(frameToken),
                            "affine" to sourceAffine(affine),
                        ),
                        mapOf(
                            "tile" to tile,
                            "tile affine" to tileAffine,
                            "metadata" to floats(1, 8),
                        ),
                    )
                    preprocess(tile, tileAffine, modelCrop, retainedFloatCrop = tongueImage)
                } else {
                    preprocess(
                        checkNotNull(image),
                        if (fusedControlModels) checkNotNull(sampleAffine)
                        else sourceAffine(affine),
                        modelCrop,
                        retainedFloatCrop = tongueImage,
                    )
                }
            model(
                "face_landmarks_detector",
                mapOf("input_12" to landmarkInput),
                mapOf("Identity" to raw, "Identity_1" to presence, "Identity_2" to floats(1, 1)),
                backend,
            )
            if (fusedControlModels) {
                val inputs =
                    linkedMapOf(
                        "raw_landmarks" to raw,
                        "presence_logit" to presence,
                        "roi" to roi,
                        "affine" to affine,
                        "settings" to config,
                        "frame" to frame,
                        "intrinsics" to intrinsics,
                        "track_state" to trackState,
                        "left_camera_to_xr" to cameraToStage,
                        "command" to command,
                        "pose_state" to poseState,
                        "producer_snapshot" to checkNotNull(producerProbe),
                    )
                val outputs =
                    linkedMapOf(
                        "next_track_state" to trackState,
                        "validity" to validity,
                        "depth_offset" to depth,
                        "first_scale" to firstScale,
                        "second_scale" to secondScale,
                        "pose" to pose,
                        "next_pose_state" to poseState,
                        "world_pose" to worldPose,
                        "raw_world_pose" to rawWorldPose,
                        "pose_status" to poseStatus,
                        "diagnostics" to diagnostics,
                    )
                if (lab) outputs["fit_snapshot"] = checkNotNull(fitProbe)
                model(
                    if (lab) "face_landmark_control_lab" else "face_landmark_control",
                    inputs,
                    outputs,
                    0,
                )
                return@apply
            }
            val fitIndices = (0 until 468).filter { geometry.canonical[it * 4 + 3] > 0 }
            val fitCount = fitIndices.size
            if (lab || BuildConfig.FACE_FUSED_GEOMETRY)
                check(fitCount == 33) {
                    "Update lab probe layout for changed canonical fit weights"
                }
            val canonical =
                floats(
                    fitCount,
                    4,
                    fitIndices
                        .flatMap { index -> (0..3).map { geometry.canonical[index * 4 + it] } }
                        .toFloatArray(),
                )
            val projected = floats(fitCount, 3)
            val firstTargets = floats(fitCount, 3)
            script(
                "track_landmarks",
                mapOf(
                    "rawLandmarks" to raw,
                    "presenceLogit" to presence,
                    "roi" to roi,
                    "settings" to config,
                    "frame" to frame,
                    "intrinsics" to intrinsics,
                    "indices" to floats(1, fitCount, fitIndices.map(Int::toFloat).toFloatArray()),
                    "canonical" to canonical,
                    "subset" to floats(1, 1),
                    "trackState" to trackState,
                ),
                mapOf(
                    "trackState" to trackState,
                    "landmarks" to floats(1, 1),
                    "blendInput" to floats(1, 1),
                    "validity" to validity,
                    "projected" to projected,
                    "targets" to firstTargets,
                    "depthOffset" to depth,
                ),
            )
            val secondTargets: GraphTensor
            val metric: GraphTensor
            if (BuildConfig.FACE_INLINE_GEOMETRY) {
                secondTargets = floats(fitCount, 3)
                metric = floats(fitCount, 3)
                model(
                    "face_fit_inline",
                    mapOf(
                        "first_targets" to firstTargets,
                        "projected" to projected,
                        "depth" to depth,
                        "validity" to validity,
                    ),
                    mapOf(
                        "first_scale" to firstScale,
                        "second_scale" to secondScale,
                        "second_targets" to secondTargets,
                        "metric" to metric,
                        "pose" to pose,
                    ),
                    0,
                )
            } else if (BuildConfig.FACE_FUSED_GEOMETRY) {
                val fitted = fitWithModels(firstTargets, projected)
                secondTargets = fitted.first
                metric = fitted.second
            } else {
                solve(canonical, firstTargets, firstScale, floats(4, 4))
                secondTargets =
                    unproject(
                        projected,
                        canonical,
                        firstScale,
                        floats(1, 1, floatArrayOf(1f)),
                        fitCount,
                    )
                solve(canonical, secondTargets, secondScale, floats(4, 4))
                metric = unproject(projected, canonical, firstScale, secondScale, fitCount)
                solve(canonical, metric, floats(1, 1), pose)
            }
            // Fit consumers retain their service-side validity and tracker-state feedback.
            script(
                "face_pose",
                mapOf(
                    "pose" to pose,
                    "validity" to validity,
                    "leftCameraToXr" to cameraToStage,
                    "command" to command,
                    "settings" to config,
                    "frame" to frame,
                    "trackState" to trackState,
                    "poseState" to poseState,
                ),
                mapOf(
                    "poseState" to poseState,
                    "trackState" to trackState,
                    "validity" to validity,
                    "worldPose" to worldPose,
                    "rawWorldPose" to rawWorldPose,
                    "poseStatus" to poseStatus,
                ),
            )
            script(
                "registration_diagnostics",
                mapOf(
                    "projected" to projected,
                    "metric" to metric,
                    "canonical" to canonical,
                    "pose" to pose,
                    "validity" to validity,
                    "roi" to roi,
                    "intrinsics" to intrinsics,
                    "frame" to frame,
                    "command" to command,
                    "trackState" to trackState,
                    "poseStatus" to poseStatus,
                ),
                mapOf(
                    "diagnostics" to diagnostics,
                    "validity" to validity,
                    "trackState" to trackState,
                ),
            )
            if (lab)
                geometryProbe(
                    projected,
                    firstTargets,
                    secondTargets,
                    metric,
                    floats(1, 1, floatArrayOf(0f)),
                    checkNotNull(producerProbe),
                    checkNotNull(fitProbe),
                )
        }

    /** Four CPU model calls replace eight JS calls; native SVD and snapshot tensors stay intact. */
    private fun GraphPipeline.fitWithModels(
        firstTargets: GraphTensor,
        projected: GraphTensor,
    ): Pair<GraphTensor, GraphTensor> {
        var covariance = floats(3, 3)
        var centers = floats(1, 6)
        model(
            "face_fit_prepare",
            mapOf("targets" to firstTargets),
            mapOf("covariance" to covariance, "centers" to centers),
            0,
        )
        var targets = firstTargets
        val stages = mutableListOf<GraphTensor>()
        val one = floats(1, 1, floatArrayOf(1f))
        repeat(2) { pass ->
            val u = floats(3, 3)
            val vt = floats(3, 3)
            op(SVD, listOf(covariance), listOf(floats(3, 1), u, vt))
            val nextTargets = floats(33, 3)
            val nextCovariance = floats(3, 3)
            val nextCenters = floats(1, 6)
            model(
                "face_fit_bridge",
                mapOf(
                    "targets" to targets,
                    "centers" to centers,
                    "u" to u,
                    "vt" to vt,
                    "projected" to projected,
                    "depth" to depth,
                    "previous_scale" to if (pass == 0) one else firstScale,
                    "validity" to validity,
                ),
                mapOf(
                    "scale" to if (pass == 0) firstScale else secondScale,
                    "next_targets" to nextTargets,
                    "covariance" to nextCovariance,
                    "next_centers" to nextCenters,
                ),
                0,
            )
            targets = nextTargets
            covariance = nextCovariance
            centers = nextCenters
            stages.add(nextTargets)
        }
        val u = floats(3, 3)
        val vt = floats(3, 3)
        op(SVD, listOf(covariance), listOf(floats(3, 1), u, vt))
        model(
            "face_fit_finish",
            mapOf("targets" to targets, "centers" to centers, "u" to u, "vt" to vt),
            mapOf("pose" to pose),
            0,
        )
        return stages[0] to stages[1]
    }

    private fun GraphPipeline.solve(
        canonical: GraphTensor,
        targets: GraphTensor,
        scale: GraphTensor,
        pose: GraphTensor,
    ) {
        val covariance = floats(3, 3)
        val centers = floats(1, 6)
        script(
            "geometry_covariance",
            mapOf("canonical" to canonical, "targets" to targets),
            mapOf("covariance" to covariance, "centers" to centers),
        )
        val u = floats(3, 3)
        val vt = floats(3, 3)
        op(SVD, listOf(covariance), listOf(floats(3, 1), u, vt))
        script(
            "geometry_solve",
            mapOf(
                "canonical" to canonical,
                "targets" to targets,
                "centers" to centers,
                "u" to u,
                "vt" to vt,
            ),
            mapOf("pose" to pose, "scale" to scale),
        )
    }

    private fun GraphPipeline.unproject(
        projected: GraphTensor,
        canonical: GraphTensor,
        first: GraphTensor,
        second: GraphTensor,
        count: Int,
    ): GraphTensor =
        floats(count, 3).also { target ->
            script(
                "geometry_unproject",
                mapOf(
                    "projected" to projected,
                    "depthOffset" to depth,
                    "firstScale" to first,
                    "secondScale" to second,
                    "canonical" to canonical,
                    "validity" to validity,
                ),
                mapOf("targets" to target),
            )
        }

    private fun buildMesh(backend: Int): GraphPipeline =
        session.pipeline(context).apply {
            val config = floats(1, settings.size, settings)
            val canonical = floats(geometry.canonical.size / 4, 4, geometry.canonical)
            val landmarks = floats(478, 3)
            val blendInput = floats(1, 292)
            script(
                "mesh_landmarks",
                mapOf(
                    "rawLandmarks" to raw,
                    "roi" to roi,
                    "settings" to config,
                    "validity" to validity,
                    "subset" to
                        floats(1, 146, geometry.blendshapeIndices.map(Int::toFloat).toFloatArray()),
                ),
                mapOf("landmarks" to landmarks, "blendInput" to blendInput),
            )
            val projected = floats(478, 3)
            script(
                "geometry_project",
                mapOf(
                    "landmarks" to landmarks,
                    "intrinsics" to intrinsics,
                    "settings" to config,
                    "canonical" to canonical,
                    "validity" to validity,
                ),
                mapOf(
                    "validity" to validity,
                    "projected" to projected,
                    "targets" to floats(478, 3),
                    "depthOffset" to floats(1, 1),
                ),
            )
            val metric = unproject(projected, canonical, firstScale, secondScale, 478)
            op(ARITHMETIC, listOf(blendInput), listOf(blendInput), "{0} / 1024.0")
            val blendshapes = floats(1, 52)
            model(
                "face_blendshapes",
                mapOf("input_points" to blendInput),
                mapOf("tf.__operators__.getitem_3" to blendshapes),
                backend,
            )
            script(
                "pack_service_result",
                mapOf(
                    "command" to command,
                    "validity" to validity,
                    "roi" to roi,
                    "landmarks" to landmarks,
                    "metric" to metric,
                    "pose" to pose,
                    // Match Unity: current vertices must use the same raw fit, not a lagging
                    // rigid-object pose. Mixing them changes the calibrated projection rays.
                    "worldPose" to rawWorldPose,
                    "blendshapes" to blendshapes,
                    "detectorInfo" to detectorInfo,
                    "diagnostics" to diagnostics,
                    "leftCameraToXr" to cameraToStage,
                ),
                mapOf("result" to result),
            )
            if (lab) {
                geometryProbe(
                    projected,
                    floats(1, 3, FloatArray(3)),
                    floats(1, 3, FloatArray(3)),
                    metric,
                    result,
                    checkNotNull(fitProbe),
                    checkNotNull(meshProbe),
                )
                // A packet's leading sequence can become visible before its remaining bytes.
                // This separate final operator runs after both result packing and the snapshot.
                completionMarker(checkNotNull(completedSequence))
            }
        }

    private fun buildExpressions(backend: Int): GraphPipeline =
        session.pipeline(context).apply {
            val input = floats(1, 292)
            model(
                "face_blend_input",
                mapOf("raw_landmarks" to raw, "roi" to roi),
                mapOf("blend_input" to input),
                0,
            )
            model(
                "face_blendshapes",
                mapOf("input_points" to input),
                mapOf("tf.__operators__.getitem_3" to scores),
                backend,
            )
        }

    private fun buildTongue(): GraphPipeline =
        session.pipeline(context).apply {
            model(
                "tongue_visibility",
                mapOf(
                    "mouth_image" to tongueImage,
                    "raw_landmarks" to raw,
                    "validity" to validity,
                    "command" to command,
                ),
                mapOf("tongue_result" to tongueResult),
                0,
            )
        }

    private fun buildOutput(outputs: FaceOutputs, packet: GraphTensor): GraphPipeline =
        session.pipeline(context).apply {
            val inputs =
                linkedMapOf(
                    "command" to command,
                    "validity" to validity,
                    "roi" to roi,
                    "diagnostics" to diagnostics,
                    "camera" to cameraToStage,
                )
            if (outputs.spatial) inputs["world_pose"] = rawWorldPose
            if (outputs.mesh) {
                inputs["raw_landmarks"] = raw
                inputs["fit_pose"] = pose
                inputs["first_scale"] = firstScale
                inputs["second_scale"] = secondScale
                inputs["depth"] = depth
            }
            if (outputs.blendshapes) inputs["blendshapes"] = scores
            // One compiled FP32 concatenation, no JS array marshaling or accelerator round trip.
            // CPU preserves sequence/timestamp bits; reduced-precision GPU publication is unsafe.
            model("face_output_${outputs.mask}", inputs, mapOf("result" to packet), 0)
            completionMarker(completedSequence)
        }

    private fun GraphPipeline.completionMarker(sequence: GraphTensor) {
        if (fusedControlModels)
            model(
                "face_completion_marker",
                mapOf("command" to command),
                mapOf("sequence" to sequence),
                0,
            )
        else
            script("lab_capture_marker", mapOf("command" to command), mapOf("sequence" to sequence))
    }

    private fun GraphPipeline.geometryProbe(
        projected: GraphTensor,
        firstTargets: GraphTensor,
        secondTargets: GraphTensor,
        metric: GraphTensor,
        packed: GraphTensor,
        upstream: GraphTensor,
        snapshot: GraphTensor,
    ) {
        script(
            "lab_geometry_snapshot",
            mapOf(
                "command" to command,
                "frame" to frame,
                "roi" to roi,
                "affine" to affine,
                "rawLandmarks" to raw,
                "projected" to projected,
                "firstTargets" to firstTargets,
                "secondTargets" to secondTargets,
                "metric" to metric,
                "pose" to pose,
                "rawWorldPose" to rawWorldPose,
                "worldPose" to worldPose,
                "firstScale" to firstScale,
                "secondScale" to secondScale,
                "depthOffset" to depth,
                "intrinsics" to intrinsics,
                "leftCameraToXr" to cameraToStage,
                "result" to packed,
                "upstream" to upstream,
            ),
            mapOf("snapshot" to snapshot),
        )
    }

    fun submit(
        sequence: Int,
        seconds: Float,
        sizeScale: Float,
        acquire: Boolean,
        outputs: FaceOutputs = FaceOutputs.ALL,
        evidence: Boolean = lab,
        tongueRequested: Boolean = false,
    ): Long {
        require(outputs.any)
        submittedOutputs = outputs
        require(!evidence || (lab && outputs == FaceOutputs.ALL))
        calibrationEvidence = evidence
        require(!tongueRequested || (!evidence && outputs.blendshapes))
        submittedTongue = tongueRequested
        session.reset(
            command,
            floatArrayOf(sequence.toFloat(), seconds, sizeScale, if (acquire) 1f else 0f),
        )
        val producer = if (acquire) acquisition else tracking
        var run = common.submit(producer.submit())
        if (calibrationEvidence) {
            run = mesh.submit(run)
        } else {
            if (outputs.blendshapes) run = expressions.submit(run)
            if (submittedTongue) run = tongue.submit(run)
            run = outputPipelines.getValue(outputs).first.submit(run)
        }
        lastRun = run
        return lastRun
    }

    private fun GraphPipeline.sourceAffine(crop: GraphTensor): GraphTensor {
        if (!lab) return crop
        return floats(2, 3).also { composed ->
            script(
                "lab_affine",
                mapOf("cropAffine" to crop, "imageTransform" to checkNotNull(imageTransform)),
                mapOf("sourceToCrop" to composed),
            )
        }
    }

    // Called only between completed frames; no tensor resets overlap a producer or capture.
    fun setCalibration(configuration: LabCameraConfiguration) {
        check(lab)
        val mode = configuration.mode
        if (calibrationMode == mode && calibrationRevision == configuration.revision) return
        val profile = LabCameraProfile.configuration(mode, android.os.Build.FINGERPRINT)
        val camera =
            if (mode == LabCameraProfile.CUSTOM_MODE) configuration.custom.matrix()
            else profile.second
        val imageChanged = !diagnosticImageTransform.contentEquals(profile.first)
        val geometryChanged =
            calibrationMode != mode ||
                (mode == LabCameraProfile.CUSTOM_MODE && appliedCustom != configuration.custom)
        diagnosticImageTransform = profile.first
        session.reset(checkNotNull(imageTransform), profile.first)
        compactDetectorMapping?.let {
            session.reset(it, CompactFaceDetector.toImage(profile.first))
        }
        session.reset(checkNotNull(trialIntrinsics), camera)
        session.reset(checkNotNull(labMode), floatArrayOf(mode.toFloat()))
        // Intrinsics edits do not change model sampling or invalidate the accepted camera clock.
        if (imageChanged) session.reset(trackState, FloatArray(24))
        if (geometryChanged) session.reset(poseState, FloatArray(24))
        calibrationMode = mode
        calibrationRevision = configuration.revision
        appliedCustom = configuration.custom
        android.util.Log.i(
            FaceLandmarkerRunner.TAG,
            "registration_lab_calibration_applied mode=$mode revision=$calibrationRevision intrinsics=${camera.contentToString()}",
        )
    }

    fun submitCapture() {
        check(calibrationEvidence) { "Calibration capture requires all face outputs" }
        checkNotNull(capture).submit(lastRun)
    }

    fun captureReady(sequence: Int): Boolean =
        session.read(checkNotNull(captureSequence), 1)[0] == sequence.toFloat()

    fun readCapture(sequence: Int): LabCapture {
        val probe =
            LabGeometryProbe(
                session.read(checkNotNull(meshProbe), LabGeometryProbe.meshFields.values.sum()),
                sequence,
                calibrationMode,
            )
        val producer = probe.producer
        val detectorBytes =
            compactDetectorCrop?.let(::readNormalizedCrop)
                ?: session.readBytes(checkNotNull(detectorCrop), 256 * 256 * 3)
        val modelBytes =
            normalizedModelCrop?.let(::readNormalizedCrop)
                ?: session.readBytes(checkNotNull(modelCrop), 256 * 256 * 3)
        return LabCapture(
            session.readBytes(checkNotNull(sourceCapture), 1624 * 1232 * 3),
            detectorBytes,
            modelBytes,
            probe.fit.getValue("modelLandmarks"),
            producer.getValue("cropAffine"),
            producer.getValue("captureFrame"),
            producer.getValue("cameraIntrinsics"),
            producer.getValue("serviceIntrinsics"),
            producer.getValue("imageTransform"),
            calibrationMode,
            probe,
            calibrationRevision,
        )
    }

    private fun readNormalizedCrop(crop: GraphTensor): ByteArray =
        session.read(crop, 256 * 256 * 3).let { values ->
            ByteArray(values.size) { index ->
                (values[index] * 255f + .5f).toInt().coerceIn(0, 255).toByte()
            }
        }

    fun readResult(): FloatArray =
        if (calibrationEvidence) session.read(result, FaceFrame.RESULT_SIZE)
        else
            session.read(
                outputPipelines.getValue(submittedOutputs).second,
                submittedOutputs.packetSize,
            )

    fun resultComplete(sequence: Int): Boolean =
        session.read(completedSequence, 1)[0] == sequence.toFloat()

    fun readTongue(sequence: Int): Float? {
        if (!submittedTongue) return null
        val result = session.read(tongueResult, 2)
        check(result[0] == sequence.toFloat() && result[1].isFinite() && result[1] in 0f..1f) {
            "Tongue evidence does not match the completed face capture"
        }
        return result[1]
    }

    override fun close() = session.close()

    companion object {

        fun create(context: Context, backend: Int, lab: Boolean = false): FaceLandmarkerGraph {
            val session = SpatialMLGraphSession()
            try {
                return FaceLandmarkerGraph(context, backend, lab, session)
            } catch (error: Throwable) {
                session.close()
                throw error
            }
        }
    }
}

internal class FaceGeometry(
    val canonical: FloatArray,
    val triangles: List<Int>,
    val blendshapeIndices: List<Int>,
    val blendshapeNames: List<String>,
) {
    companion object {
        fun load(context: Context): FaceGeometry {
            val json =
                JSONObject(
                    context.assets
                        .open("${SpatialMLGraphSession.ASSETS}/data/face_geometry.json")
                        .bufferedReader()
                        .use { it.readText() }
                )
            fun ints(key: String): List<Int> =
                json.getJSONArray(key).let { array -> List(array.length()) { array.getInt(it) } }
            val canonical =
                json.getJSONArray("canonical").let { array ->
                    FloatArray(array.length()) { array.getDouble(it).toFloat() }
                }
            val names =
                json.getJSONArray("blendshapeNames").let { array ->
                    List(array.length()) { array.getString(it) }
                }
            return FaceGeometry(canonical, ints("triangles"), ints("blendshapeIndices"), names)
                .also {
                    require(canonical.size >= 468 * 4 && canonical.all(Float::isFinite))
                    require(
                        it.triangles.size % 3 == 0 &&
                            it.triangles.all { index -> index in 0 until 478 }
                    )
                    require(
                        it.blendshapeIndices.size == 146 &&
                            it.blendshapeIndices.all { index -> index in 0 until 478 } &&
                            names.size == 52
                    )
                }
        }
    }
}
