# Developer Handoff Guide - ZASKA Mobile App

## Quick Start

This is a **production-ready prototype** with complete flows, edge cases, and backend integration points mapped out.

---

## Project Structure

```
/src
  /app
    /screens         # 50+ complete screens
    /components      # Reusable UI components
    App.tsx          # Main router with all navigation
  /admin             # Admin dashboard (separate)
  /styles
    fonts.css        # Poppins font
    theme.css        # Design system tokens
```

---

## Run the App

```bash
# Install dependencies
pnpm install

# Start dev server
pnpm dev

# The app auto-starts at the Vite dev server URL
```

**Note:** Do NOT run `vite build` or modify `__figma__entrypoint__.ts` - this is a Figma Make project with custom build process.

---

## Navigation System

### How it Works
- Screen-based routing via `useState<Screen>`
- Bottom tabs control main navigation
- All screens have back buttons
- No React Router needed (everything is in App.tsx)

### Adding a New Screen

1. Create screen component in `/src/app/screens/`
2. Add screen type to `Screen` union in `App.tsx`
3. Import screen in `App.tsx`
4. Add case to `renderScreen()` switch
5. Wire navigation callbacks

Example:
```typescript
// 1. Create NewScreen.tsx
export function NewScreen({ onBack }: { onBack: () => void }) {
  return <div>...</div>
}

// 2. Add to App.tsx
type Screen = ... | 'newScreen';

// 3. Import
import { NewScreen } from './screens/NewScreen';

// 4. Add case
case 'newScreen':
  return <NewScreen onBack={() => setCurrentScreen('home')} />;
```

---

## Key Components Reference

### TaskStatusBadge
```tsx
import { TaskStatusBadge } from '../components/TaskStatusBadge';

<TaskStatusBadge 
  status="in_progress"  // posted | accepted | in_progress | completed | cancelled | expired | fast_matching | awaiting_payment
  size="md"             // sm | md | lg
/>
```

### EscrowBadge
```tsx
import { EscrowBadge } from '../components/EscrowBadge';

<EscrowBadge 
  amount="$35" 
  status="held"  // held | released
/>
```

### Button
```tsx
import { Button } from '../components/Button';

<Button 
  variant="primary"   // primary | secondary | outline
  size="md"          // sm | md | lg
  fullWidth={true}
  onClick={handleClick}
>
  Click me
</Button>
```

### Avatar
```tsx
import { Avatar } from '../components/Avatar';

<Avatar 
  name="John Doe"
  size="md"  // sm | md | lg | xl
/>
```

---

## Backend Integration Points

### API Client Setup

Create `/src/lib/api.ts`:

```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL;

export const api = {
  // Auth
  async login(phone: string) {
    return fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      body: JSON.stringify({ phone })
    });
  },
  
  // Tasks
  async getTasks() {
    return fetch(`${API_BASE}/tasks`);
  },
  
  async createTask(data: TaskData) {
    return fetch(`${API_BASE}/tasks`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  
  // Payments
  async holdEscrow(taskId: string, amount: number) {
    return fetch(`${API_BASE}/payments/escrow`, {
      method: 'POST',
      body: JSON.stringify({ taskId, amount })
    });
  },
  
  async releaseEscrow(taskId: string) {
    return fetch(`${API_BASE}/payments/release`, {
      method: 'POST',
      body: JSON.stringify({ taskId })
    });
  }
};
```

### Environment Variables

Create `.env`:
```
VITE_API_BASE_URL=https://api.zaska.com
VITE_STRIPE_KEY=pk_test_...
VITE_SOCKET_URL=wss://socket.zaska.com
```

---

## State Management

Currently using local `useState`. For production, consider:

### Option 1: Context API
```typescript
// src/contexts/AuthContext.tsx
export const AuthContext = createContext();

// src/contexts/TaskContext.tsx
export const TaskContext = createContext();
```

### Option 2: Zustand (Recommended)
```typescript
// src/store/useAuthStore.ts
import create from 'zustand';

export const useAuthStore = create((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  logout: () => set({ user: null })
}));

// Usage in components
const user = useAuthStore(state => state.user);
```

---

## Real-Time Features

### WebSocket Setup

```typescript
// src/lib/socket.ts
import io from 'socket.io-client';

export const socket = io(import.meta.env.VITE_SOCKET_URL, {
  auth: {
    token: localStorage.getItem('auth_token')
  }
});

// Listen for messages
socket.on('new_message', (message) => {
  // Update chat UI
});

// Send message
socket.emit('send_message', { taskId, text });
```

---

## Payment Integration

### Escrow Flow Implementation

```typescript
// When task is accepted
async function handleTaskAccepted(taskId: string, amount: number) {
  // 1. Hold payment in escrow
  await api.holdEscrow(taskId, amount);
  
  // 2. Update UI to show "held" status
  setPaymentStatus('held');
  
  // 3. Show EscrowBadge with "held" status
}

// When user confirms completion
async function handleConfirmCompletion(taskId: string) {
  // 1. Release escrow
  await api.releaseEscrow(taskId);
  
  // 2. Update UI to show "released" status
  setPaymentStatus('released');
  
  // 3. Navigate to PaymentSuccessScreen
}
```

### Stripe Integration Example

