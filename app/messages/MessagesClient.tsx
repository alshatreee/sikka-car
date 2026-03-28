'use client'

import { useState, useEffect, useRef } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { MessageCircle, Send, ArrowLeft, User } from 'lucide-react'
import {
  sendMessage,
  getConversations,
  getMessages,
  markAsRead,
} from '@/app/actions/messageActions'
import Image from 'next/image'

interface Conversation {
  otherUserId: string
  otherUser: any
  lastMessage: any
  unreadCount: number
}

interface Message {
  id: string
  senderId: string
  receiverId: string
  content: string
  read: boolean
  createdAt: string
  sender: any
  receiver: any
  booking?: any
}

export default function MessagesClient() {
  const { t, lang } = useLanguage()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [showMessages, setShowMessages] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Check mobile
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768)
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Load conversations
  useEffect(() => {
    const loadConversations = async () => {
      try {
        setLoading(true)
        const data = await getConversations()
        setConversations(data)
      } catch (error) {
        console.error('Failed to load conversations:', error)
      } finally {
        setLoading(false)
      }
    }

    loadConversations()

    // Refresh every 10 seconds
    const interval = setInterval(loadConversations, 10000)
    return () => clearInterval(interval)
  }, [])

  // Load messages for selected user
  useEffect(() => {
    if (!selectedUserId) return

    const loadMessages = async () => {
      try {
        const data = await getMessages(selectedUserId)
        setMessages(data.map((m: any) => ({ ...m, createdAt: String(m.createdAt) })))
        await markAsRead(selectedUserId)
        scrollToBottom()
      } catch (error) {
        console.error('Failed to load messages:', error)
      }
    }

    loadMessages()

    // Refresh messages every 10 seconds
    const interval = setInterval(loadMessages, 10000)
    return () => clearInterval(interval)
  }, [selectedUserId])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSelectConversation = (userId: string) => {
    setSelectedUserId(userId)
    if (isMobile) {
      setShowMessages(true)
    }
  }

  const handleBack = () => {
    setShowMessages(false)
    setSelectedUserId(null)
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newMessage.trim() || !selectedUserId || sending) return

    try {
      setSending(true)
      await sendMessage(selectedUserId, newMessage)
      setNewMessage('')

      // Reload messages
      const data = await getMessages(selectedUserId)
      setMessages(data.map((m: any) => ({ ...m, createdAt: String(m.createdAt) })))
      scrollToBottom()

      // Reload conversations to update last message
      const convData = await getConversations()
      setConversations(convData)
    } catch (error) {
      console.error('Failed to send message:', error)
    } finally {
      setSending(false)
    }
  }

  // Mobile view - show either conversations list or message thread
  if (isMobile) {
    if (showMessages && selectedUserId) {
      return (
        <div className="flex h-[calc(100vh-120px)] flex-col bg-dark-bg">
          {/* Message thread header */}
          <div className="border-b border-dark-border bg-dark-card p-4">
            <div className="flex items-center gap-3">
              <button
                onClick={handleBack}
                className="text-text-secondary hover:text-text-primary"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <div>
                <p className="font-medium text-text-primary">
                  {conversations.find((c) => c.otherUserId === selectedUserId)
                    ?.otherUser?.fullName || 'User'}
                </p>
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full text-text-secondary">
                {t('noMessages')}
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${
                    msg.senderId === conversations
                      .find((c) => c.otherUserId === selectedUserId)
                      ?.otherUserId
                      ? 'justify-start'
                      : 'justify-end'
                  }`}
                >
                  <div
                    className={`max-w-xs rounded-lg border px-4 py-2 ${
                      msg.senderId === conversations
                        .find((c) => c.otherUserId === selectedUserId)
                        ?.otherUserId
                        ? 'border-dark-border bg-dark-surface text-text-primary'
                        : 'border-status-star/30 bg-status-star/20 text-text-primary'
                    }`}
                  >
                    <p className="break-words text-sm">{msg.content}</p>
                    <p className="mt-1 text-xs text-text-secondary">
                      {new Date(msg.createdAt).toLocaleTimeString(lang === 'ar' ? 'ar-SA' : 'en-US', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Message input */}
          <form
            onSubmit={handleSendMessage}
            className="border-t border-dark-border bg-dark-card p-4"
          >
            <div className="flex gap-2">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder={t('typeMessage')}
                className="flex-1 rounded-lg border border-dark-border bg-dark-surface px-4 py-2 text-text-primary placeholder-text-secondary focus:border-status-star focus:outline-none"
              />
              <button
                type="submit"
                disabled={sending || !newMessage.trim()}
                className="rounded-lg bg-status-star px-4 py-2 text-dark-bg hover:bg-status-star/90 disabled:opacity-50"
              >
                <Send className="h-5 w-5" />
              </button>
            </div>
          </form>
        </div>
      )
    }

    // Show conversations list on mobile
    return (
      <div className="min-h-[calc(100vh-120px)] bg-dark-bg p-4">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <p className="text-text-secondary">{t('loading')}</p>
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <MessageCircle className="mb-4 h-12 w-12 text-text-secondary" />
            <p className="text-text-primary font-medium">{t('noMessages')}</p>
            <p className="text-text-secondary text-sm">{t('startMessaging')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {conversations.map((conv) => (
              <button
                key={conv.otherUserId}
                onClick={() => handleSelectConversation(conv.otherUserId)}
                className="w-full rounded-lg border border-dark-border bg-dark-card p-4 text-left transition-colors hover:bg-dark-surface"
              >
                <div className="flex items-start gap-3">
                  <div className="mt-1 h-10 w-10 rounded-full bg-status-star/20 flex items-center justify-center flex-shrink-0">
                    <User className="h-5 w-5 text-status-star" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-text-primary truncate">
                        {conv.otherUser?.fullName || 'User'}
                      </p>
                      {conv.unreadCount > 0 && (
                        <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-status-star text-dark-bg text-xs font-bold flex-shrink-0">
                          {conv.unreadCount}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-text-secondary truncate">
                      {conv.lastMessage?.content || ''}
                    </p>
                    <p className="text-xs text-text-secondary mt-1">
                      {new Date(conv.lastMessage?.createdAt).toLocaleDateString(
                        lang === 'ar' ? 'ar-SA' : 'en-US'
                      )}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  // Desktop view - split layout
  return (
    <div className="flex h-[calc(100vh-120px)] gap-4 bg-dark-bg p-4">
      {/* Left sidebar - Conversations list */}
      <div className="w-80 flex flex-col border border-dark-border rounded-lg bg-dark-card overflow-hidden">
        <div className="border-b border-dark-border p-4">
          <h2 className="font-bold text-text-primary">{t('conversations')}</h2>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-text-secondary">{t('loading')}</p>
            </div>
          ) : conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full p-4 text-center">
              <MessageCircle className="mb-4 h-12 w-12 text-text-secondary" />
              <p className="text-text-primary font-medium">{t('noMessages')}</p>
              <p className="text-text-secondary text-sm">{t('startMessaging')}</p>
            </div>
          ) : (
            <div className="divide-y divide-dark-border">
              {conversations.map((conv) => (
                <button
                  key={conv.otherUserId}
                  onClick={() => handleSelectConversation(conv.otherUserId)}
                  className={`w-full p-4 text-left transition-colors ${
                    selectedUserId === conv.otherUserId
                      ? 'bg-dark-surface border-l-2 border-status-star'
                      : 'hover:bg-dark-surface'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-1 h-10 w-10 rounded-full bg-status-star/20 flex items-center justify-center flex-shrink-0">
                      <User className="h-5 w-5 text-status-star" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium text-text-primary truncate">
                          {conv.otherUser?.fullName || 'User'}
                        </p>
                        {conv.unreadCount > 0 && (
                          <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-status-star text-dark-bg text-xs font-bold flex-shrink-0">
                            {conv.unreadCount}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-text-secondary truncate">
                        {conv.lastMessage?.content || ''}
                      </p>
                      <p className="text-xs text-text-secondary mt-1">
                        {new Date(conv.lastMessage?.createdAt).toLocaleDateString(
                          lang === 'ar' ? 'ar-SA' : 'en-US'
                        )}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right side - Message thread */}
      <div className="flex-1 flex flex-col border border-dark-border rounded-lg bg-dark-card overflow-hidden">
        {selectedUserId ? (
          <>
            {/* Message thread header */}
            <div className="border-b border-dark-border p-4">
              <p className="font-bold text-text-primary">
                {conversations.find((c) => c.otherUserId === selectedUserId)
                  ?.otherUser?.fullName || 'User'}
              </p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-text-secondary">
                  {t('noMessages')}
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.senderId === selectedUserId
                        ? 'justify-start'
                        : 'justify-end'
                    }`}
                  >
                    <div
                      className={`max-w-sm rounded-lg border px-4 py-2 ${
                        msg.senderId === selectedUserId
                          ? 'border-dark-border bg-dark-surface text-text-primary'
                          : 'border-status-star/30 bg-status-star/20 text-text-primary'
                      }`}
                    >
                      <p className="break-words text-sm">{msg.content}</p>
                      <p className="mt-1 text-xs text-text-secondary">
                        {new Date(msg.createdAt).toLocaleTimeString(
                          lang === 'ar' ? 'ar-SA' : 'en-US',
                          {
                            hour: '2-digit',
                            minute: '2-digit',
                          }
                        )}
                      </p>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Message input */}
            <form
              onSubmit={handleSendMessage}
              className="border-t border-dark-border p-4"
            >
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder={t('typeMessage')}
                  className="flex-1 rounded-lg border border-dark-border bg-dark-surface px-4 py-2 text-text-primary placeholder-text-secondary focus:border-status-star focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={sending || !newMessage.trim()}
                  className="rounded-lg bg-status-star px-4 py-2 text-dark-bg hover:bg-status-star/90 disabled:opacity-50"
                >
                  <Send className="h-5 w-5" />
                </button>
              </div>
            </form>
          </>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <MessageCircle className="mx-auto mb-4 h-12 w-12 text-text-secondary" />
              <p className="text-text-primary font-medium">
                {t('selectConversation')}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
