package com.example.intelligent_system_ar.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "employees")
data class Employee(
    @PrimaryKey val id: Int,
    val name: String,
    val role: String, // "Рабочий", "Слесарь", "Мастер", "Инженер"
    val workshopId: Int,
    val canRepair: Boolean // Может ли чинить (полномочия)
)