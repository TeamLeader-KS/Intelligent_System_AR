package com.example.intelligent_system_ar.data.model

enum class ScanStatus(val titleRu: String) {
    OK("Норма"),
    WARNING("Требует внимания"),
    CRITICAL("Неисправность"),
    UNKNOWN("Не распознано");

    companion object {
        // Значения приходят с сервера: "OK" | "WARNING" | "CRITICAL"
        fun fromServer(value: String?): ScanStatus = when (value?.uppercase()) {
            "OK" -> OK
            "WARNING" -> WARNING
            "CRITICAL" -> CRITICAL
            else -> UNKNOWN
        }
    }
}
