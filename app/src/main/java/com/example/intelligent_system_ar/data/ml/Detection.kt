package com.example.intelligent_system_ar.data.ml

import android.graphics.RectF

data class Detection(
    val boundingBox: RectF,
    val label: String,
    val confidence: Float
)