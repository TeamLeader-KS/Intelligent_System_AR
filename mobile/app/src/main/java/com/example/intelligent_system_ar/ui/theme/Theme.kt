package com.example.intelligent_system_ar.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

// Только тёмная тема: приложение работает с камерой в цеху, динамические цвета отключены
private val ArColorScheme = darkColorScheme(
    primary = ArAccent,
    onPrimary = ArOnAccent,
    secondary = ArAccent,
    background = ArBackground,
    onBackground = ArTextPrimary,
    surface = ArSurface,
    onSurface = ArTextPrimary,
    surfaceVariant = ArSurfaceHigh,
    onSurfaceVariant = ArTextSecondary,
    outline = ArOutline,
    error = StatusCritical
)

@Composable
fun Intelligent_System_ARTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = ArColorScheme,
        typography = Typography,
        content = content
    )
}
