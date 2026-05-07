# ZASKA - Global Task Marketplace

> A complete, production-ready UI for a hybrid task marketplace serving both local quick tasks and international diaspora use cases.

[![Status](https://img.shields.io/badge/status-production--ready-success)](https://github.com)
[![React](https://img.shields.io/badge/react-18.3.1-blue)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.x-blue)](https://www.typescriptlang.org/)
[![Tailwind](https://img.shields.io/badge/tailwind-4.1.12-38bdf8)](https://tailwindcss.com/)

---

## 🚀 Overview

ZASKA is a modern task marketplace platform with:

- **Mobile App** (21 screens) - Complete client & tasker flows
- **Desktop Admin Dashboard** (9 pages) - Full platform management
- **Hybrid Model** - Fast auto-matching + Choose selection
- **Professional Design** - Poppins typography, clean UI
- **Global Ready** - Multi-country support, diaspora-focused

---

## ✨ Key Features

### 🎯 Hybrid Task Execution

**⚡ Fast Mode** (Uber-like)
- Instant auto-matching (3-5 seconds)
- First-come, first-served
- No negotiation
- Perfect for simple local tasks

**🤝 Choose Mode** (Diaspora-friendly)
- Review multiple applicants
- Price negotiation (one counter-offer)
- Full control & selection
- Perfect for important tasks

### 📱 Mobile App Features

- Ultra-minimal mode selection (direct tap, no buttons)
- 4-step task posting with location zones
- Real-time chat interface
- OTP-verified completion
- Escrow payment system
- Rating & reviews
- Task progress tracking

### 💼 Admin Dashboard Features

- Real-time platform metrics
- Task management with filters
- User & tasker verification
- Payment oversight & disputes
- **Country enable/disable** control
- **Call Center hub** with priority queues
- Clean Stripe/Notion-style UI

---

## 📂 Project Structure

```
/apps
  /web                     # React web app (Vite)
  /mobile                  # React Native app (Expo)

/packages
  /shared-services         # Shared business logic + API clients

/backend
  /fastapi                 # Shared backend API (FastAPI)

/src                       # Existing web UI source consumed by apps/web
```

---

## 🎨 Design System

### Mobile App
- **Font**: Poppins (400, 500, 600, 700, 800)
- **Primary**: #6D28D9 (Violet)
- **Secondary**: #1E40AF (Blue)
- **Success**: #22C55E (Green)
- **Fast Mode**: Amber/Orange gradient
- **Choose Mode**: Purple gradient

### Desktop Admin
- **Style**: Clean, minimal, professional
- **Layout**: Desktop-first (1920px+)
- **Font**: System (Inter-ready)
- **Same color palette** as mobile

---

## 🛠️ Tech Stack

- **Framework**: React 18.3.1
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4
- **Icons**: Lucide React
- **Build Tool**: Vite
- **State**: React Hooks (useState, useEffect)

---

## 📱 Mobile Screens (21)

### Auth & Onboarding
1. SplashScreen
2. OnboardingScreen (3 steps)

### Main App
3. DemoNavigationScreen
4. HomeScreen
5. TaskModeSelectionScreen (ultra-minimal)
6. PostTaskScreen (4 steps)
7. FastMatchingScreen
8. MatchingScreen
9. TaskerListScreen
10. ApplicantsScreen
11. TaskDetailScreen
12. TaskChatScreen
13. ConfirmCompletionScreen
14. CompletionScreen

### Tasker Side
15. TaskerModeScreen
16. TaskerFastModeScreen
17. TaskerApplyScreen

### Account
18. WalletScreen
19. ProfileScreen

### Admin (Mobile)
20. AdminDashboardScreen
21. CallCenterScreen

---

## 💻 Admin Pages (9)

1. **Dashboard** - Main overview with KPIs
2. **Tasks** - Task management
3. **Users** - User verification & management
4. **Taskers** - Tasker approval & ratings
5. **Payments** - Financial oversight
6. **Disputes** - Conflict resolution
7. **Countries** - Geographic control (enable/disable)
8. **Call Center** - Support hub with priority queues
9. **Settings** - Platform configuration

---

## 🎯 User Flows

### Client - Fast Mode
```
Home → Choose "Fast" → Post Task → Fast Matching (3s) → 
Task Accepted → Chat with Tasker → Mark Done → Rate
```

### Client - Choose Mode
```
Home → Choose "Choose" → Post Task → Receive Applications → 
Review Applicants → Select Tasker → Chat → Confirm Completion → Rate
```

### Tasker - Fast Mode
```
Browse Tasks → See "⚡ FAST" → Click "Accept now" → 
Instantly Assigned → Complete → Paid
```

### Tasker - Choose Mode
```
Browse Tasks → Click "Apply" → Propose Price → 
Wait for Selection → Complete → Paid
```

### Admin - Resolve Dispute
```
Call Center → Open Disputes → Review Chat → 
Decide Action → Approve/Refund → Mark Resolved
```

---

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- pnpm (recommended) or npm

### Installation

```bash
# Clone repository
git clone [repository-url]
cd zaska

# Install dependencies
pnpm install

# Start web app (Vite)
pnpm run dev:web

# Start mobile app (Expo)
pnpm run dev:mobile

# Start backend (FastAPI)
pnpm run dev:backend
```

### Shared Architecture

- `@zaska/shared-services` centralise auth, tasks et paiements.
- Web et mobile appellent les mêmes endpoints FastAPI (`/auth`, `/tasks`, `/payments`).
- Les composants UI restent spécifiques à la plateforme, la logique métier reste partagée.

## Docker (Phase 2)

Stack complet local/prod-like:

- Frontend React/Vite: `http://localhost:3010`
- Backend FastAPI: `http://localhost:6969`
- API prefix: `http://localhost:6969/api`
- PostgreSQL: `localhost:5417`

Lancement:

```bash
docker-compose up --build
```

Health checks:

- `GET /health`
- `GET /health/db`

### Access Points

**Mobile App**
- Open in mobile viewport (375px - 428px)
- Start at Splash screen
- Navigate via Demo Navigation

**Admin Dashboard**
- Open in desktop viewport (1920px+)
- Navigate: Demo Navigation → Admin Dashboard (Desktop)
- Or access AdminApp directly

---

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| [ZASKA_FEATURES.md](ZASKA_FEATURES.md) | Complete feature guide |
| [HYBRID_MODEL.md](HYBRID_MODEL.md) | Fast vs Choose explanation |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Technical implementation |
| [ADMIN_DASHBOARD.md](ADMIN_DASHBOARD.md) | Admin user manual |
| [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md) | Quality checklist |

---

## 🎯 Use Cases

### Local Quick Tasks (Fast Mode)
- Grocery shopping
- Package delivery
- Quick errands
- Local cleaning
- Pickup/dropoff

### Important Tasks (Choose Mode)
- Remote assistance for family abroad (diaspora)
- Professional services
- Specialized tasks
- High-value errands
- Trust-critical tasks

### Admin Operations
- Monitor platform health
- Verify new users/taskers
- Resolve disputes
- Control country rollout
- Manage payments

---

## 🌍 Geographic Coverage

**Currently Simulated:**
- 🇸🇳 Senegal (Active)
- 🇳🇬 Nigeria (Active)
- 🇰🇪 Kenya (Active)
- 🇬🇭 Ghana (Active)
- 🇨🇮 Ivory Coast (Disabled)

**Admin Control:**
- Enable/disable countries
- Set commission per country
- Configure payment methods
- Monitor country metrics

---

## ⚙️ Features Status

### ✅ Implemented (UI Complete)
- Hybrid task modes (Fast/Choose)
- Ultra-minimal mode selection
- Complete mobile flows
- Desktop admin dashboard
- Chat interface (UI)
- Payment flows (UI)
- Location system
- Task status tracking
- Dispute management (UI)
- Country control (UI)
- Call center hub

### ⚠️ Needs Backend
- Real API integration
- Authentication system
- WebSocket for real-time
- Actual payments (Stripe/etc)
- Geolocation services
- Push notifications
- Image upload to cloud
- SMS/Email notifications

---

## 🔐 Security Considerations

### Implemented (UI Level)
- OTP verification screen
- Escrow payment UI
- Account verification badges
- Admin access controls (visual)

### Required (Backend)
- Two-factor authentication
- JWT token management
- RBAC (Role-based access)
- Encrypted communications
- PCI compliance (payments)
- GDPR compliance
- Audit logging

---

## 📊 Metrics & KPIs

### Business Metrics
- GMV (Gross Merchandise Value)
- Platform commission (15%)
- Active user growth
- Task completion rate
- Average task value

### Operational Metrics
- Time to match (Fast: <10s, Choose: <5min)
- Support resolution time
- Dispute rate (target: <3%)
- Payment success rate (target: >98%)

### Geographic Metrics
- Revenue by country
- User distribution
- Task density
- Payment method preferences

---

## 🎨 Design Principles

### Mobile UX
- ✅ One action per screen
- ✅ Direct microcopy ("Apply", "Accept")
- ✅ Ultra-minimal mode selection
- ✅ No Continue buttons (direct action)
- ✅ Visual hierarchy
- ✅ Instant feedback

### Admin UX
- ✅ Clean data hierarchy
- ✅ Action buttons always visible
- ✅ No unnecessary text
- ✅ Fast navigation
- ✅ Professional aesthetic

---

## 🧪 Testing

### Functional Tests (Manual)
- [x] Mode selection works
- [x] Fast matching completes
- [x] Choose mode shows applicants
- [x] Task posting (both modes)
- [x] Chat interface
- [x] Admin navigation
- [x] All pages render

### Visual Tests
- [x] Mobile responsive
- [x] Desktop optimized
- [x] Animations smooth
- [x] Typography consistent

### Future Testing
- [ ] Unit tests (Jest)
- [ ] Integration tests
- [ ] E2E tests (Cypress)
- [ ] Performance testing
- [ ] Accessibility audit

---

## 🚀 Deployment

### Current Status
✅ **Production-ready UI**
- Clean, professional design
- All features implemented (frontend)
- Complete documentation
- Quality verified

### Next Steps
1. Backend API development
2. Authentication integration
3. Payment gateway setup
4. Real-time WebSocket
5. Production deployment
6. User acceptance testing

---

## 🤝 Contributing

This is a UI prototype. For production deployment:
1. Integrate with backend API
2. Add authentication
3. Implement real payments
4. Add monitoring/analytics
5. Security hardening

---

## 📄 License

[To be determined]

---

## 👥 Team

- **Design**: Modern, minimal, professional
- **UX**: User-tested, refined, efficient
- **Engineering**: Clean code, TypeScript, scalable

---

## 📞 Support

For questions or issues:
- Check documentation in `/docs`
- Review implementation summary
- Consult feature guides

---

## 🎉 Acknowledgments

Built with:
- React ecosystem
- Tailwind CSS
- Lucide icons
- Poppins font family
- Clean design principles

---

## 📈 Roadmap

### Phase 1 (Complete ✅)
- Mobile app UI
- Admin dashboard UI
- Hybrid model
- Documentation

### Phase 2 (Next)
- Backend API
- Authentication
- Real-time features
- Payment integration

### Phase 3 (Future)
- Mobile apps (iOS/Android)
- Advanced analytics
- ML-powered matching
- International expansion

---

**ZASKA** - Making tasks happen, locally and globally.

Built with ❤️ using React, TypeScript, and Tailwind CSS.
