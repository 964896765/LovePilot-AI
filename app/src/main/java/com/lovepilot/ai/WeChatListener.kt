package com.lovepilot.ai

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification

class WeChatListener: NotificationListenerService() {
 override fun onListenerConnected() {
  NotificationProbe.connection(applicationContext, true)
  activeNotifications?.forEach { NotificationProbe.observe(applicationContext, it) }
 }

 override fun onListenerDisconnected() {
  NotificationProbe.connection(applicationContext, false)
 }

 override fun onNotificationPosted(sbn: StatusBarNotification) {
  NotificationProbe.observe(applicationContext, sbn)
 }

 override fun onNotificationRemoved(sbn: StatusBarNotification) {
  NotificationProbe.removed(applicationContext, sbn)
 }
}
