# Sikka Car - Design System

## Brand Identity
- **Name:** Sikka Car | سكة كار
- **Tagline (AR):** أكبر منصة لتأجير السيارات بين الأفراد في الكويت
- **Tagline (EN):** Kuwait's Largest Peer-to-Peer Car Rental Platform
- **Direction:** RTL (Arabic default), LTR (English toggle)

---

## Color Palette

### Dark Theme (Primary)
| Token             | Hex       | Usage                        |
|-------------------|-----------|------------------------------|
| dark-bg           | `#111111` | Page background              |
| dark-card         | `#1C1C1E` | Card / panel background      |
| dark-surface      | `#2A2A2E` | Input / nested backgrounds   |
| dark-border       | `#333333` | Default borders              |
| dark-border-light | `#444444` | Hover / focus borders        |

### Text
| Token          | Hex       | Usage                        |
|----------------|-----------|------------------------------|
| text-primary   | `#FFFFFF` | Headings, body text          |
| text-secondary | `#AAAAAA` | Descriptions, labels         |
| text-muted     | `#555555` | Disabled, placeholders       |

### Brand
| Token              | Hex       | Usage                        |
|--------------------|-----------|------------------------------|
| brand-solid        | `#1A1A2E` | Primary button background    |
| brand-solid-hover  | `#252540` | Primary button hover         |
| sikka-gold         | `#FFB800` | Logo accent, stars, CTAs     |

### Status
| Token          | Hex       | Usage                        |
|----------------|-----------|------------------------------|
| status-star    | `#FFB800` | Ratings, gold accent, active |
| status-success | `#4CAF50` | Success states               |
| status-warning | `#FF9800` | Warnings, errors             |

### Contextual Colors (used inline)
| Color              | Hex/Class          | Usage                   |
|--------------------|--------------------|-------------------------|
| Green (success)    | `green-400/500`    | Payment success, checks |
| Red (error)        | `red-400/500`      | Date conflicts, alerts  |

---

## Typography

### Font Family
- **Arabic:** IBM Plex Sans Arabic
- **Google Fonts URL:** `https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap`

### Font Weights
| Weight | Usage                              |
|--------|------------------------------------|
| 400    | Body text, descriptions            |
| 500    | Labels, secondary headings         |
| 600    | Buttons, nav items                 |
| 700    | Page titles, card headings, stats  |

### Font Sizes (Tailwind)
| Class     | Size   | Usage                    |
|-----------|--------|--------------------------|
| text-3xl  | 30px   | Page titles (h1)         |
| text-2xl  | 24px   | Section titles, stats    |
| text-lg   | 18px   | Card headings            |
| text-base | 16px   | Body text                |
| text-sm   | 14px   | Buttons, labels, inputs  |
| text-xs   | 12px   | Badges, chips, captions  |

---

## Spacing System

Uses Tailwind's default 4px grid:
| Class  | Value  | Common Usage                 |
|--------|--------|------------------------------|
| gap-2  | 8px    | Chip groups, tight lists     |
| gap-3  | 12px   | Form input grids             |
| gap-4  | 16px   | Form fields, card sections   |
| gap-6  | 24px   | Card grid, section spacing   |
| gap-8  | 32px   | Major sections               |
| p-4    | 16px   | Card inner padding (mobile)  |
| p-6    | 24px   | Card inner padding (desktop) |
| py-8   | 32px   | Page vertical padding        |

---

## Border Radius

| Class        | Radius | Usage                          |
|--------------|--------|--------------------------------|
| rounded-full | 9999px | Chips, filter buttons, avatars |
| rounded-2xl  | 16px   | Cards, panels, modals          |
| rounded-xl   | 12px   | Buttons, inputs, badges        |
| rounded-lg   | 8px    | Small elements, icons          |

---

## Components

### Card
```
Background: dark-card (#1C1C1E)
Border: 1px solid dark-border (#333333)
Radius: rounded-2xl (16px)
Padding: p-6 (24px)
Shadow: shadow-sm → shadow-md on hover
```

### Button - Primary (Solid)
```
Background: brand-solid (#1A1A2E)
Hover: brand-solid-hover (#252540)
Text: text-primary (#FFFFFF)
Radius: rounded-xl (12px)
Padding: px-6 py-3.5
Font: text-sm font-medium
Shadow: shadow-lg
```

### Button - Secondary (Outline)
```
Background: transparent
Border: 1px solid dark-border (#333333)
Hover: bg-dark-surface (#2A2A2E)
Text: text-primary (#FFFFFF)
Radius: rounded-xl (12px)
Padding: px-6 py-3
```

