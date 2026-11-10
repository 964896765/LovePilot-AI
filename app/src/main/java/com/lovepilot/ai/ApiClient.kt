package com.lovepilot.ai

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

fun JSONArray?.objects(): List<JSONObject> = if (this == null) emptyList() else
    (0 until length()).mapNotNull { optJSONObject(it) }

fun encodeQuery(value: String): String = URLEncoder.encode(value, "UTF-8")

fun InputStream.readBounded(maximum: Int): ByteArray {
    val output = ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    var count = read(buffer)
    while (count >= 0) {
        require(output.size() + count <= maximum) { "数据超过安全大小限制" }
        output.write(buffer, 0, count)
        count = read(buffer)
    }
    return output.toByteArray()
}

class ApiException(val status: Int, message: String) : Exception(message)

class ApiClient(baseUrl: String, private val token: String) {
    private val base = validateApiEndpoint(baseUrl, BuildConfig.DEBUG)

    suspend fun get(path: String): JSONObject = request("GET", path, null)
    suspend fun post(path: String, data: JSONObject): JSONObject = request("POST", path, data)

    private suspend fun request(method: String, path: String, data: JSONObject?): JSONObject = withContext(Dispatchers.IO) {
        require(path.startsWith('/') && !path.startsWith("//"))
        require(token.isNotBlank()) { "请先在「我的」配置服务令牌" }
        val connection = URL(base + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 6000
            connection.readTimeout = 55000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            if (data != null) {
                connection.doOutput = true
                connection.outputStream.use { it.write(data.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val raw = stream?.use { String(it.readBounded(64 * 1024 * 1024), Charsets.UTF_8) }.orEmpty()
            if (status !in 200..299) {
                val message = when (status) {
                    401 -> "服务令牌无效，请重新配置"
                    403 -> "当前令牌权限不足或联系人授权已撤销"
                    409 -> "数据冲突，请先检查已有联系人"
                    429 -> "操作过于频繁，请稍后重试"
                    else -> "服务请求失败 HTTP $status"
                }
                throw ApiException(status, message)
            }
            JSONObject(raw)
        } finally {
            connection.disconnect()
        }
    }
}
