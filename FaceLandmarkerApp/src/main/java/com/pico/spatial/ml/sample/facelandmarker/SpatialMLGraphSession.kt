// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.content.Context
import android.os.SharedMemory
import com.bytedance.pico.openmr.spatial.pack.SSMRJNIWrapper
import com.bytedance.pico.openmr.spatial.pack.SSMRJNIWrapper.PipelineJNIWrapper
import com.bytedance.pico.openmr.spatial.pack.utils.ModelEncoding
import com.bytedance.pico.openmr.spatial.pack.utils.PipelineTensorMap
import java.nio.ByteOrder

/**
 * Owns the public native bindings shipped with Spatial SDK 6.1.9. Its fluent Pipeline API omits
 * CameraSpaceToWorld, so this sample uses the same bindings directly, without accessing SDK
 * internals. All handles stay on the inference coroutine; children are destroyed before the
 * zero-sized session.
 */
internal class SpatialMLGraphSession : AutoCloseable {
    private val session = SSMRJNIWrapper.createSessionHandle(0, WIDTH, HEIGHT, 0, 0, 0)
    private val globals = mutableListOf<GraphTensor>()
    private val pipelines = mutableListOf<GraphPipeline>()
    private var closed = false

    init {
        check(session != 0L) { "SpatialML rejected the zero-sized session" }
    }

    fun global(rows: Int, columns: Int, values: FloatArray? = null): GraphTensor {
        val tensor =
            GraphTensor(
                SSMRJNIWrapper.createTensor(session, FLOAT_MATRIX, intArrayOf(rows, columns)),
                FLOAT_MATRIX,
                intArrayOf(rows, columns),
                true,
            )
        check(tensor.id != 0L)
        globals.add(tensor)
        reset(tensor, values ?: FloatArray(rows * columns))
        return tensor
    }

    fun globalImage(width: Int = WIDTH, height: Int = HEIGHT, float: Boolean = false): GraphTensor {
        val flag = if (float) FLOAT_IMAGE else BYTE_IMAGE
        val tensor =
            GraphTensor(
                SSMRJNIWrapper.createTensor(session, flag, intArrayOf(height, width)),
                flag,
                intArrayOf(height, width),
                true,
            )
        check(tensor.id != 0L)
        globals.add(tensor)
        return tensor
    }

    fun globalTimestamp(): GraphTensor {
        val tensor =
            GraphTensor(
                SSMRJNIWrapper.createTensor(session, TIMESTAMP, intArrayOf(1)),
                TIMESTAMP,
                intArrayOf(1),
                true,
            )
        check(tensor.id != 0L)
        globals.add(tensor)
        return tensor
    }

    fun pipeline(context: Context): GraphPipeline =
        GraphPipeline(PipelineJNIWrapper.create(session), context).also { pipelines.add(it) }

    fun reset(tensor: GraphTensor, values: FloatArray) {
        check(!closed)
        require(values.size == tensor.shape.fold(1, Int::times))
        withFloats(values) { SSMRJNIWrapper.resetTensor(tensor.id, it) }
    }

    fun read(tensor: GraphTensor, size: Int): FloatArray =
        SSMRJNIWrapper.readbackSharedMemory(tensor.id).use { memory ->
            val buffer = memory.mapReadOnly()
            try {
                check(buffer.remaining() == size * Float.SIZE_BYTES) {
                    "SpatialML result readback has ${buffer.remaining()} bytes; expected ${size * Float.SIZE_BYTES}"
                }
                FloatArray(size).also {
                    buffer.order(ByteOrder.nativeOrder()).asFloatBuffer().get(it)
                }
            } finally {
                SharedMemory.unmap(buffer)
            }
        }

    fun readBytes(tensor: GraphTensor, size: Int): ByteArray =
        SSMRJNIWrapper.readbackSharedMemory(tensor.id).use { memory ->
            val buffer = memory.mapReadOnly()
            try {
                check(buffer.remaining() == size) {
                    "Incomplete image readback: ${buffer.remaining()} / $size bytes"
                }
                ByteArray(size).also { buffer.get(it) }
            } finally {
                SharedMemory.unmap(buffer)
            }
        }

    override fun close() {
        if (closed) return
        closed = true
        // Attempt every release even if a disconnected service rejects an individual handle.
        pipelines.asReversed().forEach { runCatching { it.close() } }
        globals.asReversed().forEach { runCatching { SSMRJNIWrapper.destroyTensor(it.id) } }
        runCatching { SSMRJNIWrapper.destroySessionHandle(session) }
        pipelines.clear()
        globals.clear()
    }

    class GraphTensor(
        val id: Long,
        val flag: Int,
        val shape: IntArray,
        val global: Boolean = false,
    )

    class GraphPipeline(private val id: Long, private val context: Context) : AutoCloseable {
        private val mappings = PipelineTensorMap.create()
        private val references = mutableMapOf<Long, Long>()
        private var closed = false

        init {
            check(id != 0L && mappings != 0L)
        }

