package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.ml.InventoryQrDecoder
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import org.junit.Assert.*
import org.junit.Test

class InventoryQrDecoderTest {
    private fun pixels(text: String): IntArray {
        val matrix=QRCodeWriter().encode(text,BarcodeFormat.QR_CODE,256,256)
        return IntArray(256*256) { i -> if(matrix[i%256,i/256]) 0xff000000.toInt() else 0xffffffff.toInt() }
    }
    @Test fun exactInventoryCodeCanBeReadOffline() {
        assertEquals("pump_demo_001",InventoryQrDecoder().decode(256,256,pixels("pump_demo_001")))
    }
    @Test fun externalUrlsAreNotInventoryIdentifiers() {
        assertNull(InventoryQrDecoder().decode(256,256,pixels("https://example.com/pump")))
    }
}
