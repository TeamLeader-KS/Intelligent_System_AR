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
import com.example.intelligent_system_ar.ui.theme.ArClearButton
import com.example.intelligent_system_ar.ui.theme.ArOnAccent
import com.example.intelligent_system_ar.ui.theme.ArSurfaceHigh
import com.example.intelligent_system_ar.ui.theme.ArTextSecondary

/** Имя файла в res/drawable БЕЗ расширения. Android требует маленькие буквы: screen_cleaning.png */
private const val CLEAR_ICON_NAME = "screen_cleaning"

/** Отступ картинки от краёв кнопки. 0.dp — картинка занимает кнопку целиком. */
private val CLEAR_ICON_PADDING = 0.dp

/** FillBounds — растянуть на всю кнопку. Crop — заполнить без искажения (края обрежутся). Fit — вписать с полями. */
private val CLEAR_ICON_SCALE = ContentScale.FillBounds

/**
 * Кнопка «Очистить экран».
 * Фон — бледно-оранжевый. Если картинки screen_cleaning нет или она не загрузилась,
 * кнопка остаётся просто оранжевой с крестиком — приложение не падает.
 */
@Composable
fun ClearScreenButton(
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val icon = rememberDrawableBitmap(CLEAR_ICON_NAME)

    Button(
        onClick = onClick,
        enabled = enabled,
        shape = RoundedCornerShape(16.dp),
        contentPadding = PaddingValues(0.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = ArClearButton,
            contentColor = ArOnAccent,
            disabledContainerColor = ArSurfaceHigh,
            disabledContentColor = ArTextSecondary
        ),
        modifier = modifier
    ) {
        if (icon != null) {
            Image(
                bitmap = icon,
                contentDescription = "Очистить экран",
                contentScale = CLEAR_ICON_SCALE,
                alpha = if (enabled) 1f else 0.4f,
                modifier = Modifier.fillMaxSize().padding(CLEAR_ICON_PADDING)
            )
        } else {
            Text("✕", style = MaterialTheme.typography.titleMedium)
        }
    }
}
