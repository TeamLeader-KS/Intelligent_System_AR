package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.local.Employee
import com.example.intelligent_system_ar.data.model.EMPLOYEE_ROLES
import com.example.intelligent_system_ar.data.model.Workshop
import com.example.intelligent_system_ar.data.model.canRepair
import kotlinx.coroutines.delay

/** ВРЕМЕННАЯ заглушка вместо сервера. У каждого цеха свои должности и свои сотрудники. */
class MockDirectoryRepository : DirectoryRepository {

    private val workshops = listOf(Workshop(1, "Цех 1"), Workshop(2, "Цех 2"), Workshop(3, "Цех 3"))

    private fun e(id: Int, name: String, role: String, workshopId: Int) =
        Employee(id, name, role, workshopId, canRepair(role))

    private val employees = listOf(
        // Цех 1: начальник, мастера, слесарь, рабочие
        e(1, "Волков Н.Н.", "Начальник цеха", 1),
        e(2, "Иванов И.И.", "Мастер", 1),
        e(3, "Белов А.А.", "Мастер", 1),
        e(4, "Петров П.П.", "Слесарь", 1),
        e(5, "Сидоров С.С.", "Рабочий", 1),
        e(6, "Громов Е.В.", "Рабочий", 1),
        // Цех 2: без инженера
        e(7, "Захаров О.Л.", "Начальник цеха", 2),
        e(8, "Кузнецова А.В.", "Мастер", 2),
        e(9, "Морозов Р.Т.", "Слесарь", 2),
        e(10, "Смирнов Д.А.", "Рабочий", 2),
        e(11, "Лебедев Ю.К.", "Рабочий", 2),
        // Цех 3: есть инженер, нет слесаря
        e(12, "Орлов К.М.", "Начальник цеха", 3),
        e(13, "Фёдорова Т.С.", "Мастер", 3),
        e(14, "Никитин В.П.", "Инженер СГИ", 3),
        e(15, "Павлов Г.Д.", "Рабочий", 3),
        e(16, "Егоров М.А.", "Рабочий", 3)
    )

    override suspend fun getWorkshops(): Result<List<Workshop>> = safeCall {
        delay(300) // имитация сети
        workshops
    }

    override suspend fun getRoles(workshopId: Int): Result<List<String>> = safeCall {
        delay(300)
        EMPLOYEE_ROLES.filter { role -> employees.any { it.workshopId == workshopId && it.role == role } }
    }

    override suspend fun getEmployees(workshopId: Int, role: String): Result<List<Employee>> = safeCall {
        delay(300)
        employees.filter { it.workshopId == workshopId && it.role == role }.sortedBy { it.name }
    }
}
