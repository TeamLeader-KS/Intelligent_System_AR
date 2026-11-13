package com.example.intelligent_system_ar.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "defects")
data class Defect(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val equipmentId: Int,
    val title: String, // "Выкручен саморез"
    val status: String, // "CRITICAL"
    val solution: String, // "Вкрутить саморез обратно"
    val timestamp: Long = System.currentTimeMillis()
)