        fun floats(rows: Int, columns: Int, values: FloatArray? = null): GraphTensor =
            local(FLOAT_MATRIX, intArrayOf(rows, columns)).also { tensor ->
                values?.let {
                    require(it.size == rows * columns)
                    withFloats(it) { memory ->
                        PipelineJNIWrapper.resetTensor(id, tensor.id, memory)
                    }
                }
            }

        fun image(size: Int, float: Boolean = false): GraphTensor =
            local(if (float) FLOAT_IMAGE else BYTE_IMAGE, intArrayOf(size, size))

        fun timestamp(): GraphTensor = local(TIMESTAMP, intArrayOf(1))

        private fun local(flag: Int, shape: IntArray): GraphTensor =
            GraphTensor(PipelineJNIWrapper.createTensor(id, flag, shape, true), flag, shape).also {
                check(it.id != 0L)
            }

        private fun binding(tensor: GraphTensor): Long {
            if (!tensor.global) return tensor.id
            return references.getOrPut(tensor.id) {
                PipelineJNIWrapper.createTensor(id, tensor.flag, tensor.shape, false).also {
                    check(it != 0L)
                    PipelineTensorMap.add(mappings, it, tensor.id)
                }
            }
        }

        fun op(
            type: Int,
            inputs: List<GraphTensor>,
            outputs: List<GraphTensor>,
            config: String? = null,
        ) {
            val operator = PipelineJNIWrapper.addOperator(id, type, config)
            check(operator != 0L) { "SpatialML rejected operator $type" }
            inputs.forEachIndexed { index, tensor ->
                PipelineJNIWrapper.setOperand(operator, binding(tensor), index)
            }
            outputs.forEachIndexed { index, tensor ->
                PipelineJNIWrapper.setResult(operator, binding(tensor), index)
            }
        }

        fun namedOp(
            type: Int,
            inputs: Map<String, GraphTensor>,
            outputs: Map<String, GraphTensor>,
            config: String? = null,
        ) {
            val operator = PipelineJNIWrapper.addOperator(id, type, config)
            check(operator != 0L) { "SpatialML rejected operator $type" }
            inputs.forEach { (name, tensor) ->
                PipelineJNIWrapper.setOperand(operator, binding(tensor), name)
            }
            outputs.forEach { (name, tensor) ->
                PipelineJNIWrapper.setResult(operator, binding(tensor), name)
            }
        }

        fun script(
            name: String,
            inputs: Map<String, GraphTensor>,
            outputs: Map<String, GraphTensor>,
        ) {
            val script =
                context.assets.open("$ASSETS/operators/$name.js").bufferedReader().use {
                    it.readText()
                }
            namedOp(JAVASCRIPT, inputs, outputs, script)
        }

        fun model(
            name: String,
            inputs: Map<String, GraphTensor>,
            outputs: Map<String, GraphTensor>,
            backend: Int,
            inputEncodings: Map<String, ModelEncoding.EncodingType> = emptyMap(),
        ) {
            require(inputEncodings.keys.all { it in inputs })
            val encoding = ModelEncoding.create()
            try {
                inputs.keys.forEach {
                    ModelEncoding.add(
                        encoding,
                        true,
                        it,
                        null,
                        inputEncodings[it]
                            ?: if (inputs.getValue(it).flag == TIMESTAMP) {
                                ModelEncoding.EncodingType.INT32
                            } else {
                                ModelEncoding.EncodingType.FLOATING_POINT32
                            },
                    )
                }
                outputs.keys.forEach {
                    ModelEncoding.add(
                        encoding,
                        false,
                        it,
                        null,
                        ModelEncoding.EncodingType.FLOATING_POINT32,
                    )
                }
                val bytes = context.assets.open("$ASSETS/model/$name.tflite").use { it.readBytes() }
                SharedMemory.create(name, bytes.size).use { memory ->
                    val buffer = memory.mapReadWrite()
                    try {
                        buffer.put(bytes)
                    } finally {
                        SharedMemory.unmap(buffer)
                    }
                    val operator =
                        PipelineJNIWrapper.addModelInference(id, name, memory, encoding, 1, backend)
                    check(operator != 0L) { "SpatialML rejected model $name" }
                    inputs.values.forEachIndexed { index, tensor ->
                        PipelineJNIWrapper.setOperand(operator, binding(tensor), index)
                    }
                    outputs.values.forEachIndexed { index, tensor ->
                        PipelineJNIWrapper.setResult(operator, binding(tensor), index)
                    }
                }
            } finally {
                ModelEncoding.destroy(encoding)
            }
        }

