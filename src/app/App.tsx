import { lazy, Suspense, useState, useEffect, useRef, useCallback } from 'react';
import { authService, apiClient } from '@zaska/shared-services';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoadingScreen } from './screens/LoadingScreen';
import { BottomNav } from './components/BottomNav';
import { InstallPrompt } from './components/InstallPrompt';
import { DemoBanner } from './components/DemoBanner';
import { setAppLanguage } from '../i18n';

// Eagerly loaded: needed immediately (auth guard, call overlays)
import { SplashScreen } from './screens/SplashScreen';
import { LoginScreen } from './screens/LoginScreen';
import { CallScreen } from './screens/CallScreen';
import { IncomingCallScreen } from './screens/IncomingCallScreen';
import type { IncomingCallData } from './screens/IncomingCallScreen';

// Lazily loaded: deferred until navigation reaches these screens
const OnboardingScreen = lazy(() => import('./screens/OnboardingScreen').then(m => ({ default: m.OnboardingScreen })));
const RegisterScreen = lazy(() => import('./screens/RegisterScreen').then(m => ({ default: m.RegisterScreen })));
const OTPScreen = lazy(() => import('./screens/OTPScreen').then(m => ({ default: m.OTPScreen })));
const SetPasswordScreen = lazy(() => import('./screens/SetPasswordScreen').then(m => ({ default: m.SetPasswordScreen })));
const ProfileSetupScreen = lazy(() => import('./screens/ProfileSetupScreen').then(m => ({ default: m.ProfileSetupScreen })));
const DemoNavigationScreen = lazy(() => import('./screens/DemoNavigationScreen').then(m => ({ default: m.DemoNavigationScreen })));
const HomeScreen = lazy(() => import('./screens/HomeScreen').then(m => ({ default: m.HomeScreen })));
const CategoriesScreen = lazy(() => import('./screens/CategoriesScreen').then(m => ({ default: m.CategoriesScreen })));
const SearchScreen = lazy(() => import('./screens/SearchScreen').then(m => ({ default: m.SearchScreen })));
const NotificationsScreen = lazy(() => import('./screens/NotificationsScreen').then(m => ({ default: m.NotificationsScreen })));
const TaskModeSelectionScreen = lazy(() => import('./screens/TaskModeSelectionScreen').then(m => ({ default: m.TaskModeSelectionScreen })));
const PostTaskScreen = lazy(() => import('./screens/PostTaskScreen').then(m => ({ default: m.PostTaskScreen })));
const TaskCreatedScreen = lazy(() => import('./screens/TaskCreatedScreen').then(m => ({ default: m.TaskCreatedScreen })));
const FastMatchingScreen = lazy(() => import('./screens/FastMatchingScreen').then(m => ({ default: m.FastMatchingScreen })));
const MatchingScreen = lazy(() => import('./screens/MatchingScreen').then(m => ({ default: m.MatchingScreen })));
const TaskerListScreen = lazy(() => import('./screens/TaskerListScreen').then(m => ({ default: m.TaskerListScreen })));
const ApplicantsScreen = lazy(() => import('./screens/ApplicantsScreen').then(m => ({ default: m.ApplicantsScreen })));
const TaskDetailScreen = lazy(() => import('./screens/TaskDetailScreen').then(m => ({ default: m.TaskDetailScreen })));
const TaskChatScreen = lazy(() => import('./screens/TaskChatScreen').then(m => ({ default: m.TaskChatScreen })));
const ConfirmCompletionScreen = lazy(() => import('./screens/ConfirmCompletionScreen').then(m => ({ default: m.ConfirmCompletionScreen })));
const CompletionScreen = lazy(() => import('./screens/CompletionScreen').then(m => ({ default: m.CompletionScreen })));
const PaymentSuccessScreen = lazy(() => import('./screens/PaymentSuccessScreen').then(m => ({ default: m.PaymentSuccessScreen })));
const TaskerModeScreen = lazy(() => import('./screens/TaskerModeScreen').then(m => ({ default: m.TaskerModeScreen })));
const TaskerFastModeScreen = lazy(() => import('./screens/TaskerFastModeScreen').then(m => ({ default: m.TaskerFastModeScreen })));
const TaskerApplyScreen = lazy(() => import('./screens/TaskerApplyScreen').then(m => ({ default: m.TaskerApplyScreen })));
const TasksTabScreen = lazy(() => import('./screens/TasksTabScreen').then(m => ({ default: m.TasksTabScreen })));
const WalletScreen = lazy(() => import('./screens/WalletScreen').then(m => ({ default: m.WalletScreen })));
const SendMoneyScreen = lazy(() => import('./screens/SendMoneyScreen').then(m => ({ default: m.SendMoneyScreen })));
const WithdrawScreen = lazy(() => import('./screens/WithdrawScreen').then(m => ({ default: m.WithdrawScreen })));
const AddFundsScreen = lazy(() => import('./screens/AddFundsScreen').then(m => ({ default: m.AddFundsScreen })));
const TransactionHistoryScreen = lazy(() => import('./screens/TransactionHistoryScreen').then(m => ({ default: m.TransactionHistoryScreen })));
const ProfileScreen = lazy(() => import('./screens/ProfileScreen').then(m => ({ default: m.ProfileScreen })));
const KycScreen = lazy(() => import('./screens/KycScreen').then(m => ({ default: m.KycScreen })));
const EditProfileScreen = lazy(() => import('./screens/EditProfileScreen').then(m => ({ default: m.EditProfileScreen })));
const PaymentMethodsScreen = lazy(() => import('./screens/PaymentMethodsScreen').then(m => ({ default: m.PaymentMethodsScreen })));
const AddressesScreen = lazy(() => import('./screens/AddressesScreen').then(m => ({ default: m.AddressesScreen })));
const VirtualCardScreen = lazy(() => import('./screens/VirtualCardScreen').then(m => ({ default: m.VirtualCardScreen })));
const TaskHistoryScreen = lazy(() => import('./screens/TaskHistoryScreen').then(m => ({ default: m.TaskHistoryScreen })));
const SettingsScreen = lazy(() => import('./screens/SettingsScreen').then(m => ({ default: m.SettingsScreen })));
const SocialProtectionScreen = lazy(() => import('./screens/SocialProtectionScreen').then(m => ({ default: m.SocialProtectionScreen })));
const SupportScreen = lazy(() => import('./screens/SupportScreen').then(m => ({ default: m.SupportScreen })));
const FAQScreen = lazy(() => import('./screens/FAQScreen').then(m => ({ default: m.FAQScreen })));
const ReportIssueScreen = lazy(() => import('./screens/ReportIssueScreen').then(m => ({ default: m.ReportIssueScreen })));
const ErrorScreen = lazy(() => import('./screens/ErrorScreen').then(m => ({ default: m.ErrorScreen })));
const NoInternetScreen = lazy(() => import('./screens/NoInternetScreen').then(m => ({ default: m.NoInternetScreen })));
const PaymentFailedScreen = lazy(() => import('./screens/PaymentFailedScreen').then(m => ({ default: m.PaymentFailedScreen })));
const TaskCancelledScreen = lazy(() => import('./screens/TaskCancelledScreen').then(m => ({ default: m.TaskCancelledScreen })));
const NoTaskersAvailableScreen = lazy(() => import('./screens/NoTaskersAvailableScreen').then(m => ({ default: m.NoTaskersAvailableScreen })));
const TaskExpiredScreen = lazy(() => import('./screens/TaskExpiredScreen').then(m => ({ default: m.TaskExpiredScreen })));
const PriceNegotiationScreen = lazy(() => import('./screens/PriceNegotiationScreen').then(m => ({ default: m.PriceNegotiationScreen })));
const SkeletonLoadingScreen = lazy(() => import('./screens/SkeletonLoadingScreen').then(m => ({ default: m.SkeletonLoadingScreen })));
const AdminDashboardScreen = lazy(() => import('./screens/AdminDashboardScreen').then(m => ({ default: m.AdminDashboardScreen })));
const CallCenterScreen = lazy(() => import('./screens/CallCenterScreen').then(m => ({ default: m.CallCenterScreen })));
const AdminApp = lazy(() => import('../admin/AdminApp').then(m => ({ default: m.AdminApp })));
const ForgotPasswordScreen = lazy(() => import('./screens/ForgotPasswordScreen').then(m => ({ default: m.ForgotPasswordScreen })));
const ResetPasswordScreen = lazy(() => import('./screens/ResetPasswordScreen').then(m => ({ default: m.ResetPasswordScreen })));
const MessagesScreen = lazy(() => import('./screens/MessagesScreen').then(m => ({ default: m.MessagesScreen })));

