package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.remote.ServerDiscovery
import okhttp3.OkHttpClient
import org.junit.Assert.*
import org.junit.Test
import java.net.InetAddress
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class ServerDiscoveryTest {
    private fun withServer(body: String, check: (String, OkHttpClient) -> Unit) {
        ServerSocket(0, 1, InetAddress.getByName("127.0.0.1")).use { server ->
            server.soTimeout = 3000
            val executor = Executors.newSingleThreadExecutor()
            val client = OkHttpClient.Builder().callTimeout(2, TimeUnit.SECONDS).build()
            val request = executor.submit<List<String>> {
                server.accept().use { socket ->
                    socket.soTimeout = 3000
                    val reader = socket.getInputStream().bufferedReader()
                    val headers = mutableListOf<String>()
                    while (true) {
                        val line = reader.readLine() ?: break
                        if (line.isEmpty()) break
                        headers.add(line)
                    }
                    val bytes = body.toByteArray()
                    socket.getOutputStream().apply {
                        write("HTTP/1.1 200 OK\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray())
                        write(bytes)
                        flush()
                    }
                    headers
                }
            }
            try {
                check("http://127.0.0.1:${server.localPort}", client)
                val headers = request.get(4, TimeUnit.SECONDS)
                assertEquals("GET /industrial-vision/mobile-server HTTP/1.1", headers.first())
                assertFalse(headers.any { it.startsWith("Authorization:", ignoreCase = true) })
            } finally {
                client.connectionPool().evictAll()
                client.dispatcher().executorService().shutdownNow()
                executor.shutdownNow()
            }
        }
    }

    @Test fun probesExplicitAddressAndPreservesItsPort() {
        withServer("""{"service":"industrial-vision","api_path":"/industrial-vision/api/v1/"}""") { base, client ->
            val expected = "$base/industrial-vision/api/v1/"
            assertEquals(expected, ServerDiscovery.probe(client, base))
        }
    }

    @Test fun rejectsAnotherService() {
        withServer("""{"service":"another-service","api_path":"/industrial-vision/api/v1/"}""") { base, client ->
            assertNull(ServerDiscovery.probe(client, "$base/industrial-vision/api/v1/"))
        }
    }

    @Test fun rejectsWrongApiPath() {
        withServer("""{"service":"industrial-vision","api_path":"/another/api/v1/"}""") { base, client ->
            assertNull(ServerDiscovery.probe(client, base))
        }
    }

    @Test fun rejectsMalformedResponse() {
        withServer("not json") { base, client ->
            assertNull(ServerDiscovery.probe(client, base))
        }
    }
}
