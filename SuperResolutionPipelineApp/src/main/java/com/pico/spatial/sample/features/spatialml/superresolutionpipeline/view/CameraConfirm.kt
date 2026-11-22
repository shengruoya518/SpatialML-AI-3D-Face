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
 * A sheet GUI (a smaller floating dialogue-like window) to ask the user to confirm that camera data
 * will be given to the app, because RelaxMR mode will give the app permission to access the camera.
 *
 * This UI should only be displayed if user choose the app to run in RelaxMR mode.
 *
 * @param srViewModel the viewmodel. On confirmation of the camera access, [SrViewModel.appMode]
 *   turns from [SrViewModel.AppMode.RELAX_MR] to [SrViewModel.AppMode.RELAX_MR_CONFIRMED].
 */
@Preview
@Composable
fun CameraConfirm(srViewModel: SrViewModel = viewModel()) {

    Sheet(
        title = {
            Text(
                "RelaxMR mode",
                textAlign = TextAlign.Center,
                fontSize = 5.em,
                softWrap = false,
                modifier = Modifier.padding(start = 10.dp, end = 10.dp, top = 20.dp, bottom = 8.dp),
            )
        },
        leadingAction = null,
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
                    onClick = { srViewModel.updateAppMode(SrViewModel.AppMode.RELAX_MR_CONFIRMED) },
                    modifier = Modifier.padding(12.dp),
                    colors = buttonColors(Color.Black),
                ) {
                    Text("Confirm", color = Color.White)
                }
            }
        },
        onDismissRequest = { srViewModel.updateAppMode(SrViewModel.AppMode.NO_SELECTION) },
    ) {
        Text(
            "In RelaxMR mode, app will request the zoomed camera image from SpatialML" +
                " framework. The app will only proceed if you grant the permission to access" +
                " the camera data.",
            textAlign = TextAlign.Justify,
            fontSize = 3.em,
            softWrap = true,
            modifier = Modifier.padding(start = 10.dp, end = 10.dp, top = 20.dp, bottom = 8.dp),
        )
    }
}
