# SageMaster Signal Copier — Marketing Website Content

> **For**: Lovable (AI website builder). This document contains all copy, brand guidelines, SEO strategy, and design direction needed to build the commercial landing page. Every section is production-ready — use as-is.

---

## 1. Brand Guidelines

### 1.1 Brand Name
**SageMaster Signal Copier** (or just **Signal Copier** when contextually clear)

### 1.2 Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| **Primary (CTA/Accent)** | Emerald Green | `#34D399` | Buttons, links, active states, highlights |
| **Primary Dark** | Deep Emerald | `#047857` | Hover states, light-mode primary |
| **Background (Dark)** | Rich Charcoal | `#1E1E22` | Page background (dark mode hero) |
| **Surface (Dark)** | Warm Zinc | `#2A2A2F` | Cards, sections on dark backgrounds |
| **Surface Elevated** | Light Zinc | `#35353B` | Hover states, nested containers |
| **Border** | Subtle Gray | `#3A3A40` | Card borders, dividers |
| **Text Primary** | Near White | `#ECECEC` | Headings, body text on dark |
| **Text Secondary** | Muted Gray | `#8A8A94` | Descriptions, captions |
| **Success** | Emerald | `#10B981` | Success indicators, checkmarks |
| **Error/Destructive** | Rose | `#F43F5E` | Error states, warnings |
| **Warning** | Amber | `#F59E0B` | Caution indicators |
| **Light BG** | Near White | `#FAFAFA` | Light mode background |
| **Light Card** | Pure White | `#FFFFFF` | Light mode cards |

**Design philosophy**: Dark-mode-first (fintech/trading aesthetic). The hero and above-fold sections should always be dark. Lower sections can alternate dark/light for visual rhythm.

### 1.3 Typography

| Role | Font | Weight | Fallback |
|------|------|--------|----------|
| **Headings** | Inter | 600–700 (Semibold/Bold) | system-ui, sans-serif |
| **Body** | Inter | 400 (Regular) | system-ui, sans-serif |
| **Mono/Data** | JetBrains Mono | 400–500 | monospace |

### 1.4 Tone of Voice
- **Confident but not arrogant**: We know this product solves a real problem
- **Clear, not clever**: Traders value directness over marketing fluff
- **Technical when needed**: Our audience understands trading terminology (TP, SL, breakeven)
- **Action-oriented**: Every section drives toward a CTA
- **No jargon about us**: Avoid "leveraging AI synergies" — say "AI parses your signals in under 2 seconds"

### 1.5 Logo Direction
- Mark: Stylized signal/wave icon or arrow icon in emerald green
- Wordmark: "Signal Copier" in Inter Bold, clean spacing
- Tagline lockup: "by SageMaster" in smaller muted text below

---

## 2. SEO Strategy

### 2.1 Target Keywords

**Primary (High Intent)**:
- telegram signal copier
- copy telegram trading signals
- telegram to mt4 copier
- automated telegram signal copier
- telegram forex signal copier

**Secondary (Feature-Based)**:
- ai signal parser
- telegram signal bot
- copy trading signals automatically
- telegram to sagemaster
- forex signal automation
- crypto signal copier telegram

**Long-Tail**:
- how to copy telegram trading signals automatically
- best telegram signal copier for forex
- automate telegram signals to broker
- telegram signal copier no vps
- cloud based telegram signal copier

### 2.2 Page Meta Tags

```html
<title>Signal Copier — Automate Telegram Trading Signals | SageMaster</title>
<meta name="description" content="Automatically copy trading signals from Telegram to your SageMaster account. AI-powered parsing, multi-destination routing, no VPS required. Start free." />
<meta name="keywords" content="telegram signal copier, copy trading signals, forex signal automation, telegram to broker, AI signal parser" />

<!-- Open Graph -->
<meta property="og:title" content="Signal Copier — Automate Telegram Trading Signals" />
<meta property="og:description" content="AI-powered signal copier that routes Telegram trading signals to your SageMaster accounts instantly. No VPS, no EAs, just connect and go." />
<meta property="og:type" content="website" />
<meta property="og:image" content="/og-image.png" />

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Signal Copier — Automate Telegram Trading Signals" />
<meta name="twitter:description" content="Copy Telegram signals to SageMaster automatically. AI parsing, multi-destination routing, cloud-based." />
```

### 2.3 URL Structure
- Homepage: `/`
- Pricing: `/#pricing`
- Features: `/#features`
- FAQ: `/#faq`
- Login: `/login`
- Register: `/register`
- Blog (future): `/blog/`

