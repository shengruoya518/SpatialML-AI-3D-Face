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

package com.pico.spatial.sample.features.spatialml

import android.util.Log
import com.pico.spatial.ml.securemr.Pipeline
import com.pico.spatial.ml.securemr.PipelinePackageBundle
import com.pico.spatial.ml.securemr.SpatialMLException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Submits a named JSON pipeline with the placeholder bindings supplied by the package loader. */
class LoadedPipelineRunner(
    private val scope: CoroutineScope,
    private val bundle: Deferred<PipelinePackageBundle>,
    private val pipelineId: String,
) {
    private val updates = Mutex()

    fun runOnceAfterValueReset(
        prevTask: Deferred<Pipeline.RunTask>? = null,
        valueResetter: (PipelinePackageBundle) -> Unit = {},
    ): Deferred<Pipeline.RunTask> =
        scope.async(Dispatchers.IO) {
            val packageBundle = bundle.await()
            val loaded = packageBundle.pipelines.getValue(pipelineId)
            val waitFor = prevTask?.await()
            updates.withLock {
                valueResetter(packageBundle)
                loaded.pipeline.submit(loaded.submitBindings, null, waitFor)
            }
        }

    fun runContinuously(frequency: Int, startAfter: Deferred<Pipeline.RunTask>? = null) =
        scope.launch(Dispatchers.IO) {
            require(frequency in 1..1000)
            val loaded = bundle.await().pipelines.getValue(pipelineId)
            var waitFor = startAfter?.await()
            var failureAllowance = MAX_SUCCESSIVE_SUBMISSION_FAILURES
            while (isActive && failureAllowance > 0) {
                try {
                    loaded.pipeline.submit(loaded.submitBindings, null, waitFor)
                    failureAllowance = MAX_SUCCESSIVE_SUBMISSION_FAILURES
                } catch (exception: SpatialMLException) {
                    failureAllowance -= 1
                    Log.w(
                        TAG,
                        "Pipeline '$pipelineId' submission failed " +
                            "(${MAX_SUCCESSIVE_SUBMISSION_FAILURES - failureAllowance}/" +
                            "$MAX_SUCCESSIVE_SUBMISSION_FAILURES)",
                        exception,
                    )
                }
                waitFor = null
                delay(1000L / frequency)
            }
        }

    private companion object {
        const val TAG = "SpatialML"
        const val MAX_SUCCESSIVE_SUBMISSION_FAILURES = 5
    }
}
