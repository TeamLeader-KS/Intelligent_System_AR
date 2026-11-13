package com.example.intelligent_system_ar.ui.component

fun parameterTitle(name: String): String = when(name) {
    "vibration_mm_s" -> "Виброскорость"
    "vibration_axial_mm_s" -> "Осевая вибрация"
    "vibration_low_mm_s" -> "Низкочастотная вибрация"
    "vibration_hf_mm_s" -> "Высокочастотная вибрация"
    "bearing_temperature_c" -> "Температура подшипника"
    "current_a" -> "Ток двигателя"
    "inlet_pressure_bar" -> "Давление на входе"
    "efficiency_pct" -> "КПД насоса"
    "phase_imbalance_pct" -> "Дисбаланс токов по фазам"
    "pressure_bar" -> "Давление электронного датчика"
    "gauge_pressure_bar" -> "Давление манометра"
    else -> name
}

fun parameterUnit(unit: String): String=when(unit) {
    "C"->"°C"; "A"->"А"; "mm/s"->"мм/с"; "bar"->"бар"; else->unit
}

fun resourceTitle(status: String): String=when(status) {
    "DUE"->"Норматив достигнут"
    "APPROACHING"->"Приближается норматив"
    "WITHIN_NORM"->"В пределах норматива"
    else->"Недостаточно данных для ресурса"
}

fun inspectionTitle(status: String): String=when(status) {
    "OK"->"Видимых проблем не обнаружено"
    "WARNING"->"Рекомендуется проверка"
    "CRITICAL"->"Признаки возможного дефекта"
    else->"Недостаточно данных"
}
