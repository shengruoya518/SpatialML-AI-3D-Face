# DynamicTexture feasibility for face tracking — 2026-11-01

Some image tensors can use DynamicTexture, but converting the current graph broadly does not establish a GPU-resident computation path. In the inspected local service, DynamicTexture has GPU-accessible backing: an AHardwareBuffer in the Spatial renderer and a Vulkan image in the XR renderer. Both expose CPU mapping. VST still writes pixels through CPU-accessible matrices, and the LiteRT wrapper still copies input/output bytes into/out of its separately allocated buffers. The changed backing can add renderer map/unmap synchronization without removing those copies. These findings describe the local checkout; its equivalence to the installed service is unverified.

## Follow-up: keep images on GPU until the next consumer needs CPU access — 2026-11-02

The intended path is camera hardware buffer → GPU copy/import into a DynamicTexture → GPU affine/crop → compatible LiteRT GPU input. The detector and landmark preprocessing stages should reuse the same retained camera image with their respective affines. If the next model requires CPU access, expose only its cropped input at that boundary inside the SpatialML service. For NPU consumers, use compatible shared buffers where supported; otherwise stage only the cropped input. A CPU boundary does not require an app readback/upload round trip.

For this graph, one full RGB8 image is 24,009,216 bytes. A 256×256 crop is 196,608 bytes as RGB8 or 786,432 bytes as RGB FP32. Moving only that crop avoids transferring the full image at the model boundary. The actual benefit depends on layout conversion, synchronization and buffer-sharing support; these byte counts are not measured transfer times.

The follow-up traced both renderer implementations in local OpenMR checkout `17f060be` (with existing unrelated changes preserved):

- `SpatialClient/src/SSMRInterface.cpp:545` allocates DynamicTexture as an AHardwareBuffer with GPU sampling and CPU access usage flags; `:609` maps it using `AHardwareBuffer_lock`. The previous blanket description of Vulkan backing was incomplete for the Spatial service.
- `InferenceEngine/src/VSTSession.cpp:230` CPU-locks the camera buffer and `:258`/`:260` copy or convert pixels into the destination matrix. No DynamicTexture-specific GPU camera-copy branch was found in this path.
- `DataPipeline/include/AbstractOperator.h:57`/`:65` acquire CPU access for dynamic tensors resolved through placeholders before calling the operator.
- `Utils/src/TFLiteModel.cpp:251` copies Engine tensor inputs into separate LiteRT buffers even when GPU inference is selected. Direct hardware-buffer/texture binding is not implemented in this inspected execution path.

GPU-backed storage, GPU execution of the camera copy, and direct LiteRT GPU buffer consumption are separate capabilities. The user's proposed GPU-first path is the optimization target; changing the app tensor flag alone does not establish all three in the inspected source. The latest combined benchmark used ordinary BYTE_IMAGE storage for VST and verified GPU model delegation, not direct texture consumption. No new device measurement or app/service implementation change was made for this follow-up.

## Candidate selection

| Tensor/path | Current representation | DynamicTexture suitability | Expected effect with current implementation |
| --- | --- | --- | --- |
| Full camera image | Global 3248×2464 uint8 RGB | Service format mapping allows RGB8; actual device/driver support and row layout need validation | VST still materializes RGB on CPU, then each inference call copies it into LiteRT; no demonstrated copy elimination |
| Detector/landmark byte crops | Global 256×256 uint8 RGB in the lab | Image format candidate, mainly useful if displayed as textures | Export and reconstruction are CPU paths; changing storage does not eliminate those operations |
| Normalized detector/landmark model inputs | Pipeline-local 256×256 three-channel FP32 | Current format mapping excludes RGB FP32; pipeline-local dynamic allocation also rejected | Requires format support, global placeholders and a separate accelerator buffer interop contract |
| Affines, intrinsics, pose, ROI, state, detector scores/boxes, geometry, completion packet | Ordinary numeric vectors/matrices | Keep ordinary tensors; vector/point contracts differ from image contracts, and supported FP32 dynamic format is single-channel depth | Tiny numeric tensors or CPU/JS-consumed data gain no demonstrated benefit from texture storage; mapping adds synchronization |
| Image output displayed on a material or through TextureResource | Global RGB/RGBA uint8 | The established DynamicTexture use case | Texture binding/readback can use the underlying texture handle rather than repeated raw image upload; the face lab currently renders an app-owned mesh rather than an image output |

## What the inspected local service does