### 2.4 Structured Data (JSON-LD)

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "SageMaster Signal Copier",
  "applicationCategory": "FinanceApplication",
  "operatingSystem": "Web",
  "offers": [
    { "@type": "Offer", "price": "0", "priceCurrency": "USD", "name": "Free" },
    { "@type": "Offer", "price": "29", "priceCurrency": "USD", "name": "Starter" },
    { "@type": "Offer", "price": "59", "priceCurrency": "USD", "name": "Pro" },
    { "@type": "Offer", "price": "99", "priceCurrency": "USD", "name": "Elite" }
  ],
  "description": "AI-powered Telegram signal copier that routes trading signals to SageMaster accounts via webhook."
}
```

---

## 3. Page Sections (Full Copy)

### 3.1 Navigation Bar

**Links**: Features | How It Works | Pricing | FAQ
**CTA Button** (right-aligned): `Get Started Free`
**Logo**: Signal Copier wordmark (left-aligned)

**Design**: Sticky/fixed nav, transparent on hero → solid dark on scroll. Emerald CTA button.

---

### 3.2 Hero Section

**Headline**:
> Automate Your Telegram Signals. Instantly.

**Subheadline**:
> AI-powered signal copier that reads your Telegram channels, parses trading signals in real-time, and routes them to your SageMaster accounts — in under 2 seconds. No VPS. No EAs. Just connect and go.

**Primary CTA**: `Start Free — No Credit Card Required`
**Secondary CTA**: `See How It Works` (scrolls to How It Works section)

**Hero Visual**: Dark dashboard mockup screenshot showing the Signal Copier dashboard with recent signals table, status indicators, and routing rules. Subtle emerald glow/gradient behind the mockup.

**Trust Indicators** (below hero):
> Trusted by 500+ traders | 50,000+ signals routed | 99.9% uptime

**Design Notes**:
- Full-width dark section with subtle radial gradient (emerald tint center, fading to charcoal)
- Dashboard mockup floating with slight perspective tilt and shadow
- Animated typing effect on headline (optional)
- Green-to-transparent gradient border on the dashboard mockup

---

### 3.3 Social Proof / Trust Bar

**Logos or Text Strip**:
> Works with **SageMaster Forex** | **SageMaster Crypto** | **Custom Webhooks**

**Design**: Horizontal strip with muted logos or text, subtle separator line above and below.

---

### 3.4 How It Works (3 Steps)

**Section Headline**: How It Works
**Section Subheadline**: Three steps to fully automated signal routing

**Step 1: Connect**
- **Icon**: Telegram logo or link icon
- **Headline**: Connect Your Telegram
- **Body**: Link your Telegram account securely. We use end-to-end encrypted sessions — your credentials are never stored.

**Step 2: Configure**
- **Icon**: Settings/route icon
- **Headline**: Set Up Your Routes
- **Body**: Choose which channels to monitor, set your destination webhooks, configure symbol mappings, and pick which signal types to forward.

**Step 3: Automate**
- **Icon**: Lightning bolt or play icon
- **Headline**: Signals Flow Automatically
- **Body**: Our AI parses every signal in real-time and routes it to your SageMaster accounts. Monitor everything from your dashboard.

**Design Notes**:
- Horizontal 3-column layout on desktop, vertical stack on mobile
- Connected by a horizontal line/arrow between steps
- Each step has a numbered circle (1, 2, 3) in emerald
- Dark background section with subtle card elevation for each step
- Optional: Animated step reveal on scroll

---

### 3.5 Features Grid

**Section Headline**: Everything You Need to Copy Signals Like a Pro
**Section Subheadline**: Built for traders who take automation seriously

**Feature 1: AI-Powered Parsing**
- **Icon**: Brain / sparkle icon
- **Headline**: AI Signal Parsing
- **Body**: GPT-4o-mini reads and understands any signal format — structured, conversational, or abbreviated. Extracts symbol, direction, entry, SL, and TP automatically.

**Feature 2: Multi-Destination Routing**
- **Icon**: Git branch / split arrow icon
- **Headline**: Route to Multiple Accounts
- **Body**: Send the same signal to up to 15 SageMaster accounts simultaneously. Each destination gets its own symbol mappings, risk settings, and payload format.

**Feature 3: Real-Time Processing**
- **Icon**: Zap / lightning icon
- **Headline**: Under 2 Seconds End-to-End
- **Body**: From signal detection in Telegram to webhook dispatch — your signals arrive at SageMaster in under 2 seconds. Cloud-based, always on.

**Feature 4: Symbol Mapping**
- **Icon**: Arrows swap icon
- **Headline**: Per-Destination Symbol Mapping
- **Body**: Map signal symbols to your broker's conventions. GOLD becomes XAUUSD, BTC becomes BTCUSD — automatically, per destination.

**Feature 5: Smart Filtering**
- **Icon**: Filter icon
- **Headline**: Action & Keyword Filters
- **Body**: Choose which signal types to forward (entry, close, breakeven). Block signals containing specific keywords. Full control over what reaches your accounts.

**Feature 6: Full Signal Logs**
- **Icon**: List / clipboard icon
- **Headline**: Complete Audit Trail
- **Body**: Every signal is logged with the original message, AI-parsed data, webhook payload, and delivery status. Filter by status, route, or time period.

**Feature 7: No VPS Required**
- **Icon**: Cloud icon
- **Headline**: 100% Cloud-Based
- **Body**: No VPS rental, no MT4/MT5 EAs to install, no software to maintain. Connect from any browser and your signals flow 24/7.

**Feature 8: Bank-Grade Security**
- **Icon**: Shield / lock icon
- **Headline**: Encrypted & Secure
- **Body**: Telegram sessions encrypted with AES-256-GCM. Passwords hashed with bcrypt. All data transmitted over TLS 1.3. We never store your trading credentials.

**Design Notes**:
- 2x4 grid on desktop, 2x2 on tablet, 1-column on mobile
- Dark cards with subtle border, icon in emerald circle
- Slight hover animation (lift + border glow)
- Alternating dark/slightly-lighter background to create depth

---

### 3.6 Use Cases / Who It's For

**Section Headline**: Built for Every Type of Trader
**Section Subheadline**: Whether you follow one channel or fifteen, Signal Copier scales with you

**Persona 1: The Forex Signal Follower**
- **Headline**: Forex Traders
- **Body**: Follow VIP Telegram signal channels and route them directly to your SageMaster Forex accounts. Support for V1 strategy triggers and V2 full signals with TP/SL.
- **Visual**: Forex chart iconography

**Persona 2: The Crypto Trader**
- **Headline**: Crypto Traders
- **Body**: Automate crypto signals from Telegram to SageMaster Crypto. Full support for Binance, exchange-specific payloads, and custom symbol formats.
- **Visual**: Crypto iconography

**Persona 3: The Multi-Account Manager**
- **Headline**: Account Managers
- **Body**: Route one signal channel to multiple client accounts with independent risk settings and symbol mappings per account. Elite plan supports up to 15 destinations.
- **Visual**: Multi-branch routing visual

**Persona 4: Signal Providers**
- **Headline**: Signal Providers
- **Body**: Recommend Signal Copier to your followers as the easiest way to automate your signals. No technical setup required — they just paste their webhook URL.
- **Visual**: Broadcasting/megaphone icon

**Design Notes**:
- 2x2 grid of cards with gradient top-borders (emerald accent)
- Each card has a small icon, headline, and 2-3 sentence description
- Optional: Background illustration of trading terminal lines

---

### 3.7 Pricing Table

**Section Headline**: Simple, Transparent Pricing
**Section Subheadline**: Start free. Upgrade when you need more routes.

| | **Free** | **Starter** | **Pro** | **Elite** |
|---|:---:|:---:|:---:|:---:|
| **Price** | $0/mo | $29/mo | $59/mo | $99/mo |
| **Active Routes** | 1 | 2 | 5 | 15 |
| **AI Signal Parsing** | Yes | Yes | Yes | Yes |
| **Symbol Mapping** | Yes | Yes | Yes | Yes |
| **Signal Logs** | Yes | Yes | Yes | Yes |
| **V1 Payloads** | Yes | Yes | Yes | Yes |
| **V2 Full Signal Payloads** | — | — | Yes | Yes |
| **Email Notifications** | — | Yes | Yes | Yes |
| **Telegram Notifications** | — | Yes | Yes | Yes |
| **Multiple Take Profits** | — | — | Yes | Yes |
| **Risk Overrides** | — | — | Yes | Yes |
| **Keyword Blacklist** | — | — | Yes | Yes |
| **Provider Commands** | — | — | — | Yes |
| **Priority Support** | — | — | — | Yes |
| **CTA** | `Start Free` | `Get Starter` | `Get Pro` | `Get Elite` |

**Below table note**: All plans include unlimited Telegram channels, unlimited signals, and 24/7 cloud operation. Annual billing saves 2 months.

**Design Notes**:
- Horizontal table on desktop, vertical cards on mobile
- **Pro** plan highlighted as "Most Popular" with emerald border/badge
- Dark background with card surfaces for each plan
- Checkmark icons (emerald) for included features, dash for excluded
- CTA buttons: Free = outline/ghost, Starter/Pro/Elite = solid emerald (Pro slightly larger)
- Annual/Monthly toggle above the table

---

### 3.8 Testimonials (Placeholder)

**Section Headline**: Trusted by Traders Worldwide

**Testimonial 1**:
> "I was spending 30 minutes a day copying signals manually. Now it's fully automated — I just check my dashboard in the morning."
> — **Ahmed K.**, Forex Trader

**Testimonial 2**:
> "The AI parsing is surprisingly accurate. It handles messy signal formats that other copiers choke on."
> — **James L.**, Crypto Trader

**Testimonial 3**:
> "I route signals to 8 different accounts with different risk settings. Couldn't do this with any other tool."
> — **Priya S.**, Account Manager

**Design Notes**: 3 cards in a row, avatar placeholder circles, star ratings, quote in italic, name + role below. Dark cards with subtle emerald accent on left border.

---

### 3.9 FAQ

**Section Headline**: Frequently Asked Questions

**Q: What is a Telegram Signal Copier?**
A: A Telegram Signal Copier is a tool that automatically reads trading signals from Telegram channels and forwards them to your trading platform. Instead of manually reading signals and placing orders, the copier does it for you in real-time.

**Q: How does the AI parsing work?**
A: We use GPT-4o-mini to read each Telegram message and extract structured trading data — the symbol, direction (buy/sell), entry price, stop loss, and take profit levels. It works with virtually any signal format, whether structured or conversational.

**Q: Do I need a VPS or MT4/MT5 running?**
A: No. Signal Copier is 100% cloud-based. Your signals are processed on our servers 24/7. No software to install, no VPS to rent, no EA to configure.

**Q: Is it safe to connect my Telegram?**
A: Yes. Your Telegram session is encrypted with AES-256-GCM (the same encryption used by banks). We never store your password. Your 2FA code is used once during authentication and immediately discarded.

**Q: What trading platforms does it support?**
A: Signal Copier routes signals to SageMaster Forex (sfx.sagemaster.io) and SageMaster Crypto (app.sagemaster.io) via webhook. It also supports custom webhook endpoints for advanced users.

**Q: Can I route signals to multiple accounts?**
A: Yes — this is a core feature. You can route one Telegram channel to multiple SageMaster accounts simultaneously. Each destination has its own symbol mappings and risk settings. The Elite plan supports up to 15 destinations.

**Q: What happens if a signal fails?**
A: Failed signals are logged with a detailed error message. You can view the original message, the AI-parsed data, and the exact webhook payload in the Signal Detail panel. Notifications can alert you to failures via email or Telegram.

**Q: What's the difference between V1 and V2 payloads?**
A: V1 is a strategy trigger — it sends the signal direction and symbol without price data (SageMaster handles entry/exit). V2 is a full signal with entry price, stop loss, take profit levels, and lot size included in the payload.

**Q: Can I try it for free?**
A: Yes. The Free plan includes 1 active route, AI signal parsing, and full signal logs — no credit card required. Upgrade anytime for more routes and advanced features.

**Q: How fast is signal processing?**
A: Under 2 seconds from Telegram message detection to webhook dispatch at your SageMaster account. Signals are processed in real-time, 24/7.

**Design Notes**: Accordion/collapsible FAQ. Dark section. Each question is a clickable row that expands to show the answer. Subtle emerald left-border on expanded items.

---

### 3.10 Final CTA Section

**Headline**:
> Ready to Automate Your Signals?

**Subheadline**:
> Join hundreds of traders who've stopped copying signals manually. Start with our free plan — no credit card, no setup fees, no strings attached.

**Primary CTA**: `Get Started Free`
**Secondary CTA**: `View Pricing`

**Design Notes**:
- Full-width dark section with centered text
- Subtle radial emerald gradient glow behind the CTA area
- Large CTA button (emerald, rounded, with hover glow effect)
- Optional: Floating dashboard mockup elements in the background (blurred, decorative)

---

### 3.11 Footer

**Column 1: Brand**
- Logo + "Signal Copier" wordmark
- One-line description: "AI-powered Telegram signal automation for SageMaster."
- Copyright: "(c) 2026 SageMaster. All rights reserved."

**Column 2: Product**
- Features
- Pricing
- FAQ
- Login
- Register

**Column 3: Resources**
- Documentation
- API Reference
- Status Page
- Changelog

**Column 4: Company**
- About SageMaster
- Contact
- Terms of Service
- Privacy Policy

**Bottom Bar**: Social media icons (Twitter/X, Telegram, Discord) | "Built with AI" badge

**Design Notes**: Dark footer (darker than page bg). 4-column grid on desktop, stacked on mobile. Muted text colors. Emerald hover on links.

---

## 4. Design Direction for Lovable

### 4.1 Overall Layout
- **Single-page marketing site** with anchor-linked sections
- **Dark-mode-first**: Hero and top sections on dark backgrounds
- **Section rhythm**: Alternate between full-dark sections and sections with slightly lighter dark surfaces
- **Max content width**: 1200px centered, with full-bleed backgrounds
- **Section spacing**: 80–120px vertical padding between sections

### 4.2 Component Suggestions
- **Buttons**: Rounded-lg (8px), emerald fill for primary, ghost/outline for secondary. Hover: slight glow + scale
- **Cards**: Rounded-2xl (16px), dark surface with 1px border, no box-shadow in dark mode
- **Icons**: Lucide icon set (or Heroicons). 24px in emerald circles (48px diameter)
- **Typography**: H1 = 48–56px bold, H2 = 32–40px semibold, H3 = 20–24px semibold, Body = 16–18px regular
- **Spacing**: 8px grid system (Tailwind default)

### 4.3 Animations (Subtle)
- **Scroll reveal**: Sections fade-in + slide-up on scroll entry (Framer Motion or CSS intersection observer)
- **Hero**: Slight float/bob animation on dashboard mockup
- **Steps connector**: Animated line drawing between steps on scroll
- **Pricing toggle**: Smooth slide between monthly/annual
- **FAQ**: Accordion open/close with smooth height transition
- **CTA button**: Subtle pulse/glow on emerald button

### 4.4 Responsive Breakpoints
- **Mobile**: < 640px — single column, hamburger nav, stacked pricing cards
- **Tablet**: 640–1024px — 2-column grids, condensed pricing table
- **Desktop**: 1024px+ — full layout, horizontal pricing table, 4-column footer

### 4.5 Key Visual Assets Needed
1. **Dashboard mockup**: Screenshot of the actual Signal Copier dashboard (dark mode) — can be provided as PNG
2. **OG image**: 1200x630px social share image with headline + dashboard preview
3. **Favicon**: Emerald signal icon (SVG, 32x32 and 16x16)
4. **Step illustrations**: Simple line icons for Connect, Configure, Automate
5. **Avatar placeholders**: For testimonials section

### 4.6 Performance
- Lazy-load images below the fold
- Preload Inter and JetBrains Mono fonts
- Critical CSS inline for above-fold content
- Target Lighthouse score: 90+ performance, 95+ accessibility

---

## 5. Sitemap & Page Structure

### 5.1 Page Hierarchy

```
signalcopier.sagemaster.io (or your domain)
│
├── /                          ← Marketing landing page (single-page, all sections below)
│   ├── #hero                  ← Hero section
│   ├── #how-it-works          ← 3-step flow
│   ├── #features              ← Feature grid
│   ├── #use-cases             ← Who it's for
│   ├── #pricing               ← Pricing table
│   ├── #testimonials          ← Social proof
│   ├── #faq                   ← FAQ accordion
│   └── #cta                   ← Final CTA
│
├── /login                     ← User login (separate page)
├── /register                  ← User registration (separate page)
├── /forgot-password           ← Password reset request (separate page)
├── /reset-password?token=...  ← Password reset form (separate page)
│
├── /terms                     ← Terms of Service (separate page)
├── /privacy                   ← Privacy Policy (separate page)
│
├── /app/                      ← Dashboard app (post-login, separate SPA)
│   ├── /app/                  ← Dashboard overview
│   ├── /app/telegram          ← Telegram connection
│   ├── /app/routing-rules     ← Route list
│   ├── /app/routing-rules/new ← Create route wizard
│   ├── /app/routing-rules/:id/edit ← Edit route
│   ├── /app/logs              ← Signal logs
│   └── /app/settings          ← Account settings
│
└── /404                       ← Not found page
```

### 5.2 Navigation Map

| From | Action | To |
|------|--------|----|
| Any page | Click logo | `/` (homepage) |
| Nav bar | Click "Features" | `/#features` |
| Nav bar | Click "How It Works" | `/#how-it-works` |
| Nav bar | Click "Pricing" | `/#pricing` |
| Nav bar | Click "FAQ" | `/#faq` |
| Nav bar | Click "Get Started Free" | `/register` |
| Hero | Click "Start Free" | `/register` |
| Hero | Click "See How It Works" | `/#how-it-works` (smooth scroll) |
| Pricing | Click "Start Free" (Free tier) | `/register` |
| Pricing | Click "Get Starter/Pro/Elite" | `/register?plan=starter` (pre-select plan) |
| Final CTA | Click "Get Started Free" | `/register` |
| Final CTA | Click "View Pricing" | `/#pricing` (smooth scroll) |
| Footer | Click "Login" | `/login` |
| Footer | Click "Register" | `/register` |
| Footer | Click "Terms of Service" | `/terms` |
| Footer | Click "Privacy Policy" | `/privacy` |
| Login page | Click "Register" | `/register` |
| Login page | Click "Forgot password?" | `/forgot-password` |
| Register page | Click "Sign in" | `/login` |
| Login success | Auto-redirect | `/app/` (dashboard) |
| Register success | Auto-redirect | `/app/setup` (onboarding wizard) |