```typescript
// src/lib/stripe.ts
import { loadStripe } from '@stripe/stripe-js';

const stripe = await loadStripe(import.meta.env.VITE_STRIPE_KEY);

export async function processPayment(amount: number, method: string) {
  const { clientSecret } = await api.createPaymentIntent(amount);
  
  const { error } = await stripe.confirmCardPayment(clientSecret);
  
  if (error) {
    // Navigate to PaymentFailedScreen
    setCurrentScreen('paymentFailed');
  } else {
    // Navigate to PaymentSuccessScreen
    setCurrentScreen('paymentSuccess');
  }
}
```

---

## Push Notifications

### Setup

```typescript
// src/lib/notifications.ts
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

export async function requestNotificationPermission() {
  const permission = await Notification.requestPermission();
  
  if (permission === 'granted') {
    const token = await getToken(messaging);
    // Send token to backend
    await api.saveNotificationToken(token);
  }
}

// Handle foreground notifications
onMessage(messaging, (payload) => {
  // Show in-app notification
  showNotification(payload);
});
```

---

## Image Upload

### File Upload Component

```typescript
// src/components/ImageUpload.tsx
export function ImageUpload({ onUpload }: { onUpload: (url: string) => void }) {
  const handleFile = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.uploadImage(formData);
    onUpload(response.url);
  };
  
  return (
    <input 
      type="file" 
      accept="image/*" 
      onChange={(e) => handleFile(e.target.files[0])}
    />
  );
}
```

---

## Testing

### Unit Tests

```typescript
// Example: Button.test.tsx
import { render, fireEvent } from '@testing-library/react';
import { Button } from './Button';

test('button calls onClick when clicked', () => {
  const handleClick = jest.fn();
  const { getByText } = render(<Button onClick={handleClick}>Click</Button>);
  
  fireEvent.click(getByText('Click'));
  expect(handleClick).toHaveBeenCalled();
});
```

### E2E Tests (Playwright)

```typescript
// tests/user-flow.spec.ts
test('user can post task and complete payment', async ({ page }) => {
  await page.goto('/');
  
  // Login
  await page.fill('input[type="tel"]', '+221771234567');
  await page.click('button:has-text("Continue")');
  
  // Post task
  await page.click('button:has-text("Post a task")');
  await page.click('button:has-text("Fast")');
  // ... continue flow
});
```

---

## Performance Optimization

### Code Splitting

```typescript
// App.tsx
import { lazy, Suspense } from 'react';

const TaskDetailScreen = lazy(() => import('./screens/TaskDetailScreen'));

// In render
<Suspense fallback={<SkeletonLoadingScreen type="detail" />}>
  <TaskDetailScreen />
</Suspense>
```

### Memoization

```typescript
import { memo, useMemo, useCallback } from 'react';

// Memoize expensive components
export const TaskList = memo(function TaskList({ tasks }) {
  return tasks.map(task => <TaskCard key={task.id} task={task} />);
});

// Memoize callbacks
const handleClick = useCallback(() => {
  setCurrentScreen('taskDetail');
}, []);
```

---

## Security Checklist

- [ ] Environment variables for all secrets
- [ ] Input validation on all forms
- [ ] XSS protection (React default)
- [ ] HTTPS only in production
- [ ] JWT token storage (httpOnly cookies)
- [ ] Rate limiting on API
- [ ] Escrow verification on backend
- [ ] Phone number verification
- [ ] Payment method validation

---

## Deployment

### Build for Production

```bash
# This is a Figma Make project
# Build process is handled by Figma
# Export static assets if needed
```

### Mobile App (React Native)

This prototype can be converted to React Native:

1. Replace `div` with `View`
2. Replace `button` with `TouchableOpacity`
3. Use `react-native-vector-icons` for icons
4. Adjust styling for native platform

---

## Common Patterns

### Loading States
```typescript
const [loading, setLoading] = useState(false);

if (loading) {
  return <SkeletonLoadingScreen type="list" />;
}
```

### Error Handling
```typescript
try {
  await api.createTask(data);
} catch (error) {
  setCurrentScreen('error');
}
```

### Empty States
```typescript
if (tasks.length === 0) {
  return (
    <EmptyStateScreen
      title="No tasks yet"
      message="Post your first task to get started"
      actionLabel="Post a task"
      onAction={() => setCurrentScreen('taskModeSelection')}
    />
  );
}
```

---

## Troubleshooting

### Screen not rendering?
- Check if screen type is in `Screen` union
- Verify import statement
- Ensure case is added to switch statement

### Navigation not working?
- Check callback props are wired correctly
- Verify `setCurrentScreen` is called with valid screen name

### Bottom nav not showing?
- Add screen name to `showBottomNav` array
- Check if screen is a top-level tab screen

---

## Next Steps

1. **Connect Backend API** → Replace mock data with real API calls
2. **Add Authentication** → Implement JWT token management
3. **Setup WebSocket** → Real-time chat and notifications
4. **Integrate Payments** → Stripe/payment gateway
5. **Add Analytics** → Track user behavior
6. **Setup Error Tracking** → Sentry or similar
7. **Write Tests** → Unit + E2E coverage
8. **Deploy** → Mobile app stores

---

## Support

For questions about the design system or navigation:
- See `PRODUCTION_READY.md` for complete flow documentation
- Check component files for prop definitions
- Review `App.tsx` for navigation examples

**Status: Ready for backend integration** 🚀
