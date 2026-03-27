# Sikka Car Messaging System Guide

## Overview
A complete peer-to-peer messaging system allowing car owners and renters to communicate directly, with optional booking context.

## Database
### Message Model
```prisma
model Message {
  id         String   @id @default(cuid())
  senderId   String
  receiverId String
  bookingId  String?
  content    String
  read       Boolean  @default(false)
  createdAt  DateTime @default(now())

  sender     User     @relation("SentMessages", fields: [senderId], references: [id])
  receiver   User     @relation("ReceivedMessages", fields: [receiverId], references: [id])
  booking    Booking? @relation(fields: [bookingId], references: [id])
}
```

To migrate the database:
```bash
npx prisma migrate dev --name add_messages
npx prisma generate
```

## Server Actions
Location: `/app/actions/messageActions.ts`

### Available Functions

#### sendMessage(receiverId, content, bookingId?)
Sends a message to another user.
- **receiverId**: Target user ID
- **content**: Message text
- **bookingId**: Optional booking context
- Returns: Message object with sender and receiver data

#### getConversations()
Gets all active conversations for current user.
- Returns: Array of conversation objects with:
  - `otherUserId`: Other user's ID
  - `otherUser`: User details
  - `lastMessage`: Most recent message
  - `unreadCount`: Number of unread messages

#### getMessages(otherUserId)
Gets message history with another user.
- **otherUserId**: Conversation participant ID
- Returns: Array of messages sorted chronologically

#### markAsRead(otherUserId)
Marks all messages from a user as read.
- **otherUserId**: Message sender ID

#### getUnreadCount()
Gets total unread message count.
- Returns: Integer count

## API Routes
Location: `/app/api/messages/`

### GET /api/messages/unread
Returns unread message count for authenticated user.
- Response: `{ count: number }`

## Pages & Components

### Messages Page
Location: `/app/messages/page.tsx`
- Server component that handles authentication
- Renders MessagesClient for UI

### MessagesClient Component
Location: `/app/messages/MessagesClient.tsx`
- Fully responsive client component
- Features:
  - Conversation list with last message preview
  - Message thread with real-time feel (10s refresh)
  - Message input with send button
  - Unread badges
  - Mobile-responsive layout
  - Bilingual interface (Arabic/English)

## Navigation
Messages are accessible through:
1. **Desktop Header** - `/messages` link with unread badge
2. **Mobile Bottom Nav** - MessageCircle icon with unread badge
3. **Mobile Menu** - Messages option in mobile menu

All navigation elements auto-update unread count every 30 seconds.

## Features

### Core Functionality
- [x] One-to-one messaging between users
- [x] Optional booking context
- [x] Read/unread tracking
- [x] Auto-mark as read when viewing conversation
- [x] Real-time-feel with periodic refresh

### UI/UX
- [x] Desktop split-view (conversations + thread)
- [x] Mobile responsive (toggle view)
- [x] Dark theme consistent with app
- [x] Bilingual Arabic/English
- [x] Unread badges in header and nav
- [x] Empty states for no messages
- [x] Message timestamps and formatting

### Security
- [x] Authentication required via middleware
- [x] Only authenticated users can send/receive messages
- [x] Current user required for all actions
- [x] `/messages` route is protected

## Styling Reference

### Theme Colors
- **Primary background**: `bg-dark-bg`
- **Cards**: `bg-dark-card`
- **Hover/active**: `bg-dark-surface`
- **Borders**: `border-dark-border`
- **Text primary**: `text-text-primary`
- **Text secondary**: `text-text-secondary`
- **Accent**: `bg-status-star` (gold)
- **Accent light**: `bg-status-star/20`

### Message Styling
- **Sent messages**: Gold background with accent border
- **Received messages**: Dark surface background
- **Unread badge**: Solid gold with dark text

## Development Notes

### Message Refresh Strategy
- Auto-refresh messages every 10 seconds
- Auto-refresh unread count every 30 seconds
- Prevents aggressive polling while maintaining responsive feel
- Can be adjusted in respective `setInterval` calls

### Performance
- Conversations are grouped by user
- Only latest message is stored per conversation pair
- Read status allows filtering unread messages
- Booking context is optional for general conversations

### Bilingual Support
Translations are managed in `/components/shared/LanguageProvider.tsx`:
```javascript
messages: { ar: 'الرسائل', en: 'Messages' },
noMessages: { ar: 'لا توجد رسائل', en: 'No messages' },
// ... etc
```

Access via `useLanguage()` hook:
```javascript
const { t, lang } = useLanguage()
t('messages') // Returns translated text
lang === 'ar' // Check if Arabic
```

## Testing Checklist

- [ ] Can send messages between users
- [ ] Unread count displays correctly
- [ ] Messages auto-mark as read
- [ ] Conversations list updates
- [ ] Mobile view switches correctly
- [ ] Messages refresh every 10 seconds
- [ ] Header badge updates every 30 seconds
- [ ] Arabic/English toggle works
- [ ] Protected route redirects unsigned users
- [ ] Empty states display when no messages

## Future Enhancements
- Typing indicators
- Message reactions/emojis
- File/image attachments
- Message search
- Message notifications
- Conversation archiving
- Block user functionality
- Message encryption
