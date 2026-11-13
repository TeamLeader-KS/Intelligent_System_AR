package com.example.intelligent_system_ar.ui.component

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.example.intelligent_system_ar.data.model.ScanResult
import com.example.intelligent_system_ar.ui.theme.ArOutline
import com.example.intelligent_system_ar.ui.theme.ArSurface
import com.example.intelligent_system_ar.ui.theme.ArTextPrimary
import com.example.intelligent_system_ar.ui.theme.ArTextSecondary
import com.example.intelligent_system_ar.ui.theme.statusColor

/** Карточка оборудования. Тап по карточке — свернуть/развернуть рекомендации. */
@Composable
fun ResultCard(result: ScanResult, modifier: Modifier = Modifier) {
    val color = result.status.statusColor()
    var expanded by remember(result) { mutableStateOf(true) }
    val shape = RoundedCornerShape(20.dp)
    val recommendations = result.defects.mapNotNull { it.recommendation }

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .clip(shape)
            .clickable { expanded = !expanded },
        shape = shape,
        color = ArSurface.copy(alpha = 0.95f),
        border = BorderStroke(1.dp, color.copy(alpha = 0.55f))
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = result.equipmentName,
                    color = ArTextPrimary,
                    style = MaterialTheme.typography.titleMedium
                )
                StatusBadge(result.status)
            }

            result.primaryDefect?.let {
                Spacer(Modifier.height(6.dp))
                Text(text = it.title, color = color, style = MaterialTheme.typography.bodyLarge)
            }

            AnimatedVisibility(visible = expanded && recommendations.isNotEmpty()) {
                Column {
                    Spacer(Modifier.height(12.dp))
                    Box(Modifier.fillMaxWidth().height(1.dp).background(ArOutline))
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text = "Рекомендация",
                        color = ArTextSecondary,
                        style = MaterialTheme.typography.labelMedium
                    )
                    Spacer(Modifier.height(4.dp))
                    recommendations.forEach {
                        Text(text = it, color = ArTextPrimary, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}
