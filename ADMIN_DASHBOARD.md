# ZASKA Admin & Call Center Dashboard

## Overview
Complete desktop-first admin panel for managing the ZASKA task marketplace platform.

---

## Design System

### Style Guide
- **Design Philosophy**: Clean, minimal, professional (Stripe/Notion style)
- **Layout**: Desktop-first (optimized for 1920px+)
- **Font**: System default (fallback ready for Inter)
- **Color Palette**:
  - Primary: #6D28D9 (Purple)
  - Success: #22C55E (Green)
  - Warning: #F59E0B (Amber)
  - Danger: #EF4444 (Red)
  - Gray Scale: 50, 100, 200...900
- **Components**: Cards, tables, simple charts
- **Spacing**: Consistent 24px grid

---

## Layout Structure

### Sidebar Navigation (256px fixed)
1. **Dashboard** - Main overview
2. **Tasks** - Task management
3. **Users** - User management
4. **Taskers** - Tasker management
5. **Payments** - Transaction & payouts
6. **Disputes** - Conflict resolution
7. **Countries** - Geographic control
8. **Call Center** - Support hub
9. **Settings** - Platform config

### Top Bar
- **Search Bar**: Global search across tasks, users, transactions
- **Notifications**: Bell icon with badge
- **Admin Profile**: User info and logout

### Main Content Area
- Dynamic page rendering
- Consistent padding (24px)
- Responsive to sidebar

---

## Pages Overview

### 1. Dashboard (Main Overview)

**KPI Cards (4 columns):**
- Tasks Today: 147 (+12%)
- Revenue Today: $4,235 (+8%)
- Active Users: 1,249 (+23%)
- Active Taskers: 892 (+15%)

**Data Tables:**
- Recent Tasks (ID, Title, Status, Price)
- Recent Payments (ID, Amount, Status, Method)

**Charts** (Future):
- Tasks per day (line chart)
- Revenue per day (bar chart)

**Purpose:** Real-time platform monitoring

---

### 2. Tasks Page

**Metrics:**
- Total tasks by status
- Filter by status (All, Posted, In progress, Done)

**Table Columns:**
- Task ID
- Title
- Location
- Status (badge)
- Price
- User
- Tasker
- Actions (View, Flag, Cancel)

**Actions:**
- View task details
- Flag task for review
- Cancel task (admin override)

**Purpose:** Complete task lifecycle management

---

### 3. Users Page

**Metrics:**
- Total Users: 1,249
- Verified: 892
- Pending: 234
- Incomplete: 123

**Table Columns:**
- User ID
- Name
- Email
- Phone
- Status (Verified/Pending/Incomplete)
- Tasks count
- Actions (Call, Message, Verify, Suspend)

**Actions:**
- Call user
- Send message
- Verify account manually
- Suspend user

**Purpose:** User account management and verification

---

### 4. Taskers Page

**Metrics:**
- Total Taskers: 892
- Active Today: 234
- Avg Rating: 4.8 ⭐
- Tasks Completed: 3,421

**Table Columns:**
- Tasker ID
- Name
- Email
- Rating (with reviews count)
- Completed tasks
- Status
- Actions (Call, Message, Verify, Ban)

**Actions:**
- Contact tasker
- Verify credentials
- Suspend/ban account

**Purpose:** Tasker quality control and management

---

### 5. Payments Page

**Metrics:**
- Total Revenue: $84,235 (+18%)
- Commission (15%): $12,635
- In Escrow: $5,420 (234 transactions)
- Pending Payouts: $2,180 (89 taskers)

**Table Columns:**
- Payment ID
- Task ID
- Amount
- Status (Released/Escrow/Pending)
- Method
- User
- Tasker
- Date

**Purpose:** Financial oversight and payout management

---

### 6. Disputes Page 🔴 CRITICAL

**Metrics:**
- Open Disputes: 2
- Under Review: 1
- Resolved Today: 8
- Total Amount: $140

**Table Columns:**
- Dispute ID
- Task ID
- User
- Tasker
- Issue description
- Amount
- Status (Open/Under review/Resolved)
- Created time
- Actions (Review chat, Approve payment, Refund, Resolve)

**Actions:**
- Review chat history
- Approve payment release
- Issue refund to user
- Mark as resolved

**Purpose:** Conflict resolution and customer satisfaction

---

### 7. Countries Page 🌍 CRITICAL

**Metrics:**
- Active Countries: 4
- Total Users: 6,996
- Total Tasks: 18,310
- Avg Commission: 15%

**Country Table:**
- Country Name
- Code (ISO)
- Status (Active/Disabled)
- Users count
- Tasks count
- Commission %
- Payment Methods
- Actions (Enable/Disable, Configure)

**Current Countries:**
- 🇸🇳 Senegal (Active)
- 🇳🇬 Nigeria (Active)
- 🇰🇪 Kenya (Active)
- 🇬🇭 Ghana (Active)
- 🇨🇮 Ivory Coast (Disabled)

**Actions:**
- Toggle country ON/OFF
- Set commission percentage
- Configure payment methods
- Add new country

**Purpose:** Control geographic expansion and localization

---

### 8. Call Center Page 📞 CORE FEATURE

**Quick Stats:**
- Pending Actions: 8
- Calls Today: 47
- Resolved Today: 38

**Section A: Users Needing Attention**
- Incomplete profiles
- KYC pending
- Phone not verified

**Table:** Name, Phone, Issue, Priority (High/Medium/Low)

**Actions:** Call, Verify

**Section B: Tasks with Issues**
- Stuck in matching
- No tasker response
- Payment pending

