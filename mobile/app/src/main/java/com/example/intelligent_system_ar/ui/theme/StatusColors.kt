package com.example.intelligent_system_ar.ui.theme

import androidx.compose.ui.graphics.Color
import com.example.intelligent_system_ar.data.model.ScanStatus

fun ScanStatus.statusColor(): Color = when (this) {
    ScanStatus.OK -> StatusOk
    ScanStatus.WARNING -> StatusWarning
    ScanStatus.CRITICAL -> StatusCritical
    ScanStatus.UNKNOWN -> ArTextSecondary
}
