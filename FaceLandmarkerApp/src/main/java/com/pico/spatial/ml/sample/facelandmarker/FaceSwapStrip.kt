// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.pico.spatial.ui.design.Button
import com.pico.spatial.ui.design.Icon
import com.pico.spatial.ui.design.PicoTheme
import com.pico.spatial.ui.design.Text
import com.pico.spatial.ui.design.ToggleButton
import com.pico.spatial.ui.design.ToggleButtonDefaults
import com.pico.spatial.ui.foundation.material.backgroundMaterial
import com.pico.spatial.ui.platform.Material

internal class FaceSwapChoice(val effect: FaceEffect, val name: String, val icon: ImageVector)

internal val FaceSwapChoices =
    listOf(
        FaceSwapChoice(FaceEffect.HELMET, "钢铁侠头盔", FaceSwapIcons.helmet),
        FaceSwapChoice(FaceEffect.EYES, "大眼咧嘴", FaceSwapIcons.eyes),
        FaceSwapChoice(FaceEffect.HAT, "棒球帽", FaceSwapIcons.cap),
        FaceSwapChoice(FaceEffect.FLAG, "脸颊国旗", FaceSwapIcons.flag),
        FaceSwapChoice(FaceEffect.DRAGON, "中国龙", FaceSwapIcons.dragon),
    )

/**
 * The whole face-swap UI: one glass strip of effects, then pause and re-target. [hint] is the only
 * status line and is absent while an effect is on a face. [action] replaces the two bottom buttons
 * when the app is blocked on the wearer, e.g. the camera permission.
 */
@Composable
internal fun FaceSwapStrip(
    selected: FaceEffect,
    enabled: Boolean,
    paused: Boolean,
    hint: String?,
    action: Pair<String, () -> Unit>?,
    onSelect: (FaceEffect) -> Unit,
    onPause: () -> Unit,
    onSwitchPerson: () -> Unit,
) {
    Column(
        Modifier.size(600.dp, 236.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Fixed slot: the strip must not jump when the hint comes and goes.
        Box(Modifier.height(40.dp), contentAlignment = Alignment.Center) {
            if (hint != null)
                Box(
                    Modifier.clip(RoundedCornerShape(20.dp))
                        .backgroundMaterial(enable = true, style = Material.Regular)
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                ) {
                    Text(
                        hint,
                        style = PicoTheme.typography.bodyMedium,
                        color = PicoTheme.colorScheme.labelPrimary,
                    )
                }
        }
        Row(
            Modifier.clip(RoundedCornerShape(32.dp))
                .backgroundMaterial(enable = true, style = Material.Regular)
                .padding(8.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            for (choice in FaceSwapChoices) ToggleButton(
                checked = choice.effect == selected,
                onCheckedChange = { if (it) onSelect(choice.effect) },
                enabled = enabled,
                size = ToggleButtonDefaults.toggleButtonSize(width = 108.dp, height = 92.dp),
                contentPadding = PaddingValues(4.dp),
                shape = RoundedCornerShape(24.dp),
            ) {
                Column(
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Icon(choice.icon, contentDescription = null, modifier = Modifier.size(34.dp))
                    Text(choice.name, style = PicoTheme.typography.bodyMedium, maxLines = 1)
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (action != null) {
                Button(onClick = action.second) { Text(action.first) }
            } else {
                Button(
                    onClick = onPause,
                    enabled = enabled,
                    leadingIcon = {
                        Icon(
                            if (paused) FaceSwapIcons.play else FaceSwapIcons.pause,
                            contentDescription = null,
                        )
                    },
                ) {
                    Text(if (paused) "继续" else "暂停")
                }
                Button(
                    onClick = onSwitchPerson,
                    enabled = enabled && !paused,
                    leadingIcon = { Icon(FaceSwapIcons.swap, contentDescription = null) },
                ) {
                    Text("换一个人")
                }
            }
        }
    }
}