type Screen =
  | 'splash' | 'onboarding' | 'login' | 'register' | 'otp' | 'setPassword'
  | 'profileSetup' | 'demoNav' | 'home' | 'categories' | 'search'
  | 'notifications' | 'taskModeSelection' | 'postTask' | 'taskCreated'
  | 'fastMatching' | 'matching' | 'taskerList' | 'applicants' | 'taskDetail'
  | 'taskChat' | 'confirmCompletion' | 'completion' | 'paymentSuccess'
  | 'taskerMode' | 'taskerFastMode' | 'taskerApply' | 'tasksTab' | 'messages'
  | 'wallet' | 'sendMoney' | 'withdraw' | 'addFunds' | 'transactionHistory'
  | 'profile' | 'editProfile' | 'paymentMethods' | 'addresses' | 'virtualCard'
  | 'taskHistory' | 'settings' | 'support' | 'faq' | 'reportIssue' | 'loading'
  | 'skeletonLoading' | 'error' | 'noInternet' | 'paymentFailed' | 'taskCancelled'
  | 'noTaskersAvailable' | 'taskExpired' | 'priceNegotiation' | 'admin'
  | 'adminDashboard' | 'callCenter' | 'kyc' | 'forgotPassword' | 'resetPassword'
  | 'socialProtection';