---

## 6. Wireframe & Layout Specifications

### 6.1 Section-by-Section Layout

#### Navigation Bar
```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo]          Features  How It Works  Pricing  FAQ    [CTA] │
└─────────────────────────────────────────────────────────────────┘
```
- Height: 64px
- Logo: left-aligned, 32px mark + wordmark
- Nav links: center or right of logo, 14px Inter Medium, 24px gap between items
- CTA: right-aligned, emerald solid button, 14px, px-16 py-8
- Mobile: hamburger menu icon (right), sheet/drawer overlay with stacked links

#### Hero Section
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│              Automate Your Telegram Signals.                    │
│                       Instantly.                                │
│                                                                 │
│    AI-powered signal copier that reads your Telegram            │
│    channels, parses trading signals in real-time...             │
│                                                                 │
│        [Start Free — No Credit Card]  [See How It Works]        │
│                                                                 │
│              ┌──────────────────────────────┐                   │
│              │                              │                   │
│              │     Dashboard Mockup         │                   │
│              │     (perspective tilt)        │                   │
│              │                              │                   │
│              └──────────────────────────────┘                   │
│                                                                 │
│         500+ traders  ·  50,000+ signals  ·  99.9% uptime       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```
- **Desktop**: Headline H1 (48-56px) centered, max-width 800px
- **Subheadline**: 18px, muted text, max-width 640px, centered
- **CTAs**: Side by side, 16px gap. Primary = emerald solid. Secondary = ghost/outline
- **Mockup**: Max-width 900px, centered, 12px border-radius, subtle shadow
- **Trust stats**: 14px, muted text, dot separators, centered below mockup
- **Mobile**: Stack CTAs vertically, mockup full-width with horizontal scroll or scale down
- **Padding**: 120px top, 80px bottom

#### How It Works
```
┌─────────────────────────────────────────────────────────────────┐
│                      How It Works                               │
│          Three steps to fully automated signal routing           │
│                                                                 │
│    ┌─────────┐  ─────  ┌─────────┐  ─────  ┌─────────┐        │
│    │  (1)    │         │  (2)    │         │  (3)    │        │
│    │ Connect │         │Configure│         │Automate │        │
│    │         │         │         │         │         │        │
│    │ Link    │         │ Set up  │         │ AI      │        │
│    │ Telegram│         │ routes  │         │ parses  │        │
│    └─────────┘         └─────────┘         └─────────┘        │
└─────────────────────────────────────────────────────────────────┘
```
- **Desktop**: 3 equal columns, connected by horizontal dashed lines
- **Step card**: 280px wide, icon (48px emerald circle) + H3 headline + body text
- **Numbered circle**: 32px, emerald bg, white text, above icon
- **Mobile**: Vertical stack, connected by vertical line (left-aligned)
- **Section bg**: Slightly lighter dark surface (#2A2A2F)

#### Features Grid
```
┌─────────────────────────────────────────────────────────────────┐
│         Everything You Need to Copy Signals Like a Pro          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────┐ │
│  │ AI Parsing   │  │ Multi-Route  │  │ <2s Speed    │  │Map │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────┐ │
│  │ Filtering    │  │ Full Logs    │  │ No VPS       │  │Sec │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────┘ │
└─────────────────────────────────────────────────────────────────┘
```
- **Desktop**: 4-column grid, 24px gap
- **Tablet**: 2-column grid
- **Mobile**: 1-column stack
- **Card size**: Min-height 200px, padding 24px
- **Card structure**: Icon (top-left, 40px in 56px emerald/10% circle) → H3 headline → body text (14px muted)
- **Card hover**: translateY(-4px) + emerald border-glow transition 200ms

#### Pricing Table
```
┌─────────────────────────────────────────────────────────────────┐
│              Simple, Transparent Pricing                        │
│                                                                 │
│               [Monthly]  [Annual — Save 17%]                    │
│                                                                 │
│  ┌──────┐  ┌──────┐  ┌════════════┐  ┌──────┐                 │
│  │ Free │  │Start │  ║    Pro     ║  │Elite │                 │
│  │ $0   │  │ $29  │  ║    $59     ║  │ $99  │                 │
│  │      │  │      │  ║ POPULAR    ║  │      │                 │
│  │ 1 rt │  │ 2 rt │  ║ 5 routes   ║  │15 rt │                 │
│  │ ...  │  │ ...  │  ║ ...        ║  │ ...  │                 │
│  │[Free]│  │[Get] │  ║  [Get]     ║  │[Get] │                 │
│  └──────┘  └──────┘  ╚════════════╝  └──────┘                 │
└─────────────────────────────────────────────────────────────────┘
```
- **Desktop**: 4 cards side by side, Pro card slightly elevated (+8px) with emerald border + "Most Popular" badge
- **Mobile**: Vertical stack, Pro card first (reordered to top)
- **Card width**: Equal (25% - gap), min 240px
- **Card structure**: Plan name → Price (large, 36px) → "/mo" (14px muted) → Feature checklist → CTA button
- **Annual toggle**: Pill-style toggle above cards, shows strikethrough monthly price when annual selected
- **Annual prices**: Free=$0, Starter=$24/mo ($290/yr), Pro=$49/mo ($590/yr), Elite=$82/mo ($990/yr)

#### FAQ
```
┌─────────────────────────────────────────────────────────────────┐
│              Frequently Asked Questions                          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ ▸ What is a Telegram Signal Copier?                     │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │ ▾ How does the AI parsing work?                         │    │
│  │   We use GPT-4o-mini to read each Telegram message...  │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │ ▸ Do I need a VPS or MT4/MT5 running?                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```
- **Max-width**: 720px centered
- **Row height**: 56px collapsed, auto expanded
- **Chevron**: Right-aligned, rotates 180deg on open
- **Expanded answer**: 14-16px, muted text, padding 16px bottom
- **Divider**: 1px border between items

---

## 7. Interaction Specifications

### 7.1 Navigation
| Element | Hover | Click | Active |
|---------|-------|-------|--------|
| Nav link | text-white (from muted) | Smooth scroll to anchor | Underline or bold |
| Nav CTA | Emerald glow + slight scale(1.02) | Navigate to /register | — |
| Mobile hamburger | bg-muted/50 | Open sheet overlay | X close icon |
| Logo | opacity 0.8 → 1 | Navigate to / | — |

### 7.2 Hero
| Element | Hover | Click |
|---------|-------|-------|
| Primary CTA | Glow shadow + scale(1.02) | Navigate to /register |
| Secondary CTA | Text brightness increase | Smooth scroll to #how-it-works |
| Dashboard mockup | None (decorative) | None |

### 7.3 Features
| Element | Hover | Click |
|---------|-------|-------|
| Feature card | translateY(-4px) + emerald border glow | None (informational) |

### 7.4 Pricing
| Element | Hover | Click |
|---------|-------|-------|
| Monthly/Annual toggle | — | Switches prices, animates card values |
| Plan CTA button | Glow + scale | Navigate to /register?plan={tier} |
| Plan card | Slight border brightness | None |

### 7.5 FAQ
| Element | Hover | Click |
|---------|-------|-------|
| FAQ row | bg slightly lighter | Toggle accordion open/close, 200ms ease |
| Chevron icon | — | Rotates 180deg with transition |

### 7.6 Scroll Behaviors
- **Nav**: Transparent bg (hero) → solid dark bg with border-bottom on scroll past 80px
- **Sections**: Fade-in + translateY(20px→0) when entering viewport (IntersectionObserver, threshold 0.1)
- **Smooth scroll**: All anchor links use `scroll-behavior: smooth` with 80px offset (nav height)

---

## 8. Auth Pages (Login / Register / Password Reset)

### 8.1 Login Page (`/login`)

**Layout**: Centered card on dark background, max-width 400px

```
┌────────────────────────────────┐
│        Signal Copier           │
│        [Logo Mark]             │
│                                │
│  Email                         │
│  ┌────────────────────────┐   │
│  │ you@example.com        │   │
│  └────────────────────────┘   │
│                                │
│  Password                      │
│  ┌────────────────────────┐   │
│  │ ••••••••               │   │
│  └────────────────────────┘   │
│                                │
│              Forgot password?  │
│                                │
│  ┌────────────────────────┐   │
│  │      Sign In           │   │
│  └────────────────────────┘   │
│                                │
│  Don't have an account?        │
│  Register                      │
└────────────────────────────────┘
```

**Fields**:
| Field | Type | Placeholder | Validation | Error Message |
|-------|------|-------------|------------|---------------|
| Email | email | you@example.com | Required, valid email format | "Invalid email" |
| Password | password | •••••••• | Required, non-empty | "Password is required" |

**States**:
- **Default**: Form visible, button enabled
- **Loading**: Button shows "Signing in..." with spinner, inputs disabled
- **Error**: Toast notification at top-right: "Incorrect email or password"
- **Success**: Toast "Logged in successfully", redirect to `/app/`

**Links**:
- "Forgot password?" → `/forgot-password`
- "Register" → `/register`

### 8.2 Register Page (`/register`)

**Layout**: Same centered card as login

**Fields**:
| Field | Type | Placeholder | Validation | Error Message |
|-------|------|-------------|------------|---------------|
| Email | email | you@example.com | Required, valid email | "Invalid email" |
| Password | password | •••••••• | Required, min 8 chars | "Password must be at least 8 characters" |
| Confirm Password | password | •••••••• | Must match password | "Passwords do not match" |

**States**:
- **Default**: Form visible
- **Loading**: "Creating account..." with spinner
- **Error**: Toast with API error message (e.g., "Email already registered")
- **Success**: Toast "Account created", redirect to `/app/setup`

**Links**:
- "Already have an account? Sign in" → `/login`

**Query params**: `?plan=starter` pre-selects plan (shown as info banner: "You selected the Starter plan. You can upgrade after registration.")

### 8.3 Forgot Password Page (`/forgot-password`)

**Fields**:
| Field | Type | Placeholder | Validation |
|-------|------|-------------|------------|
| Email | email | you@example.com | Required, valid email |

**States**:
- **Default**: Form with "Send Reset Link" button
- **Loading**: "Sending..." with spinner
- **Submitted**: Form replaced with confirmation message: "Check your inbox. If an account exists for that email, we've sent a password reset link." + "Back to Login" link

### 8.4 Reset Password Page (`/reset-password?token=...`)

**Fields**:
| Field | Type | Validation | Error |
|-------|------|------------|-------|
| New Password | password | Min 8 chars | "Must be at least 8 characters" |
| Confirm Password | password | Must match | "Passwords do not match" |

**States**:
- **No token**: Error message "Invalid reset link. No token provided." + "Back to Login" link
- **Default**: Form with "Reset Password" button
- **Loading**: "Resetting..." with spinner
- **Success**: Toast "Password reset successfully", redirect to `/login`
- **Error**: Toast with API error (e.g., "Token expired")

---

## 9. Legal Pages

### 9.1 Terms of Service (`/terms`)

**Page layout**: Dark bg, centered content, max-width 720px, long-form text

**Section Structure**:
1. **Last Updated**: Date
2. **Acceptance of Terms**: By using Signal Copier you agree to these terms
3. **Service Description**: Cloud-based Telegram signal routing service; does NOT execute trades; routes signals to SageMaster webhooks
4. **Account Responsibilities**: Users responsible for account security; one account per person; must be 18+
5. **Subscription & Billing**: Free tier available; paid tiers billed monthly or annually; cancel anytime; no refunds for partial months
6. **Acceptable Use**: No abuse of API; no reverse engineering; no sharing of accounts; no automated scraping
7. **Telegram Integration**: Users authorize Signal Copier to access their Telegram channels; sessions encrypted at rest; user can revoke access at any time via disconnect
8. **Trading Disclaimer**: Signal Copier routes signals — it does NOT provide financial advice, execute trades, or guarantee trading outcomes; users trade at their own risk
9. **Data & Privacy**: Reference to Privacy Policy; data handling per GDPR principles
10. **Limitation of Liability**: Service provided "as is"; not liable for trading losses, signal delays, parsing errors, or webhook failures
11. **Termination**: We may suspend accounts violating terms; users can delete accounts at any time
12. **Changes to Terms**: We may update terms; users notified via email; continued use = acceptance
13. **Contact**: support@sagemaster.io

### 9.2 Privacy Policy (`/privacy`)

**Section Structure**:
1. **Last Updated**: Date
2. **Data We Collect**:
   - Account data: email, hashed password
   - Telegram data: phone number (for auth only), encrypted session string, channel list
   - Usage data: signal logs (raw messages, parsed data, webhook payloads, status)
   - Technical data: IP address, browser type (for security/rate limiting only)
3. **Data We Do NOT Collect**:
   - Trading account credentials
   - Broker login details
   - 2FA passwords (used once, immediately discarded)
   - Financial data or account balances
4. **How We Use Data**: Provide service, process signals, send notifications, improve parsing accuracy
5. **Data Storage & Security**:
   - PostgreSQL on Neon (encrypted at rest)
   - Telegram sessions: AES-256-GCM encryption
   - Passwords: bcrypt hashing
   - All transit: TLS 1.3
6. **Data Retention**: Signal logs retained for 90 days; account data retained until deletion
7. **Third-Party Services**: OpenAI (signal text sent for parsing — no PII), Upstash (message queue), Resend (email)
8. **Your Rights**: Access, export, delete your data; disconnect Telegram at any time; delete account via settings or email request
9. **Cookies**: Minimal — JWT token in localStorage (not cookies); no tracking cookies; no third-party analytics (optional: add Plausible/Fathom for privacy-respecting analytics)
10. **Contact**: privacy@sagemaster.io

---

## 10. Error & Utility Pages

### 10.1 404 Not Found Page

**Headline**: Page Not Found
**Body**: The page you're looking for doesn't exist or has been moved.
**CTA**: `Go to Homepage` (links to `/`)
**Secondary**: `Login to Dashboard` (links to `/login`)

**Design**: Centered on dark background, large "404" in muted text (200px, 10% opacity), headline and body below, CTA buttons centered

### 10.2 Loading State (Page Transition)

**Full-page loader**: Centered Signal Copier logo mark (32px) with subtle pulse animation
**Duration**: Show if page load takes >300ms (avoid flash for fast loads)
**Background**: Match page background color (dark)

### 10.3 Maintenance Page (Future)

**Headline**: We'll Be Right Back
**Body**: Signal Copier is undergoing scheduled maintenance. Your signals will resume automatically when we're back online.
**Subtext**: Estimated downtime: [X minutes]
**Status link**: Check status.sagemaster.io for updates

---

## 11. Image & Asset Specifications

### 11.1 Required Assets

| Asset | Dimensions | Format | Description |
|-------|-----------|--------|-------------|
| **Logo mark** | 32x32, 64x64 | SVG + PNG | Emerald signal/wave icon |
| **Logo wordmark** | 200x40 | SVG | "Signal Copier" text logo |
| **Logo + tagline** | 200x56 | SVG | Wordmark + "by SageMaster" |
| **Favicon** | 16x16, 32x32 | ICO + SVG | Logo mark |
| **Apple touch icon** | 180x180 | PNG | Logo mark on white bg |
| **OG image** | 1200x630 | PNG | Headline + dashboard preview |
| **Twitter card** | 1200x600 | PNG | Same as OG, cropped |
| **Dashboard mockup** | 1200x800 | PNG | Dark mode dashboard screenshot |
| **Step icons (x3)** | 48x48 | SVG | Connect, Configure, Automate |
| **Feature icons (x8)** | 40x40 | SVG | One per feature (use Lucide) |
| **Persona icons (x4)** | 48x48 | SVG | Forex, Crypto, Manager, Provider |
| **Avatar placeholders (x3)** | 48x48 | PNG/SVG | Circular, neutral |
| **Background gradient** | Full-width | CSS | Radial emerald-to-transparent |

### 11.2 Alt Text for Accessibility

| Image | Alt Text |
|-------|----------|
| Logo mark | "Signal Copier logo" |
| Dashboard mockup | "Signal Copier dashboard showing recent trading signals, connection status, and routing rules" |
| Step 1 icon | "Telegram connection icon" |
| Step 2 icon | "Route configuration icon" |
| Step 3 icon | "Automated signal processing icon" |
| OG image | "Signal Copier — Automate Telegram Trading Signals" |

### 11.3 Image Loading Strategy

| Position | Strategy |
|----------|----------|
| Logo | Inline SVG (no network request) |
| Hero mockup | `loading="eager"`, `fetchpriority="high"`, preload in `<head>` |
| Feature icons | Inline SVG or CSS sprite |
| Step icons | Inline SVG |
| Testimonial avatars | `loading="lazy"` |
| OG/Twitter images | Server-side only (meta tags) |

---

## 12. Mobile-Specific Copy Adjustments

### 12.1 Shortened Headlines (Mobile)

| Section | Desktop | Mobile |
|---------|---------|--------|
| Hero H1 | "Automate Your Telegram Signals. Instantly." | "Automate Your Signals." |
| Hero sub | Full 2-sentence paragraph | "AI-powered signal copier. No VPS, no EAs. Connect and go." |
| Features H2 | "Everything You Need to Copy Signals Like a Pro" | "Built for Signal Traders" |
| Use Cases H2 | "Built for Every Type of Trader" | "Who It's For" |
| Pricing H2 | "Simple, Transparent Pricing" | "Pricing" |
| Final CTA H2 | "Ready to Automate Your Signals?" | "Start Automating Today" |

### 12.2 Mobile Navigation

```
┌──────────────────────┐
│ [Logo]    [Hamburger] │
└──────────────────────┘

