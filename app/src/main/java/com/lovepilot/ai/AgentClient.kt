package com.lovepilot.ai

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Call on a background thread. The prototype uses adb reverse to reach localhost securely. */
object AgentClient {
    fun health(token: String): JSONObject {
        val conn = (URL("http://127.0.0.1:8768/health").openConnection() as HttpURLConnection)
        try {
            conn.requestMethod = "GET"
            conn.connectTimeout = 3000
            conn.readTimeout = 5000
            conn.setRequestProperty("Authorization", "Bearer $token")
            val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
            return JSONObject(stream.bufferedReader(Charsets.UTF_8).use { it.readText() })
        } finally { conn.disconnect() }
    }

    fun post(path: String, token: String, data: JSONObject): JSONObject {
        require(path in setOf("/contacts", "/facts", "/draft", "/delete", "/revoke", "/export"))
        val conn = (URL("http://127.0.0.1:8768$path").openConnection() as HttpURLConnection)
        try {
            conn.requestMethod = "POST"
            conn.connectTimeout = 5000
            conn.readTimeout = 35000
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.doOutput = true
            conn.outputStream.use { it.write(data.toString().toByteArray(Charsets.UTF_8)) }
            val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
            val result = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            return JSONObject(result)
        } finally { conn.disconnect() }
    }
}
