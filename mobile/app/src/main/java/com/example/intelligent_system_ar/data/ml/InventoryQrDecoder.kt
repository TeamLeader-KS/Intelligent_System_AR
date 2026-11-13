package com.example.intelligent_system_ar.data.ml

import com.google.zxing.BinaryBitmap
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.ReaderException
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeReader

class InventoryQrDecoder {
    private val reader=QRCodeReader()
    fun decode(width: Int,height: Int,pixels: IntArray): String? = try {
        val value=reader.decode(BinaryBitmap(HybridBinarizer(RGBLuminanceSource(width,height,pixels)))).text.trim()
        value.takeIf { it.matches(Regex("[A-Za-z0-9][A-Za-z0-9_./-]{0,79}")) }
    } catch (_: ReaderException) { null }
    finally { reader.reset() }
}
