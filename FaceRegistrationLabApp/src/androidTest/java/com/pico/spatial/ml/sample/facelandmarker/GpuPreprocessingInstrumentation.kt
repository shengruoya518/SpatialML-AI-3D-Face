// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.app.Instrumentation
import android.content.Intent
import android.os.Bundle
import android.os.SharedMemory
import com.bytedance.pico.openmr.spatial.pack.SSMRJNIWrapper
import com.bytedance.pico.openmr.spatial.pack.utils.ModelEncoding
import com.pico.spatial.ml.securemr.SpatialMLInstance
import java.io.File
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject

/** Controlled tensor probe; it never acquires VST or writes a calibration/capture. */
class GpuPreprocessingInstrumentation : Instrumentation() {
    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        start()
    }

    override fun onStart() {
        val report = JSONObject().put("cases", JSONArray())
        val output = File(targetContext.getExternalFilesDir(null), "GpuPreprocessingProbe")
        output.mkdirs()
        try {
            runBlocking {
                // Initialize the same Full Space app/runtime context used by the benchmark.
                // The probe itself uses seeded tensors rather than a camera image.
                startActivitySync(
                    Intent()
                        .setClassName(
                            targetContext.packageName,
                            "com.pico.spatial.ml.sample.facelandmarker.platform.MainActivity",
                        )
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
                delay(8_000)
                val instance = SpatialMLInstance.create(targetContext)
                run {
                    withTimeout(15_000) { while (!instance.ready) delay(50) }
                    SpatialMLGraphSession().use { session ->
                        val source = session.globalImage()
                        val gpu = session.globalImage(256, 256, float = true)
                        val native = session.globalImage(256, 256, float = true)
                        val command = session.global(1, 1)
                        val completed = session.global(1, 1)
                        val affine = session.global(2, 3)
                        fun producer(
                            name: String,
                            model: Boolean,
                        ): SpatialMLGraphSession.GraphPipeline =
                            session.pipeline(targetContext).apply {
                                if (model) {
                                    model(
                                        name,
                                        mapOf("image" to source, "affine" to affine),
                                        mapOf("model_input" to gpu),
                                        SpatialMLGraphSession.PREPROCESSING_BACKEND,
                                        mapOf(
                                            "image" to
                                                ModelEncoding.EncodingType.UNSIGNED_FIXED_POINT8
                                        ),
                                    )
                                } else {
                                    val crop = image(256)
                                    op(
                                        SpatialMLGraphSession.APPLY_AFFINE,
                                        listOf(affine, source),
                                        listOf(crop),
                                    )
                                    op(
                                        SpatialMLGraphSession.ASSIGNMENT,
                                        listOf(crop),
                                        listOf(native),
                                    )
                                    op(
                                        SpatialMLGraphSession.ARITHMETIC,
                                        listOf(native),
                                        listOf(native),
                                        "{0} / 255.0",
                                    )
                                }
                                script(
                                    "lab_capture_marker",
                                    mapOf("command" to command),
                                    mapOf("sequence" to completed),
                                )
                            }
                        val detector = producer("detector_preprocess_gpu", true)
                        val landmark = producer("landmark_preprocess_gpu", true)
                        val reference = producer("native", false)
                        val width = SpatialMLGraphSession.WIDTH
                        val height = SpatialMLGraphSession.HEIGHT
                        val image = ByteArray(width * height * 3)
                        for (y in 0 until height) {
                            for (x in 0 until width) {
                                val i = (y * width + x) * 3
                                image[i] = (x % 256).toByte()
                                image[i + 1] = (y % 256).toByte()
                                image[i + 2] = ((x / 13 + y / 17) % 256).toByte()
                            }
                        }
                        SharedMemory.create("controlled-rgb", image.size).use { memory ->
                            val buffer = memory.mapReadWrite()
                            try {
                                buffer.put(image)
                            } finally {
                                SharedMemory.unmap(buffer)
                            }
                            SSMRJNIWrapper.resetTensor(source.id, memory)
                        }
                        val scale = 256f / width
                        val detectorAffine =
                            floatArrayOf(scale, 0f, 0f, 0f, scale, (256 - scale * height) / 2)
                        fun roi(angle: Float, cx: Float, cy: Float, side: Float): FloatArray {
                            val a = 256 * cos(angle) / side
                            val b = 256 * sin(angle) / side
                            return floatArrayOf(
                                a,
                                b,
                                128 - a * cx - b * cy,
                                -b,
                                a,
                                128 + b * cx - a * cy,
                            )
                        }
                        val cases =
                            listOf(
                                "detector" to detectorAffine,
                                "landmark_center" to roi(0f, 1624f, 1232f, 700f),
                                "landmark_rotation" to roi(.3f, 1624f, 1232f, 900f),
                                "landmark_border" to roi(-.6f, 100f, 120f, 500f),
                            )
                        var sequence = 0
                        for ((name, matrix) in cases) {
                            session.reset(affine, matrix)
                            suspend fun execute(pipeline: SpatialMLGraphSession.GraphPipeline) {
                                sequence += 1
                                session.reset(command, floatArrayOf(sequence.toFloat()))
                                pipeline.submit()
                                withTimeout(15_000) {
                                    while (
                                        session.read(completed, 1)[0] != sequence.toFloat()
                                    ) delay(5)
                                }
                            }
                            execute(reference)
                            val expected = session.read(native, 256 * 256 * 3)
                            execute(if (name == "detector") detector else landmark)
                            val actual = session.read(gpu, expected.size)
                            var maximum = 0f
                            var sum = 0.0
                            var finite = true
                            var range = true
                            for (i in actual.indices) {
                                finite = finite && actual[i].isFinite()
                                range = range && actual[i] in 0f..1f
                                val difference = (actual[i] - expected[i]) * 255
                                maximum = maxOf(maximum, abs(difference))
                                sum += difference.toDouble() * difference
                            }
                            val rms = sqrt(sum / actual.size)
                            report
                                .getJSONArray("cases")
                                .put(
                                    JSONObject()
                                        .put("name", name)
                                        .put("finite", finite)
                                        .put("range", range)
                                        .put(
                                            "maxByteError",
                                            if (maximum.isFinite()) maximum else -1,
                                        )
                                        .put("rmsByteError", if (rms.isFinite()) rms else -1)
                                        .put("reference", "same-source native ApplyAffine /255")
                                        .put(
                                            "accepted",
                                            finite && range && rms < .5 && maximum <= 12,
                                        )
                                )
                        }
                    }
                }
            }
            report.put("completed", true)
        } catch (error: Throwable) {
            report.put("completed", false).put("error", error.toString())
        }
        File(output, "result.json").writeText(report.toString(2))
        val result = Bundle().apply { putString("gpu_probe", report.toString()) }
        finish(if (report.optBoolean("completed")) 0 else 1, result)
    }
}