Sheet overlay (from right):
┌──────────────────────┐
│              [Close X]│
│                       │
│  Features             │
│  How It Works         │
│  Pricing              │
│  FAQ                  │
│                       │
│  ┌─────────────────┐ │
│  │ Get Started Free│ │
│  └─────────────────┘ │
│                       │
│  Login                │
└──────────────────────┘
```

### 12.3 Mobile Pricing
- Show Pro plan first (reorder from desktop)
- Vertical card stack, full width
- Collapsed feature list with "See all features" expandable
- Sticky bottom bar with CTA when scrolling pricing section

---

## 13. Complete CTA Destination Map

| Location | Button Text | Destination URL | Notes |
|----------|-------------|-----------------|-------|
| Nav bar | "Get Started Free" | `/register` | |
| Hero primary | "Start Free — No Credit Card Required" | `/register` | |
| Hero secondary | "See How It Works" | `/#how-it-works` | Smooth scroll |
| Pricing: Free | "Start Free" | `/register` | |
| Pricing: Starter | "Get Starter" | `/register?plan=starter` | Pre-select plan |
| Pricing: Pro | "Get Pro" | `/register?plan=pro` | Pre-select plan |
| Pricing: Elite | "Get Elite" | `/register?plan=elite` | Pre-select plan |
| Final CTA primary | "Get Started Free" | `/register` | |
| Final CTA secondary | "View Pricing" | `/#pricing` | Smooth scroll |
| Footer: Login | "Login" | `/login` | |
| Footer: Register | "Register" | `/register` | |
| Footer: Terms | "Terms of Service" | `/terms` | |
| Footer: Privacy | "Privacy Policy" | `/privacy` | |
| Footer: Documentation | "Documentation" | `https://docs.sagemaster.io` | External link |
| Footer: Status | "Status Page" | `https://status.sagemaster.io` | External link |
| Footer: Twitter/X | Twitter icon | `https://x.com/sagemaster` | External, new tab |
| Footer: Telegram | Telegram icon | `https://t.me/sagemaster` | External, new tab |
| Footer: Discord | Discord icon | `https://discord.gg/sagemaster` | External, new tab |
| 404: Homepage | "Go to Homepage" | `/` | |
| 404: Login | "Login to Dashboard" | `/login` | |
| Login: Register | "Register" | `/register` | |
| Login: Forgot | "Forgot password?" | `/forgot-password` | |
| Register: Login | "Sign in" | `/login` | |
| Forgot: Back | "Back to Login" | `/login` | |
