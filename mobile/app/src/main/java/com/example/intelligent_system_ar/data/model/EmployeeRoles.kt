package com.example.intelligent_system_ar.data.model

val EMPLOYEE_ROLES = listOf("Рабочий", "Слесарь", "Мастер", "Инженер СГИ", "Начальник цеха")

/** Кто имеет полномочия чинить (поле Employee.canRepair). */
fun canRepair(role: String): Boolean = role != "Рабочий"
