package com.example.intelligent_system_ar.data.ml

enum class FindingKind { DEFECT, UNKNOWN }

data class DetectionBox(val left: Float, val top: Float, val right: Float, val bottom: Float)
data class Detection(
    val classId: Int,
    val label: String,
    val confidence: Float,
    val kind: FindingKind,
    val box: DetectionBox
)
