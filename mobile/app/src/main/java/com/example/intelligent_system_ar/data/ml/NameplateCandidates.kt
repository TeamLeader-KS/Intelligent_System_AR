package com.example.intelligent_system_ar.data.ml

/** OCR is a suggestion: preserve spelling and require the engineer to confirm. */
object NameplateCandidates {
    fun extract(text: String): List<String> {
        val labels=setOf("SERIAL","MODEL","TYPE","PUMP","MOTOR","NUMBER","MADE","RATED","POWER")
        val tokens=Regex("(?<![A-Za-z0-9_./-])[A-Za-z0-9][A-Za-z0-9_./-]{1,119}(?![A-Za-z0-9_./-])").findAll(text).map { it.value }
            .filter { value -> value.length<=120 && (value.any { it.isDigit() } || value.length>=4 && value.uppercase() !in labels) }.distinct().toList()
        return tokens.sortedWith(compareByDescending<String> { value -> value.any { it.isDigit() } }.thenByDescending { it.length }).take(12)
    }
}