### Button - Gold Accent
```
Background: status-star/10 (10% opacity)
Border: 1px solid status-star/30
Text: status-star (#FFB800)
Hover: status-star/20
Radius: rounded-xl (12px)
```

### Filter Chip - Active
```
Background: status-star (#FFB800)
Text: dark-bg (#111111)
Radius: rounded-full
Padding: px-3 py-1.5
Font: text-xs font-medium
```

### Filter Chip - Inactive
```
Background: dark-surface (#2A2A2E)
Border: 1px solid dark-border-light (#444444)
Text: text-secondary (#AAAAAA)
Hover: bg-dark-border (#333333)
```

### Input Field
```
Background: dark-surface (#2A2A2E)
Border: 1px solid dark-border (#333333)
Focus Border: dark-border-light (#444444)
Focus Ring: 2px dark-border/50
Text: text-primary (#FFFFFF)
Placeholder: text-muted (#555555)
Radius: rounded-xl (12px)
Padding: px-4 py-3
Font: text-sm
```

### Status Badge
```
Approved:  bg-green-500/10, text-green-400, border-green-500/20
Pending:   bg-orange-500/10, text-orange-400, border-orange-500/20
Rejected:  bg-red-500/10, text-red-400, border-red-500/20
```

### Stat Card
```
Background: dark-card/80 (80% opacity)
Border: 1px solid dark-border-light (#444444)
Radius: rounded-xl
Padding: px-4 py-3
Value: text-2xl font-bold (color varies)
Label: text-xs text-secondary
```

---

## Layout

### Container
```
Max Width: 80rem (1280px / max-w-7xl)
Padding: px-4 (16px)
Center: mx-auto
```

### Grid Breakpoints
| Breakpoint | Width  | Columns (car grid) |
|------------|--------|---------------------|
| Mobile     | <640px | 1 column            |
| sm         | 640px  | 2 columns           |
| lg         | 1024px | 3 columns           |

### Bottom Navigation (Mobile)
```
Position: fixed bottom-0
Background: dark-bg (#111111)
Border-top: 1px solid dark-border
Min touch target: 44x44px
Icon: h-6 w-6
Label: text-xs
Active: status-star (#FFB800)
```

### Header
```
Position: sticky top-0 z-50
Background: dark-bg with backdrop-blur-md
Border-bottom: 1px solid dark-border
Height: ~56px (py-3)
Logo: Car icon (status-star) + "Sikka Car" text
```

---

## Icons

Using **Lucide React** icon library.

Key icons used:
| Icon              | Usage                  |
|-------------------|------------------------|
| Car               | Logo, empty states     |
| Search            | Search bar             |
| SlidersHorizontal | Filter toggle          |
| Calendar          | Date inputs            |
| Clock             | Time inputs            |
| CreditCard        | Payment/booking button |
| Star              | Ratings                |
| Shield            | Admin panel            |
| MapPin            | Location               |
| Mail              | Email                  |
| Phone             | Phone                  |
| ArrowUpDown       | Sort dropdown          |
| CheckCircle       | Success states         |
| AlertTriangle     | Warnings               |
| Home              | Bottom nav             |
| PlusCircle        | Add car                |
| LayoutDashboard   | Dashboard              |

---

## Pages & Screens

1. **Home** `/` - Hero + stats + featured cars + why us + how it works + footer
2. **Browse** `/browse` - Search + filters + sort + car grid
3. **Car Detail** `/cars/[id]` - Gallery + specs + owner + reviews + booking panel
4. **List Car** `/list` - Multi-section form (basic, details, images)
5. **Edit Car** `/edit/[id]` - Same form pre-filled
6. **Dashboard** `/dashboard` - My cars (with bookings) + my bookings (with reviews)
7. **Admin** `/admin` - Stats + cars/bookings/users management (tabs)
8. **Contact** `/contact` - Info cards + form (2-column)
9. **Payment Success** `/payment-success` - Success icon + links
10. **Sign In/Up** - Clerk themed pages

---

## Animations & Transitions

- All interactive elements: `transition-all` or `transition-colors`
- Card hover: shadow-sm → shadow-md
- Spinner: `animate-spin` (Loader2 icon)
- Scroll: `scroll-behavior: smooth`

---

## Figma Setup Tips

1. Create a **dark frame** (#111111) as your base
2. Set up **Auto Layout** with 16px/24px padding to match cards
3. Use **IBM Plex Sans Arabic** font (download from Google Fonts)
4. Create **color styles** matching the table above
5. Build atomic components: Button, Input, Card, Chip, Badge, StatCard
6. Assemble pages from components
7. Use **RTL text direction** as default for Arabic layouts
