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

import android.content.Context
import android.os.SharedMemory
import android.util.Log
import java.io.IOException
import java.nio.channels.Channels

/**
 * Helper function: load asset file to shared memory for SpatialML usage.
 *
 * @param appContext the app context.
 * @param assetName the path of the asset in the app's asset directory.
 * @param loader the callback after the loading is completed.
 */
@Suppress("NestedBlockDepth", "EmptyWhileBlock")
fun loadAssetToSharedMemory(
    appContext: Context,
    assetName: String,
    loader: (SharedMemory) -> Unit,
) {
    Log.i("SpatialML", "loading asset from SpatialML/$assetName")
    appContext.assets.open("SpatialML/$assetName").use { inputStream ->
        val size = inputStream.available()
        SharedMemory.create("gltf_scene_from$assetName", size).use { mem ->
            val buffer = mem.mapReadWrite()
            try {
                Channels.newChannel(inputStream).use { fileChannel ->
                    while (fileChannel.read(buffer) > 0) {}
                }
            } catch (e: IOException) {
                mem.close()
                throw e
            } finally {
                buffer.rewind()
                SharedMemory.unmap(buffer)
            }
            Log.i("SpatialML", "asset $assetName has been loaded of $size bytes")
            loader(mem)
        }
    }
}
