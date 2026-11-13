package com.example.intelligent_system_ar.ui.component

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import com.example.intelligent_system_ar.ui.theme.ArAccent
import com.example.intelligent_system_ar.ui.theme.ArOnAccent
import com.example.intelligent_system_ar.ui.theme.ArSurfaceHigh
import com.example.intelligent_system_ar.ui.theme.ArTextSecondary

/** Имя файла в res/drawable БЕЗ расширения. Android требует маленькие буквы: scanning.png */
private const val SCAN_ICON_NAME = "scanning"

/** Отступ картинки от краёв кнопки. 0.dp — картинка занимает кнопку целиком. */
private val SCAN_ICON_PADDING = 0.dp

/** FillBounds — растянуть на всю кнопку. Crop — заполнить без искажения (края обрежутся). Fit — вписать с полями. */
private val SCAN_ICON_SCALE = ContentScale.FillBounds

@Composable
fun ScanButton(
    isScanning: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val icon = rememberDrawableBitmap(SCAN_ICON_NAME)

    Button(
        onClick = onClick,
        enabled = enabled,
        shape = RoundedCornerShape(16.dp),
        contentPadding = PaddingValues(0.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = ArAccent,
            contentColor = ArOnAccent,
            disabledContainerColor = ArSurfaceHigh,
            disabledContentColor = ArTextSecondary
        ),
        modifier = modifier
    ) {
        if (icon != null) {
            Image(
                bitmap = icon,
                contentDescription = "Сканировать",
                contentScale = SCAN_ICON_SCALE,
                alpha = if (enabled) 1f else 0.4f, // во время анализа кнопка бледнеет
                modifier = Modifier.fillMaxSize().padding(SCAN_ICON_PADDING)
            )
        } else {
            Text(
                text = if (isScanning) "Анализ…" else "Сканировать",
                style = MaterialTheme.typography.labelLarge
            )
        }
    }
}
