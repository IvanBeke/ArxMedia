import { defineStore } from 'pinia'
import { notificationsAPI } from '@/api'

// Only the unread count is shared (header bell and notifications page); the list lives in NotificationsView.
export const useNotificationsStore = defineStore('notifications', {
  state: () => ({ unreadCount: 0 }),
  actions: {
    async refreshUnread() {
      try { this.unreadCount = (await notificationsAPI.getUnreadCount()).unread_count } catch { /* keep the last known count */ }
    },
  },
})