        fun preprocess(
            image: GraphTensor,
            affine: GraphTensor,
            sampledRgb: GraphTensor? = null,
            detector: Boolean = false,
            retainedFloatCrop: GraphTensor? = null,
        ): GraphTensor {
            // A calibration frame may retain both normalized model input and diagnostic bytes.
            // The byte copy below comes from this same normalized crop on the GPU path.
            val result = retainedFloatCrop ?: image(256, float = true)
            if (!BuildConfig.FACE_GPU_PREPROCESSING) {
                val crop = sampledRgb ?: image(256)
                op(APPLY_AFFINE, listOf(affine, image), listOf(crop))
                op(ASSIGNMENT, listOf(crop), listOf(result))
                op(ARITHMETIC, listOf(result), listOf(result), "{0} / 255.0")
                return result
            }
            // Keep preprocessing on the GPU independently of the trained models' backend.
            // The model preserves RGB, inverse affine mapping and byte-rounded sampling.
            // Device validation must establish full-precision GPU coordinates before promotion.
            val modelName =
                if (image.shape[0] == LANDMARK_TILE_SIZE && image.shape[1] == LANDMARK_TILE_SIZE) {
                    "landmark_preprocess_tile_rgb_gpu"
                } else if (BuildConfig.FACE_GPU_SAMPLE_BYTES) {
                    if (detector) "detector_preprocess_rgb_gpu" else "landmark_preprocess_rgb_gpu"
                } else {
                    if (detector) "detector_preprocess_gpu" else "landmark_preprocess_gpu"
                }
            model(
                modelName,
                mapOf("image" to image, "affine" to affine),
                mapOf("model_input" to result),
                PREPROCESSING_BACKEND,
                mapOf("image" to ModelEncoding.EncodingType.UNSIGNED_FIXED_POINT8),
            )
            // Save exactly the same rounded crop which the model normalized. Keep the original
            // byte-image export contract; regular tracking does not need this diagnostic copy.
            sampledRgb?.let {
                val crop = image(256, float = true)
                // The model rounds before /255. Add half before native truncating conversion
                // to recover the same integer byte despite float normalization roundoff.
                op(ARITHMETIC, listOf(result), listOf(crop), "{0} * 255.0 + 0.5")
                op(ASSIGNMENT, listOf(crop), listOf(it))
            }
            return result
        }

        /** Convert only an already sampled RGB detector image to the model's float range. */
        fun normalizeRgb(image: GraphTensor): GraphTensor {
            require(image.shape[0] == 256 && image.shape[1] == 256)
            val result = image(256, float = true)
            op(ASSIGNMENT, listOf(image), listOf(result))
            op(ARITHMETIC, listOf(result), listOf(result), "{0} / 255.0")
            return result
        }

        /**
         * Resample square VST rows to the logical 336x256 view, then center crop in one GPU call.
         */
        fun compactDetectorInput(
            image: GraphTensor,
            retainedFloatCrop: GraphTensor? = null,
        ): GraphTensor {
            require(
                image.shape.contentEquals(
                    intArrayOf(CompactFaceDetector.VST_SIZE, CompactFaceDetector.VST_SIZE)
                )
            )
            val result = retainedFloatCrop ?: image(256, float = true)
            model(
                "detector_compact_preprocess_gpu",
                mapOf("image" to image),
                mapOf("model_input" to result),
                PREPROCESSING_BACKEND,
                mapOf("image" to ModelEncoding.EncodingType.UNSIGNED_FIXED_POINT8),
            )
            return result
        }

        fun submit(waitFor: Long = 0): Long {
            check(!closed)
            return PipelineJNIWrapper.submit(id, waitFor, 0, mappings).also {
                check(it != 0L) { "SpatialML rejected a face frame" }
            }
        }

        override fun close() {
            if (closed) return
            closed = true
            try {
                PipelineJNIWrapper.destroy(id)
            } finally {
                PipelineTensorMap.destroy(mappings)
            }
        }
    }

    companion object {
        const val WIDTH = 3248
        const val HEIGHT = 2464
        const val LANDMARK_TILE_SIZE = 768
        const val ASSETS = "SpatialML/face-landmarker"
        // Native tensor ABI: dtype | usage | channels, matching the SDK Tensor.InitInfo contract.
        private const val FLOAT_MATRIX = (1 shl 14) or (1 shl 18) or (1 shl 11) or 1
        private const val FLOAT_IMAGE = (1 shl 14) or (1 shl 18) or (1 shl 11) or 3
        private const val BYTE_IMAGE = (1 shl 12) or (1 shl 16) or (1 shl 11) or 3
        private const val TIMESTAMP = (1 shl 14) or (1 shl 17) or (1 shl 10) or 4
        const val ARITHMETIC = 1
        const val APPLY_AFFINE = 15
        const val ASSIGNMENT = 18
        const val CAMERA_TO_WORLD = 22
        const val VST = 23
        const val RETAINED_VST_ACCESS = 43
        const val RETAINED_VST_ROI = 44
        const val RETAINED_VST_AFFINE = 45
        const val SVD = 34
        const val JAVASCRIPT = 39
        const val PREPROCESSING_BACKEND = 1

        private inline fun withFloats(values: FloatArray, action: (SharedMemory) -> Unit) {
            SharedMemory.create("face-landmarker-floats", values.size * Float.SIZE_BYTES).use {
                memory ->
                val buffer = memory.mapReadWrite()
                try {
                    buffer.order(ByteOrder.nativeOrder()).asFloatBuffer().put(values)
                } finally {
                    SharedMemory.unmap(buffer)
                }
                action(memory)
            }
        }
    }
}
