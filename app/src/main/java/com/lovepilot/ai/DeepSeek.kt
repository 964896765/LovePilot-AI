package com.lovepilot.ai

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object DeepSeek {
 fun suggest(key: String, notes: String, incoming: String): String {
  require(key.isNotBlank()) { "请先设置 API Key" }
  val conn = URL("https://api.deepseek.com/chat/completions").openConnection() as HttpURLConnection
  try {
   conn.requestMethod="POST";conn.connectTimeout=12000;conn.readTimeout=25000
   conn.setRequestProperty("Authorization", "Bearer $key")
   conn.setRequestProperty("Content-Type", "application/json")
   conn.doOutput=true
   val msgs=JSONArray().put(JSONObject().put("role","system").put("content",Policy.systemPrompt(notes)))
     .put(JSONObject().put("role","user").put("content", "请为以下消息提供一条可由本人确认后发送的回复：$incoming"))
   val body=JSONObject().put("model","deepseek-chat").put("messages",msgs).put("max_tokens",180).toString()
   conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
   val stream=if(conn.responseCode in 200..299) conn.inputStream else conn.errorStream
   val response=stream.bufferedReader().use { it.readText() }
   if(conn.responseCode !in 200..299) error("模型接口错误 HTTP ${conn.responseCode}: ${response.take(160)}")
   return JSONObject(response).getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content")
  } finally { conn.disconnect() }
 }
}
