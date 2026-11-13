package com.example.intelligent_system_ar.ui

import com.example.intelligent_system_ar.data.local.Employee
import com.example.intelligent_system_ar.data.model.Workshop

/** Состояние окна регистрации: цех -> должность -> Ф.И.О. (каждый следующий список зависит от предыдущего). */
data class RegistrationUi(
    val workshops: List<Workshop> = emptyList(),
    val roles: List<String> = emptyList(),
    val employees: List<Employee> = emptyList(),
    val selectedWorkshop: Workshop? = null,
    val selectedRole: String? = null,
    val selectedEmployee: Employee? = null,
    val isLoading: Boolean = false,
    val error: String? = null
)