**Table:** Task ID, Issue, User, Time Stuck

**Actions:** Contact, Resolve

**Section C: Open Disputes**
- User vs tasker conflicts
- Payment disputes
- Quality issues

**Table:** Task ID, User, Tasker, Issue, Status

**Actions:** Review, Resolve

**Purpose:** Centralized support hub for quick issue resolution

---

## Component Library

### KPICard
```tsx
<KPICard 
  label="Tasks Today"
  value="147"
  change="+12%"
  icon={Briefcase}
  trend="up"
/>
```

### DataTable
```tsx
<DataTable
  columns={[...]}
  data={[...]}
  onRowClick={(row) => {}}
/>
```

### AdminLayout
- Sidebar navigation
- Top bar with search
- Main content wrapper

---

## User Flows

### Resolving a Dispute
```
Call Center → Open Disputes → Click Review →
View task chat history → Decide action →
Approve payment OR Refund user → Mark resolved
```

### Verifying a User
```
Call Center → Users Needing Attention →
Click user → Call button → Verify identity →
Click Verify → Status updated to "Verified"
```

### Enabling a New Country
```
Countries → Add Country → Select country →
Set commission % → Configure payment methods →
Toggle Active → Country goes live
```

### Handling Stuck Task
```
Call Center → Tasks with Issues →
See "No response" → Click Contact →
Call user/tasker → Manually resolve →
Force complete OR Cancel task
```

---

## Access Control (Future)

### Admin Roles:
1. **Super Admin** - Full access
2. **Financial Admin** - Payments, disputes only
3. **Support Agent** - Call center only
4. **Country Manager** - Country settings only

---

## Real-Time Features (Future)

- Live task updates
- Real-time notification badge
- WebSocket for instant alerts
- Live chat with users/taskers
- Dashboard auto-refresh

---

## Reports & Analytics (Future)

### Custom Reports:
- Revenue by country
- Task completion rates
- Average resolution time
- Tasker performance metrics
- User retention analysis

### Export Options:
- CSV export
- PDF reports
- Excel format
- Date range filters

---

## Mobile Responsiveness

Currently **desktop-optimized**. Mobile admin can use:
- Existing mobile admin screens (simplified version)
- Or responsive version (future enhancement)

---

## Security Features

### Implemented:
- Secure sidebar navigation
- Action confirmation (future)
- Audit logging (future)

### Planned:
- Two-factor authentication
- IP whitelisting
- Session timeout
- Activity logging
- RBAC (Role-based access control)

---

## Performance Considerations

- Lazy loading for large tables
- Pagination (100 items per page)
- Optimized re-renders
- Efficient data fetching
- Minimal bundle size

---

## Technical Stack

### Frontend:
- React 18.3.1
- TypeScript
- Tailwind CSS v4
- Lucide React (icons)
- Custom components

### Future Integrations:
- Chart.js / Recharts for graphs
- React Query for data fetching
- WebSockets for real-time
- Export libraries (csv, pdf)

---

## File Structure

```
/src/admin
  /components
    - AdminLayout.tsx (Sidebar + Top bar + Content wrapper)
    - KPICard.tsx (Metric cards)
    - DataTable.tsx (Reusable table)
  /pages
    - DashboardPage.tsx (Main overview)
    - TasksPage.tsx (Task management)
    - UsersPage.tsx (User management)
    - TaskersPage.tsx (Tasker management)
    - PaymentsPage.tsx (Financial management)
    - DisputesPage.tsx (Dispute resolution)
    - CountriesPage.tsx (Geographic control)
    - CallCenterPage.tsx (Support hub)
  - AdminApp.tsx (Main router)
```

---

## Navigation Integration

### Access Points:
1. **Mobile App** → Demo Navigation → "Admin Dashboard (Desktop)"
2. **Direct URL**: `/admin` (future)
3. **Mobile App** → Demo Navigation → "Admin Dashboard (Mobile)" (simplified)

---

## Key Metrics Dashboard Should Track

### Business Metrics:
- GMV (Gross Merchandise Value)
- Take rate (Platform commission %)
- Active user growth
- Task completion rate
- Average task value

### Operational Metrics:
- Time to match (Fast vs Choose)
- Support ticket resolution time
- Dispute rate
- Payment success rate
- Tasker retention rate

### Geographic Metrics:
- Revenue by country
- User distribution
- Task density by region
- Payment method preferences

---

## Success Criteria

### Call Center Efficiency:
- Average resolution time < 15 min
- First-call resolution > 80%
- User satisfaction > 4.5/5

### Financial Operations:
- Payment success rate > 98%
- Payout accuracy 100%
- Dispute resolution < 24h

### Platform Control:
- Country deployment time < 1 week
- Real-time monitoring coverage 100%
- Zero unauthorized access

---

## Deployment Checklist

- [ ] Backend API integration
- [ ] Authentication system
- [ ] Role-based permissions
- [ ] Real-time WebSocket setup
- [ ] Export functionality
- [ ] Chart integration
- [ ] Mobile responsive version
- [ ] Production deployment
- [ ] Admin user training

---

## Conclusion

The ZASKA Admin Dashboard provides:
✅ **Complete platform oversight**
✅ **Fast dispute resolution**
✅ **Country-level control**
✅ **Centralized call center**
✅ **Financial transparency**
✅ **Clean, professional UI**
✅ **Scalable architecture**

**Status**: ✅ MVP Complete - Ready for backend integration

**Next Steps**:
1. Connect to real API
2. Add authentication
3. Implement WebSockets
4. Add charts
5. User testing with admin team

---

Built with focus on **efficiency**, **clarity**, and **control**.
