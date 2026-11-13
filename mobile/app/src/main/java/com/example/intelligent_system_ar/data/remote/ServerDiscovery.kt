package com.example.intelligent_system_ar.data.remote

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import com.google.gson.Gson
import com.google.gson.JsonParseException
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.net.*
import java.util.UUID
import java.util.concurrent.TimeUnit

object ServerDiscovery {
    private data class Advertisement(val service: String?, val api_url: String?, val nonce: String?)
    private data class ServerIdentity(val service: String?, val api_path: String?)

    suspend fun find(context: Context, previous: String): String? = withContext(Dispatchers.IO) {
        val connectivity = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val wifi = connectivity.allNetworks.firstOrNull {
            connectivity.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        } ?: return@withContext null
        val addresses = connectivity.getLinkProperties(wifi)?.linkAddresses.orEmpty()
            .mapNotNull { it.address as? Inet4Address }.filter { it.isSiteLocalAddress }
        if (addresses.isEmpty()) return@withContext null
        val client = OkHttpClient.Builder().socketFactory(wifi.socketFactory)
            .connectTimeout(350, TimeUnit.MILLISECONDS).readTimeout(500, TimeUnit.MILLISECONDS)
            .callTimeout(800, TimeUnit.MILLISECONDS).followRedirects(false).followSslRedirects(false)
            .proxy(Proxy.NO_PROXY).build()
        try {
            val udp = try { broadcast(context, wifi, addresses) } catch (_: IOException) { null }
            if (udp != null) {
                val host = HttpUrl.parse(udp)?.host()
                if (host != null && probe(client, host) != null) return@withContext udp
            }
            // Previous addresses are only tried within the current Wi-Fi /24.
            val prefixes = addresses.map { it.hostAddress!!.substringBeforeLast('.') }.distinct()
            val saved = HttpUrl.parse(previous)?.host()
            if (saved != null && prefixes.any { saved.startsWith("$it.") }) {
                probe(client, saved)?.let { return@withContext it }
            }
            // Some access points drop UDP broadcast. Probe only our service/port
            // on the connected Wi-Fi subnets, without credentials or Internet.
            val hosts = prefixes.flatMap { prefix -> (1..254).map { "$prefix.$it" } }
            coroutineScope {
                val found = CompletableDeferred<String?>()
                val gate = Semaphore(24)
                val jobs = hosts.map { host ->
                    launch {
                        gate.withPermit {
                            ensureActive()
                            if (!found.isCompleted) probe(client, host)?.let { found.complete(it) }
                        }
                    }
                }
                val completion = launch {
                    jobs.joinAll()
                    found.complete(null)
                }
                val result = withTimeoutOrNull(7000) { found.await() }
                jobs.forEach { it.cancel() }
                completion.cancel()
                result
            }
        } finally {
            client.connectionPool().evictAll()
            client.dispatcher().executorService().shutdown()
        }
    }

    private fun probe(client: OkHttpClient, host: String): String? = try {
        client.newCall(Request.Builder().url("http://$host:8001/industrial-vision/mobile-server").build())
            .execute().use { response ->
                if (!response.isSuccessful) null else {
                    val text = response.peekBody(1024).string()
                    val identity = Gson().fromJson(text, ServerIdentity::class.java)
                    if (identity?.service == "industrial-vision" && identity.api_path == "/industrial-vision/api/v1/")
                        "http://$host:8001/industrial-vision/api/v1/" else null
                }
            }
    } catch (_: IOException) { null } catch (_: JsonParseException) { null }

    private suspend fun broadcast(context: Context, network: Network, addresses: List<Inet4Address>): String? {
        val manager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val lock = manager.createMulticastLock("industrial-vision-discovery").apply { setReferenceCounted(false) }
        lock.acquire()
        try {
            val nonce = UUID.randomUUID().toString()
            val request = "IV_DISCOVER_V1 $nonce".toByteArray(Charsets.UTF_8)
            val targets = addresses.map { it.hostAddress!!.substringBeforeLast('.') + ".255" }.toSet()
            DatagramSocket(null).use { socket ->
                network.bindSocket(socket)
                socket.bind(InetSocketAddress(0))
                socket.broadcast = true
                socket.soTimeout = 350
                for (host in targets) {
                    socket.send(DatagramPacket(request, request.size, InetAddress.getByName(host), 51020))
                }
                val deadline = System.nanoTime() + 1_500_000_000L
                while (System.nanoTime() < deadline) {
                    currentCoroutineContext().ensureActive()
                    val packet = DatagramPacket(ByteArray(1024), 1024)
                    try { socket.receive(packet) } catch (_: SocketTimeoutException) { continue }
                    val ad = try {
                        Gson().fromJson(String(packet.data, 0, packet.length, Charsets.UTF_8), Advertisement::class.java)
                    } catch (_: JsonParseException) { continue }
                    if (ad?.service != "industrial-vision" || ad.nonce != nonce || ad.api_url == null) continue
                    val url = HttpUrl.parse(ad.api_url) ?: continue
                    if (url.host() != packet.address.hostAddress || !packet.address.isSiteLocalAddress) continue
                    return try { ServerConfig.normalize(ad.api_url) } catch (_: IllegalArgumentException) { null }
                }
            }
            return null
        } finally {
            lock.release()
        }
    }
}
