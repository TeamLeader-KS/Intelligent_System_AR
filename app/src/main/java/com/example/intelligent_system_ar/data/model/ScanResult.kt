package com.example.intelligent_system_ar.data.model

import com.example.intelligent_system_ar.data.remote.model.BBox

/** Проблемный узел внутри оборудования (например, «Поломка двигателя»). */
data class DefectMark(
    val title: String,
    val box: BBox,
    val recommendation: String?
)

/**
 * UI-модель результата анализа кадра.
 * Позже собирается из DetectResponse (mapper), сейчас — из заглушек в MainViewModel.
 * Все bbox нормализованы (0..1).
 * equipmentBox — рамка всего оборудования, defects — проблемные узлы внутри него.
 */
data class ScanResult(
    val equipmentName: String,
    val status: ScanStatus,
    val equipmentBox: BBox,
    val defects: List<DefectMark>
) {
    val primaryDefect: DefectMark? get() = defects.firstOrNull()
    val summary: String get() = primaryDefect?.title ?: status.titleRu
}
