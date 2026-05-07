# ZASKA - Feature Documentation

## Overview
ZASKA is a global on-demand task marketplace with improved UX logic and professional design.

---

## Key Features Implemented

### 1. **Location System**
- **Primary location** (required): Main area where task will be performed
- **Additional zones**: Up to 2 nearby zones can be added
- Visual tags display selected zones
- Map interface with clear pin selection

**Flow**: Post Task → Step 3 → Location Selector Component

---

### 2. **Task Matching & Application System**

#### Client Side:
- Post task with budget
- View "Typical range" for pricing guidance
- Receive applications from taskers
- See top 3-5 applicants ranked by:
  - Distance
  - Rating
  - Availability
- Accept or reject price proposals
- Select tasker manually or wait for auto-selection

#### Tasker Side:
- Browse available tasks near location
- **Apply** to tasks (not direct acceptance)
- Two pricing options:
  1. **Accept client budget** (recommended - higher selection chance)
  2. **Propose custom price** (one chance only)
- See task details: distance, budget, category

**Flows**:
- Client: Home → View Applicants → Select Tasker
- Tasker: Browse Tasks → Apply → Choose Pricing

---

### 3. **Pricing & Negotiation**

- Client sets initial budget
- Taskers can propose different prices
- Visual indicators show:
  - Price changes (higher/lower)
  - Percentage difference
  - Color coding (green=lower, red=higher)
- Client receives notification for price proposals
- Accept/Reject buttons for quick decisions

---

### 4. **Task Status System**

Five clear stages:
1. **Posted** - Task is live, accepting applications
2. **Applications received** - Taskers have applied
3. **In progress** - Tasker is working
4. **Completed** - Task marked as done
5. **Paid** - Payment released to tasker

Visual progress bar shows current stage in task detail view.

---

### 5. **Completion & Payment Flow**

1. Tasker marks task as "Done"
2. Client sees **Confirm Completion** screen
3. Options:
   - Confirm immediately
   - Use 4-digit OTP code (optional security)
   - Report an issue
4. Payment states:
   - **Escrow**: Held during task
   - **In progress**: Task active
   - **Released**: Sent to tasker after confirmation

**Flow**: Task Detail → Complete Task → Confirm Completion → Payment Released

---

### 6. **Messaging System**

Full chat interface within tasks:
- Real-time text messages
- Send images (button available)
- Share location (button available)
- Direct call button
- Active status indicator
- Message timestamps

**Access**: Task Detail → Chat Button

---

### 7. **Task Availability Logic**

- **Posted**: Visible to all nearby taskers
- **Accepted**: Removed from public listing
- **Rejected/Canceled**: Returns to available tasks
- Auto-hide after selection to prevent double-booking

---

### 8. **Tasker Experience**

Browse Screen shows:
- Task title and description
- Distance from tasker
- Client's budget
- Estimated time
- Urgent flag (if applicable)
- Category

Apply Screen features:
- Radio selection for pricing
- Budget acceptance (recommended)
- Custom proposal input
- Tips for better selection chances

---

### 9. **Admin & Support Panels**

#### Admin Dashboard:
- **Key Metrics**:
  - Tasks per day
  - Revenue
  - Active users
  - Disputes count
- Recent activity feed
- Visual indicators for trends

#### Call Center Panel:
- Support ticket queue
- Priority levels (Urgent, High, Normal)
- Ticket types:
  - Incomplete accounts
  - Flagged tasks
  - Support requests
- Quick actions:
  - Call user
  - Validate account
  - Resolve issue

**Access**: Demo Navigation → Admin/Support sections

---

## UX Principles Applied

✅ **One main action per screen**
✅ **No complex options** - Clear choices
✅ **Direct microcopy** - "Apply", "Confirm", "Done"
✅ **Visual feedback** - Status badges, progress bars, color coding
✅ **Minimal text** - Information hierarchy
✅ **Fast navigation** - Bottom tabs, back buttons

---

## Design System

### Colors:
- **Primary**: #6D28D9 (Violet)
- **Secondary**: #1E40AF (Blue)
- **Success**: #22C55E (Green)
- **Background**: #FFFFFF / #0B0F19 (Dark)

### Typography:
- **Font**: Poppins
- **Weights**: 400, 500, 600, 700, 800

### Components:
- Rounded corners: 12-16px
- Soft shadows for cards
- Clear spacing system
- Consistent button styles

---

## Navigation Map

```
Splash → Onboarding → Demo Navigation
                          ↓
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
    Main App         Tasker Side      Admin/Support
        ↓                 ↓                 ↓
    - Home            - Browse Tasks    - Admin Dashboard
    - Post Task       - Apply           - Call Center
    - Applicants      
    - Task Detail     
    - Chat            
    - Completion      
    - Wallet          
    - Profile         
```

---

## Demo Access

After onboarding, users land on **Demo Navigation** screen with access to:
- All client flows
- All tasker flows
- Admin panels
- Support center

This allows complete exploration of ZASKA's features.

---

## Security Features

- OTP verification for task completion (optional)
- Escrow payment system
- Account verification badges
- Report issue functionality
- Admin monitoring dashboard

---

## Future Enhancement Suggestions

1. Real-time location tracking
2. Push notifications
3. Multi-language support
4. In-app payments integration
5. Rating system refinement
6. Task templates
7. Favorite taskers
8. Recurring tasks
