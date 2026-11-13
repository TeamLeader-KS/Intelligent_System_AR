package com.example.intelligent_system_ar.data.model

data class UserState(
    val login: String = "",          // логин, с которым вошли на сервер
    val employeeId: Int = 0,          // 0 — сотрудник не зарегистрирован
    val employeeName: String = "",    // "Иванов И.И."
    val role: String = "",            // "Мастер"
    val workshopId: Int = 0,
    val workshop: String = ""         // "Цех 1"
) {
    // «Зарегистрирован» = вошёл на сервер по логину и паролю
    val isRegistered: Boolean get() = login.isNotEmpty()
}
