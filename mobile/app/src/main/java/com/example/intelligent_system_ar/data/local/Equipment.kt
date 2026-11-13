package com.example.intelligent_system_ar.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "equipment")
data class Equipment(
    @PrimaryKey val id: Int,
    val name: String, // "Компрессор", "Саморез"
    val workshopId: Int,
    val status: String // "OK", "WARNING", "CRITICAL"
)