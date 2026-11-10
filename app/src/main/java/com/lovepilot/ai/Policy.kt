package com.lovepilot.ai

object Policy {
 private val sensitive = listOf("分手", "表白", "喜欢你", "爱你", "借钱", "转账", "见面", "约会", "地址", "身份证", "密码", "不想聊", "别联系", "停止联系", "自杀", "伤害自己")
 fun needsHuman(text: String): Boolean = sensitive.any { text.contains(it, ignoreCase = true) }
 fun systemPrompt(notes: String) = """你是经对话参与者知情授权的日常聊天辅助 AI。中文自然口语，通常 5-35 字；尊重对方边界，避免反复追问、过度暧昧或编造经历。不得代替本人作出关系、金钱、见面承诺。只依据已提供的事实。联系人资料：${notes.take(600)}"""
}
