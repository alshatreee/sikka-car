'use client'

import { useState, useRef, useEffect } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import { Send, Loader2, BookOpen, ArrowRight, Info } from 'lucide-react'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: { title: string; source: string | null }[]
  hasContext?: boolean
}

export default function KazimaChatPage() {
  const { lang } = useLanguage()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    if (!input.trim() || isLoading) return

    const userMessage: ChatMessage = { role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const res = await fetch('/api/kazima-ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userMessage.content,
          conversationHistory: messages.slice(-6),
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: data.error || 'حدث خطأ' },
        ])
        return
      }

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources,
          hasContext: data.hasContext,
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: lang === 'ar' ? 'فشل الاتصال بالخادم' : 'Connection failed',
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-status-star/10 border border-status-star/20">
              <BookOpen className="h-5 w-5 text-status-star" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-text-primary">
                {lang === 'ar' ? 'محادثة كاظمة' : 'Kazima Chat'}
              </h1>
              <p className="text-xs text-text-muted">
                {lang === 'ar' ? 'اسأل عن المخطوطات والتاريخ الخليجي' : 'Ask about manuscripts & Gulf history'}
              </p>
            </div>
          </div>
          <Link
            href="/kazima"
            className="flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface"
          >
            {lang === 'ar' ? 'التحليل' : 'Analysis'}
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {/* Chat Area */}
        <div className="rounded-2xl border border-dark-border bg-dark-card overflow-hidden" style={{ height: 'calc(100vh - 280px)', minHeight: '400px' }}>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4" style={{ height: 'calc(100% - 72px)' }}>
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <BookOpen className="mb-4 h-12 w-12 text-text-muted" />
                <p className="text-sm font-medium text-text-secondary mb-2">
                  {lang === 'ar' ? 'اسأل كاظمة AI' : 'Ask Kazima AI'}
                </p>
                <p className="text-xs text-text-muted max-w-sm">
                  {lang === 'ar'
                    ? 'اسأل عن أعلام، أماكن، أحداث تاريخية، مخطوطات، أو أي موضوع يتعلق بالتراث الخليجي'
                    : 'Ask about scholars, places, historical events, manuscripts, or any Gulf heritage topic'}
                </p>
                <div className="mt-6 grid gap-2 sm:grid-cols-2">
                  {[
                    lang === 'ar' ? 'من هو عبدالله بن صباح؟' : 'Who was Abdullah bin Sabah?',
                    lang === 'ar' ? 'ما أهم مخطوطات تاريخ الكويت؟' : 'Key Kuwait history manuscripts?',
                    lang === 'ar' ? 'ما العلاقة بين آل صباح والزبير؟' : 'Al Sabah and Zubayr connection?',
                    lang === 'ar' ? 'أهم علماء الفقه في الخليج' : 'Notable Gulf fiqh scholars?',
                  ].map((suggestion, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(suggestion)}
                      className="rounded-xl border border-dark-border bg-dark-surface px-3 py-2 text-xs text-text-secondary transition-colors hover:border-dark-border-light hover:text-text-primary text-right"
                      dir="rtl"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-status-star/10 border border-status-star/20 text-text-primary'
                      : 'bg-dark-surface border border-dark-border text-text-primary'
                  }`}
                  dir="rtl"
                >
                  <p className="text-sm leading-[1.8] whitespace-pre-wrap">{msg.content}</p>

                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 border-t border-dark-border pt-2">
                      <p className="text-[10px] font-medium text-text-muted mb-1">
                        {lang === 'ar' ? 'المصادر:' : 'Sources:'}
                      </p>
                      {msg.sources.map((s, j) => (
                        <span key={j} className="inline-block mr-2 mb-1 rounded bg-dark-card px-2 py-0.5 text-[10px] text-text-secondary">
                          {s.title}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* No context warning */}
                  {msg.role === 'assistant' && msg.hasContext === false && (
                    <div className="mt-2 flex items-center gap-1 text-[10px] text-status-warning">
                      <Info className="h-3 w-3" />
                      {lang === 'ar' ? 'إجابة عامة — لا توجد مصادر في قاعدة كاظمة' : 'General answer — no sources in Kazima DB'}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-end">
                <div className="rounded-2xl bg-dark-surface border border-dark-border px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-status-star" />
                    <span className="text-xs text-text-muted">
                      {lang === 'ar' ? 'يبحث ويحلل...' : 'Searching & analyzing...'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-dark-border p-3">
            <div className="flex items-center gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                className="flex-1 resize-none rounded-xl border border-dark-border bg-dark-surface px-4 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light"
                placeholder={lang === 'ar' ? 'اكتب سؤالك هنا...' : 'Type your question...'}
                dir="rtl"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-solid text-text-primary transition-all hover:bg-brand-solid-hover disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
