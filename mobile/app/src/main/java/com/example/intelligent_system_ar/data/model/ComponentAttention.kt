package com.example.intelligent_system_ar.data.model

import com.example.intelligent_system_ar.data.remote.model.ComponentDto

data class ComponentAttention(val componentId: Int, val name: String, val reasons: List<String>, val priority: Int)

fun componentAttention(components: List<ComponentDto>): List<ComponentAttention> = components.mapNotNull { component ->
    val resource = component.resource
    val reasons = mutableListOf<String>()
    var priority = 4
    when (resource.status) {
        "DUE" -> { reasons += "Исчерпан указанный нормативный ресурс"; priority = 0 }
        "APPROACHING" -> { reasons += "До нормативного предела осталось не более 10%"; priority = 2 }
        "INSUFFICIENT_DATA" -> reasons.add("Недостаточно данных для расчёта ресурса")
    }
    if (resource.serviceDue == true || resource.serviceRemainingHours == 0.0) {
        reasons += "Достигнут указанный интервал обслуживания"
        priority = minOf(priority, 1)
    }
    if (reasons.isEmpty()) null else ComponentAttention(component.id, component.name, reasons, priority)
}.sortedWith(compareBy<ComponentAttention> { it.priority }.thenBy { it.componentId })
