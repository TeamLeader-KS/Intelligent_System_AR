package com.example.intelligent_system_ar.data.repository

object StaffSource {
    /**
     * true  — цеха, должности и сотрудники берутся из встроенной заглушки (MockDirectoryRepository).
     *         Нужно, пока на сервере нет запросов workshops/{id}/roles и workshops/{id}/employees.
     * false — все три списка запрашиваются у сервера (ServerDirectoryRepository).
     */
    const val USE_MOCK = true
}
