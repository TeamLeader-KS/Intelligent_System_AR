package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.model.componentAttention
import com.example.intelligent_system_ar.data.remote.model.ComponentDto
import com.example.intelligent_system_ar.data.remote.model.ResourceDto
import org.junit.Assert.*
import org.junit.Test

class ComponentAttentionTest {
    private fun component(id: Int, status: String, service: Double? = null, due: Boolean? = null) = ComponentDto(
        id=id, revision=0, name="Узел $id", model="", specifications=emptyList(),
        resource=ResourceDto(status, emptyMap(), "Нормативный расчёт", service, due),
        installedOn=null, lastServicedAt=null, operatingHours=null, operatingCycles=null)

    @Test fun prioritizesExpiredAndDueServiceBeforeUnknownData() {
        val items=componentAttention(listOf(component(1,"INSUFFICIENT_DATA"),component(2,"APPROACHING"),
            component(3,"WITHIN_NORM",due=true),component(4,"DUE"),component(5,"WITHIN_NORM")))
        assertEquals(listOf(4,3,2,1),items.map { it.componentId })
        assertTrue(items.last().reasons.single().contains("Недостаточно данных"))
    }

    @Test fun keepsBothReasonsAndNeverTreatsUnknownServiceAsZero() {
        val items=componentAttention(listOf(component(1,"DUE",0.0),component(2,"WITHIN_NORM",null)))
        assertEquals(1,items.size)
        assertEquals(2,items.single().reasons.size)
    }
}
