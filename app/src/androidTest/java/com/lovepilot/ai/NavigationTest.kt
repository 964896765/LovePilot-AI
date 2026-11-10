package com.lovepilot.ai

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test

class NavigationTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private var previousUrl = "http://127.0.0.1:8768"
    private var previousToken = ""

    @Before fun saveConnection() {
        val prefs = SecurePrefs(InstrumentationRegistry.getInstrumentation().targetContext)
        previousUrl = prefs.read("url", previousUrl)
        previousToken = prefs.read("token")
    }

    @After fun restoreConnection() {
        val prefs = SecurePrefs(InstrumentationRegistry.getInstrumentation().targetContext)
        if (previousToken.isBlank()) prefs.clear() else prefs.saveConnection(previousUrl, previousToken)
    }

    @Test fun fiveNavigationDestinationsRender() {
        compose.onNodeWithTag("nav-0").performClick()
        compose.onNodeWithText("让交流，自然发生").assertIsDisplayed()
        compose.onNodeWithTag("nav-1").performClick()
        compose.onNodeWithText("聊天工作台").assertIsDisplayed()
        compose.onNodeWithTag("nav-2").performClick()
        compose.onNodeWithText("每位联系人，拥有独立的上下文与记忆").assertIsDisplayed()
        compose.onNodeWithTag("nav-3").performClick()
        compose.onNodeWithText("记忆空间").assertIsDisplayed()
        compose.onNodeWithTag("nav-4").performClick()
        compose.onNodeWithText("管理你的 AI、数据与连接").assertIsDisplayed()
    }

    @Test fun settingsAndBackNavigationWork() {
        compose.onNodeWithTag("nav-4").performClick()
        compose.onNodeWithText("连接与权限").performScrollTo().performClick()
        compose.onNodeWithTag("connection-url").assertIsDisplayed()
        compose.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        compose.waitForIdle()
        compose.onNodeWithText("Skills 管理").performScrollTo().performClick()
        compose.onNodeWithText("12 项独立技能，共同尊重沟通边界").assertIsDisplayed()
    }

    @Test fun realBackendContactChatMemoryAndRevocation() {
        val token = InstrumentationRegistry.getArguments().getString("agent_token")
        assumeTrue("Pass the token for the isolated phone test backend", !token.isNullOrBlank())
        compose.onNodeWithTag("nav-4").performClick()
        compose.onNodeWithText("连接与权限").performScrollTo().performClick()
        compose.onNodeWithTag("connection-url").performTextReplacement("http://127.0.0.1:8870")
        compose.onNodeWithTag("connection-token").performTextReplacement(token!!)
        compose.onNodeWithTag("connection-save").performClick()
        waitFor("已同步最新运行状态")
        compose.onNodeWithTag("nav-2").performClick()
        compose.onNodeWithText("＋ 建立联系人档案").performClick()
        val alias = "验收测试-" + System.currentTimeMillis().toString().takeLast(6)
        compose.onNodeWithTag("contact-alias").performTextInput(alias)
        compose.onNodeWithTag("contact-consent").performClick()
        compose.onNodeWithText("保存档案").performClick()
        waitFor(alias)
        compose.onNodeWithTag("nav-1").performClick()
        compose.onNodeWithTag("chat-message").performTextInput("我喜欢科幻电影")
        compose.onNodeWithTag("chat-generate").performClick()
        waitFor("听起来很有意思，你最近看了哪部电影？")
        compose.onNodeWithTag("nav-3").performClick()
        waitFor("科幻电影")
        compose.onNodeWithText("确认保存").performScrollTo().performClick()
        compose.waitUntil(20000) { compose.onAllNodesWithText("待确认 · 1").fetchSemanticsNodes().isEmpty() }
        compose.onNodeWithText("科幻电影").assertExists()
        compose.onNodeWithTag("nav-2").performClick()
        compose.onNodeWithText("撤销").performScrollTo().performClick()
        waitFor("待授权")
        compose.onNodeWithTag("nav-1").performClick()
        compose.onNodeWithTag("chat-message").performTextInput("你好")
        compose.onNodeWithTag("chat-generate").performClick()
        waitFor("需要你亲自处理")
    }

    private fun waitFor(text: String) {
        compose.waitUntil(30000) { compose.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty() }
    }
}
