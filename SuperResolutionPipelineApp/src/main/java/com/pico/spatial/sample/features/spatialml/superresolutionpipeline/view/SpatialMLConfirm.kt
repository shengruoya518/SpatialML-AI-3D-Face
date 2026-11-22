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

package com.pico.spatial.sample.features.spatialml.superresolutionpipeline.view

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pico.spatial.sample.features.spatialml.superresolutionpipeline.vm.SrViewModel
import com.pico.spatial.ui.design.Button
import com.pico.spatial.ui.design.ButtonDefaults.buttonColors
import com.pico.spatial.ui.design.Text
import com.pico.spatial.ui.design.windows.Sheet

/**
 * A sheet GUI (a smaller floating dialogue-like window) to ask the user to confirm the SpatialML
 * mode. The reason for this confirmation is that
 * 1. SpatialML's GUI is less convenient from a user's perspective, and that
 * 1. We explain what is SpatialML and how it protects user's privacy.
 *
 * This UI should only be displayed if user choose the app to run in SpatialML mode.
 *
 * @param srViewModel the viewmodel. On confirmation of the camera access, [SrViewModel.appMode]
 *   turns from [SrViewModel.AppMode.SECURE_MR] to [SrViewModel.AppMode.SECURE_MR_CONFIRMED].
 */
@Preview
@Composable
fun SpatialMLConfirm(srViewModel: SrViewModel = viewModel()) {
    Sheet(
        title = {
            Text(
                "SpatialML mode",
                textAlign = TextAlign.Center,
                fontSize = 5.em,
                softWrap = false,
                modifier = Modifier.padding(start = 10.dp, end = 10.dp, top = 20.dp, bottom = 8.dp),
            )
        },
        leadingAction = null,
        onDismissRequest = { srViewModel.updateAppMode(SrViewModel.AppMode.NO_SELECTION) },
        bottom = {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceAround,
            ) {
                Button(
                    onClick = { srViewModel.updateAppMode(SrViewModel.AppMode.NO_SELECTION) },
                    modifier = Modifier.padding(12.dp),
                    colors = buttonColors(Color.White),
                ) {
                    Text("Deny", color = Color.Black)
                }
                Button(
                    onClick = {
                        srViewModel.updateAppMode(SrViewModel.AppMode.SECURE_MR_CONFIRMED)
                    },
                    modifier = Modifier.padding(12.dp),
                    colors = buttonColors(Color.Black),
                ) {
                    Text("Confirm", color = Color.White)
                }
            }
        },
    ) {
        Text(
            "In SpatialML mode, the camera data will be processed securely by PICO OS." +
                " PICO OS will not give the app any camera data. The zoomed camera images" +
                " will be shown in a separated system window, isolated from the app to" +
                " guarantee the privacy protection. User experience might be slightly" +
                " impacted.",
            textAlign = TextAlign.Justify,
            fontSize = 3.em,
            softWrap = true,
            modifier = Modifier.padding(start = 10.dp, end = 10.dp, top = 20.dp, bottom = 8.dp),
        )
    }
}
