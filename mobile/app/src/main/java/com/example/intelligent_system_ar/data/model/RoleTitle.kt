package com.example.intelligent_system_ar.data.model


// Название должности для экрана. Сервер может отдавать код (MASTER) или уже русское название
// ("Мастер") — оба варианта поддерживаются. Неизвестное значение показывается как есть.

fun roleTitle(code: String): String = when (code.trim().uppercase()) {
    "ADMIN" -> "Администратор"
    "WORKER" -> "Рабочий"
    "MASTER" -> "Мастер"
    "ENGINEER" -> "Инженер"
    "HEAD" -> "Руководитель"
    else -> code
}
