package com.lovepilot.ai

import java.net.URI

fun validateApiEndpoint(value: String, allowLocalHttp: Boolean): String {
    val clean = value.trim().trimEnd('/')
    val uri = URI(clean)
    require(uri.host != null && uri.userInfo == null && uri.query == null && uri.fragment == null) {
        "请输入有效服务地址"
    }
    val local = uri.host in setOf("localhost", "127.0.0.1", "[::1]", "::1")
    require(uri.scheme == "https" || (allowLocalHttp && uri.scheme == "http" && local)) {
        "远程连接需要 HTTPS，本机调试可使用 localhost"
    }
    return clean
}
