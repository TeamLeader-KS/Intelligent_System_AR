package com.example.intelligent_system_ar.data.ml

data class CapturedInspection(
    val jpeg: ByteArray,
    val width: Int,
    val height: Int,
    val capturedAt: String,
    val detections: List<Detection>
)
