# ZASKA Hybrid Task Execution Model

## Overview
ZASKA now supports two distinct task execution modes to serve both local quick tasks and diaspora use cases.

---

## Task Modes

### ⚡ Fast Mode (Auto-Match)
**Best for:** Simple local tasks that need immediate attention

**How it works:**
1. Client posts task with fixed budget
2. Task is broadcast to nearby taskers
3. **First tasker to accept** gets the task immediately
4. No negotiation or selection process
5. Task is instantly removed from public feed

**Client Flow:**
```
Home → Choose Mode (Fast) → Post Task → Fast Matching → Task Accepted → Task Detail
```

**Tasker Flow:**
```
Browse Tasks → See "FAST" badge → Click "Accept now" → Task assigned immediately
```

**Characteristics:**
- ✅ Instant matching (3-5 seconds)
- ✅ No price negotiation
- ✅ First-come, first-served
- ✅ Best for urgent, simple tasks
- ❌ No tasker selection by client
- ❌ Fixed pricing

**Use Cases:**
- Grocery shopping
- Quick deliveries
- Local errands
- Time-sensitive pickups

---

### 🤝 Choose Mode (Select Tasker)
**Best for:** Important tasks, remote assistance, diaspora needs

**How it works:**
1. Client posts task with budget
2. Multiple taskers can apply
3. Taskers can propose different prices (one time only)
4. Client reviews 3-5 top applicants
5. Client selects preferred tasker
6. Task starts once client confirms selection

**Client Flow:**
```
Home → Choose Mode (Choose) → Post Task → Receive Applications → 
View Applicants → Select Tasker → Task Detail
```

**Tasker Flow:**
```
Browse Tasks → Click "Apply" → Choose pricing (Accept budget OR Propose price) → 
Submit Application → Wait for client selection
```

**Characteristics:**
- ✅ Review multiple applicants
- ✅ Price negotiation allowed (one counter-offer)
- ✅ Client has full control
- ✅ See ratings, distance, reviews
- ✅ Best for important tasks
- ❌ Takes longer to match
- ❌ Requires client decision

**Use Cases:**
- Remote assistance for family
- Important errands
- Specialized tasks
- Diaspora helping relatives abroad
- Tasks requiring trust/verification

---

## Mode Selection Screen

**Question:** "How do you want this done?"

**Options:**

### Fast Card
- Icon: ⚡ Zap
- Title: **Fast**
- Subtitle: "First available tasker accepts instantly"
- Description: "Best for simple local tasks"
- Badge: "Instant match"
- Color: Amber/Orange gradient
- Note: "⚡ No negotiation - First tasker to accept gets the task"

### Choose Card
- Icon: 🤝 Users
- Title: **Choose**
- Subtitle: "Receive offers and choose who you prefer"
- Description: "Best for important or remote tasks"
- Badge: "More control"
- Color: Purple gradient
- Note: "🤝 Recommended for diaspora - Review multiple offers before choosing"

---

## Task Matching Flows

### Fast Mode Matching

**Stage 1: Searching (3 seconds)**
- Animated loader with pulse effect
- Text: "Finding nearby taskers"
- Subtext: "This usually takes just a few seconds..."
- Background: Amber/Orange gradient
- Animated dots showing progress

**Stage 2: Matched (2 seconds)**
- Success animation
- Text: "Task accepted!"
- Subtext: "A tasker is ready to help"
- Shows matched tasker card:
  - Avatar with name
  - Rating
  - Distance
  - "Arriving soon" status
- Background: Green gradient
- Auto-redirects to task detail

### Choose Mode Matching

**Stage 1: Waiting for Applications**
- Standard matching screen
- Text: "Finding someone nearby..."
- Time: ~10-30 seconds for applications

**Stage 2: Applications Received**
- Redirect to Applicants screen
- Shows 3-5 taskers ranked by:
  1. Distance (closest first)
  2. Rating (highest first)
  3. Availability (immediate > later)

---

## Tasker Browse Screen

### Task Cards Show:
- Task title
- Distance from tasker
- Time estimate
- Price/budget
- **Mode indicator:**
  - ⚡ FAST badge (Amber/Orange)
  - No badge for Choose mode
- Urgent flag (if applicable)

### Action Buttons:
**For Fast Mode tasks:**
- Primary button: "⚡ Accept now"
- Single click → immediate assignment
- No price proposal option

**For Choose Mode tasks:**
- Primary button: "Apply to task"
- Click opens application screen
- Can propose custom price
- Subtext: "You can propose your own price"

