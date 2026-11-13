package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.ml.*
import org.junit.Assert.*
import org.junit.Test

class YoloPostprocessorTest {
    private val labels = List(12) { if (it == 5) "Без коррозии" else "class-$it" }
    private fun output(vararg classes: Pair<Int,Float>): Array<FloatArray> = Array(17) { FloatArray(classes.size) }.also { tensor ->
        classes.forEachIndexed { index, (id,score) ->
            tensor[0][index]=320f; tensor[1][index]=320f; tensor[2][index]=320f; tensor[3][index]=180f
            tensor[4+id][index]=score
        }
    }

    @Test fun restoresLetterboxToOriginalLandscapeFrame() {
        val geometry=LetterboxGeometry(1280,720)
        assertEquals(140,geometry.top)
        val box=geometry.restore(320f,320f,320f,180f)!!
        assertEquals(0.25f,box.left,0.0001f); assertEquals(0.25f,box.top,0.0001f)
        assertEquals(0.75f,box.right,0.0001f); assertEquals(0.75f,box.bottom,0.0001f)
        assertNull(geometry.restore(320f,20f,100f,20f))
    }

    @Test fun suppressesDuplicateBoxesButKeepsDifferentClasses() {
        val findings=YoloPostprocessor.decode(output(7 to 0.8f,7 to 0.6f,1 to 0.7f),labels,LetterboxGeometry(1280,720))
        assertEquals(listOf(7,1),findings.map { it.classId })
    }

    @Test fun normalAndThresholdAreNotDefectsAndUnknownThirteenthClassIsPreserved() {
        val findings=YoloPostprocessor.decode(output(5 to 0.99f,7 to 0.4f,12 to 0.75f),labels,LetterboxGeometry(640,640))
        assertEquals(1,findings.size)
        assertEquals(12,findings.single().classId)
        assertEquals(FindingKind.UNKNOWN,findings.single().kind)
        assertEquals("Неизвестный класс 12",findings.single().label)
    }

    @Test fun invalidCoordinatesAndScoresAreIgnored() {
        val tensor=output(7 to 0.8f,1 to Float.NaN,6 to 0.7f)
        tensor[0][0]=Float.NaN; tensor[2][2]=-10f
        assertTrue(YoloPostprocessor.decode(tensor,labels,LetterboxGeometry(640,640)).isEmpty())
    }

    @Test fun rotatesNormalizedBoxesBackToCameraBuffer() {
        val box=DetectionBox(0.1f,0.2f,0.4f,0.6f)
        val rotated=YoloPostprocessor.toBuffer(box,90)
        assertEquals(0.2f,rotated.left,0.0001f); assertEquals(0.6f,rotated.top,0.0001f)
        assertEquals(0.6f,rotated.right,0.0001f); assertEquals(0.9f,rotated.bottom,0.0001f)
        val restored=YoloPostprocessor.toBuffer(rotated,270)
        assertEquals(box.left,restored.left,0.0001f); assertEquals(box.top,restored.top,0.0001f)
        assertEquals(box.right,restored.right,0.0001f); assertEquals(box.bottom,restored.bottom,0.0001f)
    }
}