`InferenceEngine/include/DataType.h` maps the dynamic flag to R8, RGB8 and RGBA8 for byte types and D32_FLOAT for one-channel FP32. Three-channel FP32 and arbitrary integer-vector types do not gain texture support merely by adding the flag. The public Kotlin example `SuperResolutionApp/.../SrAlgorithmImpl.kt:86` creates a global `DataType.Image.R8G8B8A8_U_DYNAMIC` image for display; that proves a local public display pattern, not float RGB inference interop.

`SSMRClientData::createPipelineTensor` rejects pipeline-local DynamicTexture tensors and directs clients to create a global texture plus a pipeline placeholder. The current graph's normalized model inputs are local tensors, so their conversion would involve more than changing a datatype bit.

`Tensor_Mat::getRawByteArray` lazily allocates the texture and queues a renderer map request, then waits on its future and wraps the result in a `cv::Mat` with a texture row stride. The Spatial renderer maps an AHardwareBuffer; the XR renderer maps Vulkan memory. When the last CPU accessor finishes, `yieldRawByteAccess` queues an unmap. Allocation is lazy/retained; map/unmap occurs with access lifetime. These are CPU access semantics rather than proof that an operator runs on the GPU.

`AbstractOperator::compute` maps dynamic operands/results resolved through placeholders before ordinary operator execution. Native ApplyAffine still calls OpenCV `cv::warpAffine`. VST still executes CPU `RGBA2RGB` or `copyTo`. JS still converts raw tensors to JS arrays and back. Those operator implementations do not turn into GPU kernels when a tensor becomes a texture.

`Operator_RunModelInference::compute` maps dynamic inputs/results as well. `TFLiteModel::executeInference` creates/uses separate LiteRT-managed buffers, obtains input bytes, performs memcpy into LiteRT buffers, invokes the compiled model, and copies output bytes back. There is no DynamicTexture/Vulkan external-memory import branch in this inspected wrapper. Thus the same full RGB input would still be copied separately for detector and landmark preprocessing, even if its Engine backing were a DynamicTexture.

The current generic copy also treats input bytes as packed, while mapped textures expose a row stride. Any prototype must verify or unpack row pitch before claiming matching model inputs; a texture backing is not automatically a tightly packed NHWC buffer.

`Operator_LoadTexture` is the contrasting established rendering path: for DynamicTexture it obtains the Vulkan texture FD and binds it; ordinary tensors pass raw image bytes to the renderer. The same texture should be bound once and updated through its source tensor rather than rebinding each frame.

## What could improve the computation path

The useful optimization is sharing the camera/image allocation through producers and accelerator consumers with a defined layout and synchronization contract. A viable path would be:

1. Import or share the camera AHardwareBuffer into the preprocessing accelerator, preserving sensor timestamp and eye selection.
2. Perform channel selection and crop sampling on the GPU, avoiding full-image CPU RGB materialization where possible.
3. Reuse the same imported image for both separate preprocessing models.
4. Bind compatible preprocessing outputs directly to trained-model inputs where the GPU/NPU buffer requirements allow it; GPU and NPU buffer compatibility needs explicit runtime support. If CPU access is required, map or copy only the cropped input at that boundary inside SpatialML.
5. Read back compact final app-consumed results and generate byte crops only for selected lab exports. Intermediates needed by later SpatialML stages stay inside the service. Keep exact terminal completion/snapshot/packet validation.

This needs actual buffer import/binding support in the service/LiteRT integration. DynamicTexture may be part of that shared-image implementation, but its flag alone does not establish the complete path in the inspected source. No speedup can be assigned until targeted validation demonstrates copy reduction and preserved output validity against the current combined configuration.

## Recommended current choice

Keep numeric tensors in types suited to their consumers. Use DynamicTexture for the camera/preprocessing path once the runtime's GPU camera copy and direct model-buffer binding are established, and expose a small cropped CPU input only when needed. Displayed textures already have a handle-binding path. For this face graph, normalized FP32 RGB format support and pipeline-local allocation constraints also need resolution before direct texture chaining. Lab crop reconstruction remains a separate candidate for conditional export execution; the latest combined run measured 22.46 ms for those operators, as recorded in `COMBINED_RGB_INLINE_BENCHMARK_2026-11-02.md`.

This is a static assessment from the local OpenMR checkout and current Kotlin project; installed native/source equivalence and DynamicTexture device performance were not verified in this follow-up. No tensor types, app/service code or device state were changed. The original November 1 audit's source hashes are retained in `artifacts/facelandmarker/registration-lab/gpu-face-reset-benchmark-20261101-184143/dynamic-texture-source-provenance.json`; they do not establish the installed service revision.
