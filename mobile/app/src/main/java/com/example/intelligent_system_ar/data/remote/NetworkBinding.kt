package com.example.intelligent_system_ar.data.remote

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import java.net.InetAddress
import java.net.Socket
import javax.net.SocketFactory

object NetworkBinding {

    /** Текущая Wi-Fi сеть или null. */
    @Suppress("DEPRECATION")
    fun wifi(context: Context): Network? {
        val cm = context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        return cm.allNetworks.firstOrNull {
            cm.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        }
    }

    /** true для адресов вида 10.x.x.x, 172.16–31.x.x, 192.168.x.x (IP-адрес, не имя: DNS не вызывается). */
    fun isPrivateIpv4(host: String): Boolean {
        if (!Regex("""\d{1,3}(\.\d{1,3}){3}""").matches(host)) return false
        return try { InetAddress.getByName(host).isSiteLocalAddress } catch (e: Exception) { false }
    }
}

/**
 * Привязывает соединения к Wi-Fi в момент подключения.
 *
 * Зачем: если у телефона включён мобильный интернет, а Wi-Fi без интернета (точка доступа
 * ноутбука, локальный роутер), Android отправляет обычные запросы через мобильную сеть, где
 * адрес 192.168.x.x недоступен — вход «не видит сервер», хотя поиск по Wi-Fi его нашёл.
 * Сеть берётся при каждом подключении, поэтому смена/переподключение Wi-Fi не ломает работу.
 */
class WifiSocketFactory(private val context: Context) : SocketFactory() {
    private fun delegate(): SocketFactory = NetworkBinding.wifi(context)?.socketFactory ?: getDefault()

    override fun createSocket(): Socket = delegate().createSocket()
    override fun createSocket(host: String, port: Int): Socket = delegate().createSocket(host, port)
    override fun createSocket(host: String, port: Int, localHost: InetAddress, localPort: Int): Socket =
        delegate().createSocket(host, port, localHost, localPort)
    override fun createSocket(host: InetAddress, port: Int): Socket = delegate().createSocket(host, port)
    override fun createSocket(address: InetAddress, port: Int, localAddress: InetAddress, localPort: Int): Socket =
        delegate().createSocket(address, port, localAddress, localPort)
}