interface GlobalCall {
  callId: string;
  isCaller: boolean;
  mediaType: 'audio' | 'video';
  partnerName: string;
  partnerAvatar?: string | null;
}

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('splash');
  const [prevScreen, setPrevScreen] = useState<Screen>('home');
  const [activeTab, setActiveTab] = useState('home');
  const [taskMode, setTaskMode] = useState<'fast' | 'choose'>('fast');
  const [currentTaskId, setCurrentTaskId] = useState('');
  const [registeredPhone, setRegisteredPhone] = useState('');
  const [registeredEmail, setRegisteredEmail] = useState('');
  const [resetEmail, setResetEmail] = useState('');
  const [initialDescription, setInitialDescription] = useState('');
  const [postTaskBack, setPostTaskBack] = useState<Screen>('taskModeSelection');
  const [currentNegotiation, setCurrentNegotiation] = useState({
    taskerName: '', originalPrice: 0, proposedPrice: 0,
  });
  const [tasksDefaultTab, setTasksDefaultTab] = useState<'client' | 'missions' | 'messages'>('client');
  // Incremented on every tab switch to force fresh data in list screens
  const [screenKey, setScreenKey] = useState(0);

  // ── Demo session ──────────────────────────────────────────────────────────
  const [isDemoSession, setIsDemoSession] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  const exitDemoSession = useCallback(() => {
    apiClient.clearTokens();
    setIsDemoSession(false);
    setCurrentScreen('login');
  }, []);

  const handleDemoAccess = useCallback(async () => {
    setDemoLoading(true);
    try {
      const res = await apiClient.post<{
        accessToken: string;
        userId: string;
        country: string;
        currency: string;
      }>('/demo/session', {});
      apiClient.setTokens({ accessToken: res.accessToken });
      apiClient.setCountry(res.country, res.currency);
      apiClient.setUserId(res.userId);
      setIsDemoSession(true);
      setCurrentScreen('home');
    } catch {
      // silently leave the user on the login screen
    } finally {
      setDemoLoading(false);
    }
  }, []);

  // ── Global call state ──────────────────────────────────────────────────────
  const [incomingCall, setIncomingCall] = useState<IncomingCallData | null>(null);
  const [activeGlobalCall, setActiveGlobalCall] = useState<GlobalCall | null>(null);
  const callWsRef = useRef<WebSocket | null>(null);

  const publicScreens: Screen[] = [
    'splash', 'onboarding', 'login', 'register', 'otp', 'setPassword',
    'profileSetup', 'forgotPassword', 'resetPassword', 'loading', 'error', 'noInternet',
  ];

  const isAuthenticated = !!apiClient.getAccessToken();

  // ── Navigate to a screen, tracking previous for smart back ────────────────
  // Uses a ref so goTo is always stable without stale-closure issues.
  const currentScreenRef = useRef<Screen>('splash');
  useEffect(() => { currentScreenRef.current = currentScreen; }, [currentScreen]);

  const goTo = useCallback((screen: Screen) => {
    setPrevScreen(currentScreenRef.current);
    setCurrentScreen(screen);
  }, []);

  // ── Global call notification WebSocket ────────────────────────────────────
  useEffect(() => {
    const myId = apiClient.getUserId();
    if (!isAuthenticated || !myId) return;

    let closed = false;
    let ws: WebSocket | null = null;

    async function connect() {
      try {
        const res = await apiClient.post<{ ticket: string }>('/calls/user/ws-ticket', {});
        if (closed) return;

        const wsBase =
          (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_WS_URL ??
          'ws://localhost:6969';
        ws = new WebSocket(`${wsBase}/ws/users/${myId}/calls`);
        callWsRef.current = ws;

        ws.onopen = () => {
          ws!.send(JSON.stringify({ type: 'auth', ticket: res.ticket }));
        };

        ws.onmessage = ({ data }) => {
          try {
            const msg = JSON.parse(data as string) as {
              type: string;
              call_id: string;
              caller_name: string;
              caller_avatar?: string;
              media_type: 'audio' | 'video';
            };
            if (msg.type === 'incoming_call') {
              setIncomingCall({
                callId: msg.call_id,
                callerName: msg.caller_name,
                callerAvatar: msg.caller_avatar ?? null,
                mediaType: msg.media_type,
              });
            }
          } catch { /* ignore malformed frames */ }
        };

        ws.onerror = () => {};
        ws.onclose = () => {
          // Auto-reconnect after 5s if still authenticated
          if (!closed) {
            setTimeout(() => { if (!closed) void connect(); }, 5000);
          }
        };
      } catch {
        // ticket fetch failed — retry after 10s
        if (!closed) setTimeout(() => void connect(), 10_000);
      }
    }

    void connect();

    return () => {
      closed = true;
      ws?.close();
      callWsRef.current = null;
    };
  }, [isAuthenticated]); // re-connect when auth changes

  // ── Bottom nav tab switch ─────────────────────────────────────────────────
  useEffect(() => {
    if (activeTab === 'home') { setCurrentScreen('home'); setScreenKey((k) => k + 1); }
    else if (activeTab === 'explore') { setCurrentScreen('taskerMode'); setScreenKey((k) => k + 1); }
    else if (activeTab === 'tasks') { setTasksDefaultTab('client'); setCurrentScreen('tasksTab'); setScreenKey((k) => k + 1); }
    else if (activeTab === 'wallet') setCurrentScreen('wallet');
    else if (activeTab === 'profile') setCurrentScreen('profile');
  }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Auth guard ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!publicScreens.includes(currentScreen) && !apiClient.getAccessToken()) {
      setCurrentScreen('login');
    }
  }, [currentScreen]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Language sync ─────────────────────────────────────────────────────────
  useEffect(() => {
    setAppLanguage(apiClient.getCountryCode());
  }, []);

  // ── Token refresh watchdog ─────────────────────────────────────────────────
  useEffect(() => {
    const check = async () => {
      const token = apiClient.getAccessToken();
      if (!token) return;
      try {
        const payload = JSON.parse(atob(token.split('.')[1] ?? ''));
        if (typeof payload.exp !== 'number') return;
        if (payload.exp * 1000 - Date.now() < 120_000) {
          if (isDemoSession) {
            // Demo tokens don't refresh — expire cleanly
            exitDemoSession();
          } else {
            try { await authService.refresh(); }
            catch { await authService.logout(); setCurrentScreen('login'); }
          }
        }
      } catch {
        if (isDemoSession) {
          exitDemoSession();
        } else {
          await authService.logout();
          setCurrentScreen('login');
        }
      }
    };
    void check();
    const timer = setInterval(check, 60_000);
    return () => clearInterval(timer);
  }, [isDemoSession, exitDemoSession]);

  // ── Global incoming call handlers ─────────────────────────────────────────
  const handleGlobalAnswer = (callId: string, mediaType: 'audio' | 'video') => {
    if (!incomingCall) return;
    setActiveGlobalCall({
      callId,
      isCaller: false,
      mediaType,
      partnerName: incomingCall.callerName,
      partnerAvatar: incomingCall.callerAvatar,
    });
    setIncomingCall(null);
  };

  const handleGlobalDecline = () => {
    if (incomingCall) {
      apiClient.post(`/calls/${incomingCall.callId}/end`, {}).catch(() => {});
    }
    setIncomingCall(null);
  };

  const showBottomNav =
    isAuthenticated &&
    ['home', 'taskerMode', 'tasksTab', 'messages', 'wallet', 'profile',
      'categories', 'search', 'admin', 'callCenter', 'taskerApply', 'applicants',
    ].includes(currentScreen);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const openTaskDetail = (taskId: string) => {
    setCurrentTaskId(taskId);
    goTo('taskDetail');
  };

  const renderScreen = () => {
    if (!publicScreens.includes(currentScreen) && !isAuthenticated) return null;

    switch (currentScreen) {
      case 'splash':
        return <SplashScreen onComplete={() => setCurrentScreen('onboarding')} />;

      case 'onboarding':
        return <OnboardingScreen onComplete={() => setCurrentScreen('login')} />;

      case 'login':
        return (
          <LoginScreen
            onBack={() => setCurrentScreen('onboarding')}
            onLogin={() => setCurrentScreen('home')}
            onSignup={() => setCurrentScreen('register')}
            onForgotPassword={() => setCurrentScreen('forgotPassword')}
            onDemoAccess={handleDemoAccess}
            demoLoading={demoLoading}
          />
        );

      case 'register':
        return (
          <RegisterScreen
            onBack={() => setCurrentScreen('login')}
            onRegistered={(phone, email) => {
              setRegisteredPhone(phone);
              setRegisteredEmail(email ?? '');
              setCurrentScreen('otp');
            }}
          />
        );

      case 'otp':
        return (
          <OTPScreen
            phone={registeredPhone}
            email={registeredEmail || undefined}
            onBack={() => setCurrentScreen('register')}
            onVerify={() => setCurrentScreen('profileSetup')}
          />
        );

      case 'setPassword':
        return (
          <SetPasswordScreen
            email={registeredEmail}
            onBack={() => setCurrentScreen('otp')}
            onComplete={() => setCurrentScreen('profileSetup')}
          />
        );

      case 'forgotPassword':
        return (
          <ForgotPasswordScreen
            onBack={() => setCurrentScreen('login')}
            onCodeSent={(email) => { setResetEmail(email); setCurrentScreen('resetPassword'); }}
          />
        );

      case 'resetPassword':
        return (
          <ResetPasswordScreen
            email={resetEmail}
            onBack={() => setCurrentScreen('forgotPassword')}
            onSuccess={() => setCurrentScreen('login')}
          />
        );

      case 'profileSetup':
        return (
          <ProfileSetupScreen
            onBack={() => setCurrentScreen('setPassword')}
            onContinue={() => setCurrentScreen('home')}
          />
        );

      case 'demoNav':
        return <DemoNavigationScreen onNavigate={(s) => setCurrentScreen(s as Screen)} />;

      case 'home':
        return (
          <HomeScreen
            key={screenKey}
            onPostTask={() => setCurrentScreen('taskModeSelection')}
            onViewApplicants={(taskId) => { setCurrentTaskId(taskId); goTo('applicants'); }}
            onTaskDetail={openTaskDetail}
            onCategories={() => setCurrentScreen('categories')}
            onSelectCategory={(_, description) => {
              setInitialDescription(description);
              setTaskMode('fast');
              setPostTaskBack('home');
              setCurrentScreen('postTask');
            }}
            onSearch={() => setCurrentScreen('search')}
            onNotifications={() => setCurrentScreen('notifications')}
          />
        );

      case 'categories':
        return (
          <CategoriesScreen
            onBack={() => setCurrentScreen('home')}
            onSelectCategory={(_, description) => {
              setInitialDescription(description);
              setTaskMode('fast');
              setPostTaskBack('home');
              setCurrentScreen('postTask');
            }}
          />
        );

      case 'search':
        return <SearchScreen onBack={() => setCurrentScreen('home')} />;

      case 'notifications':
        return (
          <NotificationsScreen
            onBack={() => setCurrentScreen('home')}
            onTaskDetail={openTaskDetail}
            onTaskChat={(taskId) => { setCurrentTaskId(taskId); goTo('taskChat'); }}
            onViewApplicants={(taskId) => { setCurrentTaskId(taskId); goTo('applicants'); }}
          />
        );

      case 'taskModeSelection':
        return (
          <TaskModeSelectionScreen
            onBack={() => setCurrentScreen('home')}
            onSelect={(mode) => {
              setTaskMode(mode);
              setInitialDescription('');
              setPostTaskBack('taskModeSelection');
              setCurrentScreen('postTask');
            }}
          />
        );

      case 'postTask':
        return (
          <PostTaskScreen
            taskMode={taskMode}
            initialDescription={initialDescription}
            onBack={() => setCurrentScreen(postTaskBack)}
            onSubmit={(taskId) => {
              if (taskId) setCurrentTaskId(taskId);
              setInitialDescription('');
              setCurrentScreen('taskCreated');
            }}
          />
        );

      case 'taskCreated':
        return (
          <TaskCreatedScreen
            taskMode={taskMode}
            onViewTask={() => setCurrentScreen(taskMode === 'fast' ? 'fastMatching' : 'matching')}
            onBackHome={() => setCurrentScreen('home')}
          />
        );

      case 'fastMatching':
        return <FastMatchingScreen onMatched={() => setCurrentScreen('taskDetail')} />;

      case 'matching':
        return <MatchingScreen onComplete={() => setCurrentScreen('taskerList')} />;

      case 'taskerList':
        return (
          <TaskerListScreen
            onBack={() => setCurrentScreen('home')}
            onSelect={() => setCurrentScreen('taskDetail')}
          />
        );

      case 'applicants':
        return (
          <ApplicantsScreen
            taskId={currentTaskId}
            onBack={() => setCurrentScreen(prevScreen)}
            onSelectTasker={() => setCurrentScreen('taskDetail')}
            onNegotiate={(taskerName, originalPrice, proposedPrice) => {
              setCurrentNegotiation({ taskerName, originalPrice, proposedPrice });
              setCurrentScreen('priceNegotiation');
            }}
          />
        );

      case 'taskDetail':
        return (
          <TaskDetailScreen
            taskId={currentTaskId}
            onBack={() => {
              // Return to the screen that opened this task detail
              const back = ['tasksTab', 'home', 'messages', 'notifications', 'taskHistory']
                .includes(prevScreen) ? prevScreen : 'home';
              setCurrentScreen(back);
              setScreenKey((k) => k + 1); // force refresh of list
            }}
            onComplete={() => setCurrentScreen('paymentSuccess')}
            onChat={() => { goTo('taskChat'); }}
            onViewApplicants={() => { goTo('applicants'); }}
          />
        );

      case 'taskChat':
        return (
          <TaskChatScreen
            taskId={currentTaskId}
            onBack={() => {
              const back = ['messages', 'tasksTab', 'taskDetail'].includes(prevScreen)
                ? prevScreen
                : 'taskDetail';
              setCurrentScreen(back);
            }}
          />
        );

      case 'confirmCompletion':
        return (
          <ConfirmCompletionScreen
            taskId={currentTaskId}
            onBack={() => setCurrentScreen('taskDetail')}
            onSuccess={() => { setCurrentScreen('paymentSuccess'); setScreenKey((k) => k + 1); }}
            onReportIssue={() => setCurrentScreen('reportIssue')}
          />
        );

      case 'paymentSuccess':
        return (
          <PaymentSuccessScreen
            onDone={() => { setCurrentScreen('home'); setScreenKey((k) => k + 1); }}
            onViewReceipt={() => setCurrentScreen('transactionHistory')}
          />
        );

      case 'completion':
        return <CompletionScreen taskId={currentTaskId || undefined} onDone={() => setCurrentScreen('home')} />;

      case 'taskerMode':
        return (
          <TaskerModeScreen
            onApply={(taskId) => { setCurrentTaskId(taskId); setCurrentScreen('taskerApply'); }}
            onBack={() => setCurrentScreen('home')}
          />
        );

      case 'taskerFastMode':
        return <TaskerFastModeScreen onAccept={() => setCurrentScreen('taskDetail')} />;

      case 'taskerApply':
        return (
          <TaskerApplyScreen
            taskId={currentTaskId}
            onBack={() => setCurrentScreen('taskerMode')}
            onSubmit={() => setCurrentScreen('taskerMode')}
          />
        );

      case 'tasksTab':
        return (
          <TasksTabScreen
            key={screenKey}
            defaultTab={tasksDefaultTab}
            onTaskClick={openTaskDetail}
            onViewApplicants={(taskId) => { setCurrentTaskId(taskId); goTo('applicants'); }}
            onPostTask={() => setCurrentScreen('taskModeSelection')}
            onChatOpen={(taskId) => { setCurrentTaskId(taskId); goTo('taskChat'); }}
            onExplore={() => setCurrentScreen('taskerMode')}
          />
        );

      case 'messages':
        return (
          <MessagesScreen
            key={screenKey}
            onOpenChat={(taskId) => { setCurrentTaskId(taskId); goTo('taskChat'); }}
            onPostTask={() => setCurrentScreen('taskModeSelection')}
          />
        );

      case 'wallet':
        return (
          <WalletScreen
            currency={apiClient.getCurrency() ?? 'XOF'}
            onSendMoney={() => setCurrentScreen('sendMoney')}
            onWithdraw={() => setCurrentScreen('withdraw')}
            onAddFunds={() => setCurrentScreen('addFunds')}
            onTransactionHistory={() => setCurrentScreen('transactionHistory')}
          />
        );

      case 'sendMoney':
        return <SendMoneyScreen onBack={() => setCurrentScreen('wallet')} onSuccess={() => setCurrentScreen('paymentSuccess')} />;

      case 'withdraw':
        return <WithdrawScreen onBack={() => setCurrentScreen('wallet')} onSuccess={() => setCurrentScreen('paymentSuccess')} />;

      case 'addFunds':
        return <AddFundsScreen onBack={() => setCurrentScreen('wallet')} onSuccess={() => setCurrentScreen('paymentSuccess')} />;

      case 'transactionHistory':
        return <TransactionHistoryScreen onBack={() => setCurrentScreen('wallet')} />;

      case 'profile':
        return (
          <ProfileScreen
            onEditProfile={() => setCurrentScreen('editProfile')}
            onKyc={() => setCurrentScreen('kyc')}
            onPaymentMethods={() => setCurrentScreen('paymentMethods')}
            onAddresses={() => setCurrentScreen('addresses')}
            onTaskHistory={() => setCurrentScreen('taskHistory')}
            onSettings={() => setCurrentScreen('settings')}
            onSupport={() => setCurrentScreen('support')}
            onLogout={() => { void authService.logout(); setCurrentScreen('login'); }}
            onAdmin={() => setCurrentScreen('adminDashboard')}
          />
        );

      case 'kyc':
        return <KycScreen onBack={() => setCurrentScreen('profile')} onComplete={() => setCurrentScreen('profile')} />;

      case 'editProfile':
        return <EditProfileScreen onBack={() => setCurrentScreen('profile')} onSave={() => setCurrentScreen('profile')} />;

      case 'paymentMethods':
        return <PaymentMethodsScreen onBack={() => setCurrentScreen('profile')} onVirtualCards={() => setCurrentScreen('virtualCard')} />;

      case 'addresses':
        return <AddressesScreen onBack={() => setCurrentScreen('profile')} />;

      case 'virtualCard':
        return <VirtualCardScreen onBack={() => setCurrentScreen('paymentMethods')} />;

      case 'taskHistory':
        return (
          <TaskHistoryScreen
            onBack={() => setCurrentScreen('profile')}
            onTaskDetails={(taskId) => { setCurrentTaskId(taskId); goTo('taskDetail'); }}
          />
        );

      case 'settings':
        return (
          <SettingsScreen
            onBack={() => setCurrentScreen('profile')}
            onSupport={() => setCurrentScreen('support')}
            onLogout={() => { void authService.logout(); setCurrentScreen('login'); }}
            onSocialProtection={() => setCurrentScreen('socialProtection')}
          />
        );

      case 'socialProtection':
        return <SocialProtectionScreen onBack={() => setCurrentScreen('settings')} />;

      case 'support':
        return <SupportScreen onBack={() => setCurrentScreen('profile')} onFAQ={() => setCurrentScreen('faq')} />;

      case 'faq':
        return <FAQScreen onBack={() => setCurrentScreen('support')} />;

      case 'reportIssue':
        return (
          <ReportIssueScreen
            taskId={currentTaskId || undefined}
            onBack={() => setCurrentScreen(prevScreen)}
            onSubmit={() => setCurrentScreen(prevScreen)}
          />
        );

      case 'loading':
        return <LoadingScreen />;

      case 'skeletonLoading':
        return <SkeletonLoadingScreen type="list" />;

      case 'error':
        return <ErrorScreen onRetry={() => setCurrentScreen('home')} onBack={() => setCurrentScreen('home')} />;

      case 'noInternet':
        return <NoInternetScreen onRetry={() => setCurrentScreen('home')} />;

      case 'paymentFailed':
        return (
          <PaymentFailedScreen
            onRetry={() => setCurrentScreen('postTask')}
            onChangePaymentMethod={() => setCurrentScreen('postTask')}
            onCancel={() => setCurrentScreen('home')}
          />
        );

      case 'taskCancelled':
        return (
          <TaskCancelledScreen
            cancelledBy="tasker"
            refundAmount="$35"
            onDone={() => setCurrentScreen('home')}
            onReportIssue={() => setCurrentScreen('reportIssue')}
          />
        );

      case 'noTaskersAvailable':
        return (
          <NoTaskersAvailableScreen
            onTryAgain={() => setCurrentScreen('fastMatching')}
            onExpandSearch={() => setCurrentScreen('postTask')}
            onBackHome={() => setCurrentScreen('home')}
          />
        );

      case 'taskExpired':
        return (
          <TaskExpiredScreen
            onRepost={() => setCurrentScreen('taskModeSelection')}
            onBackHome={() => setCurrentScreen('home')}
          />
        );

      case 'priceNegotiation':
        return (
          <PriceNegotiationScreen
            taskerName={currentNegotiation.taskerName}
            originalPrice={currentNegotiation.originalPrice}
            proposedPrice={currentNegotiation.proposedPrice}
            onBack={() => setCurrentScreen('applicants')}
            onAccept={() => setCurrentScreen('taskDetail')}
            onCounter={() => setCurrentScreen('applicants')}
            onDecline={() => setCurrentScreen('applicants')}
          />
        );

      case 'admin':
        return <AdminDashboardScreen />;

      case 'adminDashboard':
        return <AdminApp />;

      case 'callCenter':
        return <CallCenterScreen />;

      default:
        return <HomeScreen key={screenKey} onPostTask={() => setCurrentScreen('taskModeSelection')} />;
    }
  };

  return (
    <ErrorBoundary>
      <div className="size-full bg-white flex flex-col max-w-md mx-auto relative">
        {/* ── Global incoming call overlay (visible on ANY screen) ──────────── */}
        {incomingCall && !activeGlobalCall && (
          <div className="absolute inset-0 z-50">
            <IncomingCallScreen
              call={incomingCall}
              onAnswer={handleGlobalAnswer}
              onDecline={handleGlobalDecline}
            />
          </div>
        )}

        {/* ── Global active call (callee side) ──────────────────────────────── */}
        {activeGlobalCall && (
          <div className="absolute inset-0 z-50">
            <CallScreen
              callId={activeGlobalCall.callId}
              isCaller={false}
              mediaType={activeGlobalCall.mediaType}
              partnerName={activeGlobalCall.partnerName}
              partnerAvatar={activeGlobalCall.partnerAvatar}
              onEnd={() => setActiveGlobalCall(null)}
            />
          </div>
        )}

        {/* ── Demo mode banner (shown when isDemoSession is active) ─────────── */}
        {isDemoSession && isAuthenticated && (
          <DemoBanner onExit={exitDemoSession} />
        )}

        {/* ── Main screen content ───────────────────────────────────────────── */}
        <div className="flex-1 overflow-hidden">
          <Suspense fallback={<LoadingScreen />}>
            {renderScreen()}
          </Suspense>
        </div>

        {showBottomNav && (
          <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
        )}
        <InstallPrompt />
      </div>
    </ErrorBoundary>
  );
}
