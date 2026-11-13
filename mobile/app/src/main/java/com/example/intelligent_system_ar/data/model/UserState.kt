package com.example.intelligent_system_ar.data.model

data class UserState(
    val employeeId: Int = 0,          // 0 — сотрудник не зарегистрирован
    val employeeName: String = "",    // "Иванов И.И."
    val role: String = "",            // "Мастер"
    val workshopId: Int = 0,
    val workshop: String = ""         // "Цех 1"
) {
    val isRegistered: Boolean get() = employeeId != 0
}