---

## Pricing Logic

### Fast Mode:
- Client sets fixed budget
- No negotiation allowed
- Taskers see: "$XX total"
- Accept = task assigned at posted price
- Rejection = task returns to feed for others

### Choose Mode:
- Client sets initial budget
- Taskers can:
  1. Accept posted budget ✅ (recommended)
  2. Propose different price (one time only)
- Client sees price proposals with:
  - Visual indicators (higher/lower)
  - Percentage change
  - Original vs proposed price
  - Accept/Reject buttons
- Limit: One counter-offer per tasker

---

## Task Status Progression

### Fast Mode:
```
Posted → Fast Matching → Accepted → In Progress → Completed → Paid
```

### Choose Mode:
```
Posted → Applications Received → Accepted → In Progress → Completed → Paid
```

**Visual Indicator:**
- Progress bar with 5 stages
- Current stage highlighted
- Completed stages show checkmark
- Upcoming stages grayed out

---

## Location System (Diaspora Friendly)

**Primary Location** (Required):
- Map interface with pin
- Address autocomplete
- Used for distance calculations

**Additional Zones** (Optional):
- Add up to 2 nearby zones
- Displayed as tags
- Removable by clicking X
- Expands task visibility

**Example:**
- Primary: "123 Main St, Dakar, Senegal"
- Zone 1: "Plateau District"
- Zone 2: "Almadies"

**Use Case:**
Diaspora in USA posting task for relative in Senegal can specify multiple areas where help is needed.

---

## Payment & Completion

### Escrow System:
1. **Posted**: Client pays → funds in escrow
2. **In Progress**: Payment held securely
3. **Completed**: Tasker marks done
4. **Client Confirms**: Payment released to tasker

### Confirmation Options:
- **Standard**: Click "Confirm completion"
- **OTP Verification**: Enter 4-digit code (optional)
- **Report Issue**: Dispute process

---

## Availability Logic

### Task Visibility:
**Fast Mode:**
- Posted → visible to all nearby taskers
- First acceptance → immediately removed from feed
- Rejection → task returns to feed

**Choose Mode:**
- Posted → visible to all nearby taskers
- Applications → still visible (collecting offers)
- Client selection → removed from feed
- Rejection → task returns to feed

### Auto-Selection (Choose Mode):
- Optional timeout (e.g., 24 hours)
- If client doesn't select manually:
  - System auto-selects best-ranked applicant
  - Criteria: highest rating + closest distance

---

## Messaging System

**Available in both modes:**
- Real-time text chat
- Image sharing
- Location sharing
- Voice call button
- Active status indicator

**Access:** Task Detail → Chat Button

---

## Admin Monitoring

### Key Metrics:
- **Fast mode** adoption rate
- **Choose mode** adoption rate
- Average time to match (by mode)
- Task completion rate (by mode)
- Pricing variance (Choose mode)
- Geographic distribution

### Filters:
- By mode type
- By country/region
- By task category
- By user type (local vs diaspora)

---

## UX Principles

✅ **Clear mode distinction** - Visual badges and colors
✅ **One primary action** per screen
✅ **Minimal text** - Direct microcopy
✅ **Fast feedback** - Instant confirmations
✅ **Transparent pricing** - Show ranges and proposals
✅ **Trust indicators** - Ratings, distance, reviews

---

## Recommended Usage Guide

### Choose **Fast Mode** when:
- Task is simple and well-defined
- Price is non-negotiable
- Speed is critical
- Location is local
- Trust is less critical (commodity task)

### Choose **Choose Mode** when:
- Task is complex or important
- Flexibility in pricing is desired
- Quality/trust is paramount
- Task is remote (diaspora)
- Need to verify tasker credentials
- Time is less critical

---

## Implementation Notes

### Mode Badge in UI:
- **Fast**: `⚡ FAST` (Amber/Orange gradient, white text)
- **Choose**: `🤝 CHOOSE` (Purple gradient, white text)

### Color Coding:
- Fast Mode: Amber (#F59E0B) to Orange (#F97316)
- Choose Mode: Purple (#6D28D9) to Purple (#7C3AED)
- Success: Green (#22C55E)
- Alert: Red (#EF4444)

### Animations:
- Fast matching: Pulse + spinning loader
- Success: Scale-in + checkmark
- Mode selection: Ring highlight on select

---

This hybrid model serves both **speed-focused local users** and **trust-focused diaspora users** effectively!
