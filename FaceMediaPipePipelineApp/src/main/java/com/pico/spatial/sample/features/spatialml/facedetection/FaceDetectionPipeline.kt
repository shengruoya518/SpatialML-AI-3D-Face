/*
 * Copyright 2025 - 2026 PICO. All rights reserved.
 *
 * NOTICE: All information contained herein is, and remains the property of PICO.
 * The intellectual and technical concepts contained herein are proprietary to PICO
 * and may be covered by patents, patents in process, and are protected by trade
 * secret or copyright law. Dissemination of this information or reproduction of
 * this material is strictly forbidden unless prior written permission is obtained
 * from PICO.
 */

package com.pico.spatial.sample.features.spatialml.facedetection

import android.content.Context
import android.os.SystemClock
import android.util.Log
import com.pico.spatial.ml.securemr.GlobalTensor
import com.pico.spatial.ml.securemr.Pipeline
import com.pico.spatial.ml.securemr.SceneGraphProperty
import com.pico.spatial.ml.securemr.SpatialMLException
import com.pico.spatial.ml.securemr.SpatialMLInstance
import com.pico.spatial.ml.securemr.SpatialMLSession
import com.pico.spatial.ml.securemr.loadPipelinePackageFromAssets
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class FaceDetectionPipeline(context: Context) : AutoCloseable {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var job: Job? = null

    fun start() {
        if (job?.isActive == true) return
        job =
            scope.launch {
                try {
                    startSession()
                } catch (cancellation: CancellationException) {
                    throw cancellation
                } catch (error: SpatialMLException) {
                    Log.e(TAG, "pipeline_error ${error.message}", error)
                } catch (error: IOException) {
                    Log.e(TAG, "pipeline_error ${error.message}", error)
                } catch (error: IllegalStateException) {
                    Log.e(TAG, "pipeline_error ${error.message}", error)
                }
            }
    }

    private suspend fun startSession() {
        val instance = SpatialMLInstance.create(appContext)
        while (currentCoroutineContext().isActive && !instance.ready) {
            delay(READY_POLL_MS)
        }
        val session =
            instance.createSession(
                SpatialMLSession.InitInfo(
                        imageWidth = CAMERA_WIDTH,
                        imageHeight = CAMERA_HEIGHT,
                        containerWidth = PORTAL_WIDTH,
                        containerHeight = PORTAL_HEIGHT,
                        containerDepth = PORTAL_DEPTH,
                        containerType = SpatialMLSession.ContainerType.VOLUMETRIC,
                    )
                    .addPortal()
            ) ?: error("SpatialML session creation returned null")

        val bundle = session.loadPipelinePackageFromAssets(ASSET_ROOT)
        val detectionPipeline =
            bundle.pipelines[DETECTION_PIPELINE_ID]
                ?: error("Pipeline package '$ASSET_ROOT' has no '$DETECTION_PIPELINE_ID' pipeline")
        val displayPipeline =
            bundle.pipelines[DISPLAY_PIPELINE_ID]
                ?: error("Pipeline package '$ASSET_ROOT' has no '$DISPLAY_PIPELINE_ID' pipeline")
        val framePoseTensor =
            bundle.globalTensors[FRAME_POSE_TENSOR]
                ?: error("Display pipeline output '$FRAME_POSE_TENSOR' was not materialized")
        val frameScene =
            bundle.globalTensors[FRAME_GLTF_TENSOR]
                ?: error("Display pipeline output '$FRAME_GLTF_TENSOR' was not materialized")
        val initTask = initializeFrameScene(session, frameScene)
        val framePipeline = createFramePipeline(session, frameScene, framePoseTensor)

        val frameIntervalMs = 1000L / TARGET_FPS
        var frameIndex = 0L
        var waitFor: Pipeline.RunTask? = initTask

        Log.i(
            TAG,
            "spatialml_frame_ready assetRoot=$ASSET_ROOT frameTensor=$FRAME_GLTF_TENSOR " +
                "portal=${PORTAL_WIDTH}x${PORTAL_HEIGHT}x$PORTAL_DEPTH",
        )
        while (currentCoroutineContext().isActive) {
            val startedAt = SystemClock.elapsedRealtime()
            try {
                val detectionTask =
                    detectionPipeline.pipeline.submit(
                        detectionPipeline.submitBindings,
                        null,
                        waitFor,
                    )
                val displayTask =
                    displayPipeline.pipeline.submit(
                        displayPipeline.submitBindings,
                        null,
                        detectionTask,
                    )
                waitFor = framePipeline.submit(emptyMap(), null, displayTask)
                if (frameIndex % FRAME_LOG_INTERVAL == 0L) {
                    Log.i(TAG, "submitted_spatialml_frame frame=$frameIndex")
                }
                frameIndex += 1
            } catch (error: SpatialMLException) {
                Log.w(TAG, "submit_failed frame=$frameIndex error=${error.message}")
                delay(FAILURE_BACKOFF_MS)
            }

            val elapsedMs = SystemClock.elapsedRealtime() - startedAt
            delay((frameIntervalMs - elapsedMs).coerceAtLeast(1L))
        }
    }

    private fun initializeFrameScene(
        session: SpatialMLSession,
        frameScene: GlobalTensor,
    ): Pipeline.RunTask =
        session.newPipeline().run {
            updateSceneGraphProperty(
                frameScene,
                FRAME_ENTITY_PATH,
                SceneGraphProperty.CameraAnchor.Follow,
                newLocalTensor(FRAME_CAMERA_ANCHOR_MATRIX),
            )
            updateSceneGraphProperty(
                frameScene,
                FRAME_ENTITY_PATH,
                SceneGraphProperty.Transform.Scale,
                newLocalTensor(
                    floatArrayOf(INITIAL_FRAME_SCALE, INITIAL_FRAME_SCALE, FRAME_DEPTH_SCALE)
                ),
            )
            switchSceneVisibility(frameScene, newLocalTensor(0xF.toByte()))
            submit(emptyMap(), null, null)
        }

    private fun createFramePipeline(
        session: SpatialMLSession,
        frameScene: GlobalTensor,
        framePoseTensor: GlobalTensor,
    ): Pipeline =
        session.newPipeline().apply {
            updateSceneGraphProperty(
                frameScene,
                FRAME_ENTITY_PATH,
                SceneGraphProperty.CameraAnchor.Follow,
                framePoseTensor,
            )
        }

    override fun close() {
        job?.cancel()
        scope.cancel()
    }

    private companion object {
        private const val TAG = "FaceDetectionPipeline"
        private const val ASSET_ROOT = "SpatialML/face-mediapipe-pipeline"
        private const val DETECTION_PIPELINE_ID = "detection"
        private const val DISPLAY_PIPELINE_ID = "display"
        private const val FRAME_GLTF_TENSOR = "frame_gltf"
        private const val FRAME_POSE_TENSOR = "frame_pose"
        private const val FRAME_ENTITY_PATH = "/"
        private const val CAMERA_WIDTH = 580
        private const val CAMERA_HEIGHT = 326
        private const val PORTAL_WIDTH = 1000
        private const val PORTAL_HEIGHT = 1000
        private const val PORTAL_DEPTH = 10
        private const val FRAME_DEPTH_SCALE = 0.001f
        private const val INITIAL_FRAME_SCALE = 0.02f
        private const val INITIAL_FRAME_Z = -6.0f
        private val FRAME_CAMERA_ANCHOR_MATRIX =
            floatArrayOf(
                1.0f,
                0.0f,
                0.0f,
                0.0f,
                0.0f,
                1.0f,
                0.0f,
                0.0f,
                0.0f,
                0.0f,
                1.0f,
                INITIAL_FRAME_Z,
                0.0f,
                0.0f,
                0.0f,
                1.0f,
            )
        private const val TARGET_FPS = 15
        private const val READY_POLL_MS = 100L
        private const val FAILURE_BACKOFF_MS = 100L
        private const val FRAME_LOG_INTERVAL = 30L
    }
}
