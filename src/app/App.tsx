import { lazy, Suspense, useState, useEffect } from 'react';
import { authService, apiClient } from '@zaska/shared-services';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoadingScreen } from './screens/LoadingScreen';
import { BottomNav } from './components/BottomNav';

// Eagerly loaded: needed before any interaction (auth guard, fallback)
import { SplashScreen } from './screens/SplashScreen';
import { LoginScreen } from './screens/LoginScreen';

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
const TaskHistoryScreen = lazy(() => import('./screens/TaskHistoryScreen').then(m => ({ default: m.TaskHistoryScreen })));
const SettingsScreen = lazy(() => import('./screens/SettingsScreen').then(m => ({ default: m.SettingsScreen })));
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

type Screen =
  | 'splash'
  | 'onboarding'
  | 'login'
  | 'register'
  | 'otp'
  | 'setPassword'
  | 'profileSetup'
  | 'demoNav'
  | 'home'
  | 'categories'
  | 'search'
  | 'notifications'
  | 'taskModeSelection'
  | 'postTask'
  | 'taskCreated'
  | 'fastMatching'
  | 'matching'
  | 'taskerList'
  | 'applicants'
  | 'taskDetail'
  | 'taskChat'
  | 'confirmCompletion'
  | 'completion'
  | 'paymentSuccess'
  | 'taskerMode'
  | 'taskerFastMode'
  | 'taskerApply'
  | 'tasksTab'
  | 'wallet'
  | 'sendMoney'
  | 'withdraw'
  | 'addFunds'
  | 'transactionHistory'
  | 'profile'
  | 'editProfile'
  | 'paymentMethods'
  | 'taskHistory'
  | 'settings'
  | 'support'
  | 'faq'
  | 'reportIssue'
  | 'loading'
  | 'skeletonLoading'
  | 'error'
  | 'noInternet'
  | 'paymentFailed'
  | 'taskCancelled'
  | 'noTaskersAvailable'
  | 'taskExpired'
  | 'priceNegotiation'
  | 'admin'
  | 'adminDashboard'
  | 'callCenter'
  | 'kyc'
  | 'forgotPassword'
  | 'resetPassword';

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('splash');
  const [activeTab, setActiveTab] = useState('home');
  const [taskMode, setTaskMode] = useState<'fast' | 'choose'>('fast');
  const [currentTaskId, setCurrentTaskId] = useState<string>('');
  const [registeredPhone, setRegisteredPhone] = useState<string>('');
  const [registeredEmail, setRegisteredEmail] = useState<string>('');
  const [resetEmail, setResetEmail] = useState<string>('');
  const [currentChatTaskerName, setCurrentChatTaskerName] = useState<string>('');
  const [currentNegotiation, setCurrentNegotiation] = useState<{
    taskerName: string; originalPrice: number; proposedPrice: number;
  }>({ taskerName: '', originalPrice: 0, proposedPrice: 0 });
  const publicScreens: Screen[] = ['splash', 'onboarding', 'login', 'register', 'otp', 'setPassword', 'profileSetup', 'forgotPassword', 'resetPassword', 'loading', 'error', 'noInternet'];

  useEffect(() => {
    if (activeTab === 'home') setCurrentScreen('home');
    else if (activeTab === 'explore') setCurrentScreen('taskerMode');
    else if (activeTab === 'tasks') setCurrentScreen('tasksTab');
    else if (activeTab === 'wallet') setCurrentScreen('wallet');
    else if (activeTab === 'profile') setCurrentScreen('profile');
  }, [activeTab]);

  useEffect(() => {
    if (!publicScreens.includes(currentScreen)) {
      if (!apiClient.getAccessToken()) {
        setCurrentScreen('login');
      }
    }
  }, [currentScreen]);

  useEffect(() => {
    const check = async () => {
      const token = apiClient.getAccessToken();
      if (!token) return;
      try {
        const payload = JSON.parse(atob(token.split('.')[1] ?? ''));
        if (typeof payload.exp !== 'number') return;
        const msUntilExp = payload.exp * 1000 - Date.now();
        if (msUntilExp < 120_000) {
          try {
            await authService.refresh();
          } catch {
            await authService.logout();
            setCurrentScreen('login');
          }
        }
      } catch {
        await authService.logout();
        setCurrentScreen('login');
      }
    };

    void check();
    const timer = setInterval(check, 60_000);
    return () => clearInterval(timer);
  }, []);

  const isAuthenticated = !!apiClient.getAccessToken();
  const showBottomNav = isAuthenticated && ['home', 'taskerMode', 'tasksTab', 'wallet', 'profile', 'categories', 'search', 'admin', 'callCenter'].includes(currentScreen);

  const renderScreen = () => {
    if (!publicScreens.includes(currentScreen) && !isAuthenticated) {
      return null;
    }
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
            onCodeSent={(email) => {
              setResetEmail(email);
              setCurrentScreen('resetPassword');
            }}
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
        return <DemoNavigationScreen onNavigate={(screen) => setCurrentScreen(screen as Screen)} />;

      case 'home':
        return (
          <HomeScreen
            onPostTask={() => setCurrentScreen('taskModeSelection')}
            onViewApplicants={(taskId) => {
              setCurrentTaskId(taskId);
              setCurrentScreen('applicants');
            }}
            onTaskDetail={(taskId) => {
              setCurrentTaskId(taskId);
              setCurrentScreen('taskDetail');
            }}
            onCategories={() => setCurrentScreen('categories')}
            onSearch={() => setCurrentScreen('search')}
            onNotifications={() => setCurrentScreen('notifications')}
          />
        );

      case 'categories':
        return (
          <CategoriesScreen
            onBack={() => setCurrentScreen('home')}
            onSelectCategory={() => setCurrentScreen('postTask')}
          />
        );

      case 'search':
        return (
          <SearchScreen
            onBack={() => setCurrentScreen('home')}
          />
        );

      case 'notifications':
        return (
          <NotificationsScreen
            onBack={() => setCurrentScreen('home')}
          />
        );

      case 'taskModeSelection':
        return (
          <TaskModeSelectionScreen
            onBack={() => setCurrentScreen('home')}
            onSelect={(mode) => {
              setTaskMode(mode);
              setCurrentScreen('postTask');
            }}
          />
        );

      case 'postTask':
        return (
          <PostTaskScreen
            taskMode={taskMode}
            onBack={() => setCurrentScreen('taskModeSelection')}
            onSubmit={(taskId) => {
              if (taskId) setCurrentTaskId(taskId);
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
            onBack={() => setCurrentScreen('home')}
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
            onBack={() => setCurrentScreen('home')}
            onComplete={() => setCurrentScreen('paymentSuccess')}
            onChat={(name) => { setCurrentChatTaskerName(name ?? ''); setCurrentScreen('taskChat'); }}
            onViewApplicants={() => setCurrentScreen('applicants')}
          />
        );

      case 'taskChat':
        return (
          <TaskChatScreen
            taskerName={currentChatTaskerName}
            taskId={currentTaskId}
            onBack={() => setCurrentScreen('taskDetail')}
          />
        );

      case 'confirmCompletion':
        return (
          <ConfirmCompletionScreen
            taskId={currentTaskId}
            onBack={() => setCurrentScreen('taskDetail')}
            onSuccess={() => setCurrentScreen('paymentSuccess')}
            onReportIssue={() => setCurrentScreen('reportIssue')}
          />
        );

      case 'paymentSuccess':
        return (
          <PaymentSuccessScreen
            onDone={() => setCurrentScreen('home')}
            onViewReceipt={() => setCurrentScreen('transactionHistory')}
          />
        );

      case 'completion':
        return <CompletionScreen onDone={() => setCurrentScreen('home')} />;

      case 'taskerMode':
        return (
          <TaskerModeScreen
            onApply={(taskId) => {
              setCurrentTaskId(taskId);
              setCurrentScreen('taskerApply');
            }}
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
            onTaskClick={(taskId) => {
              setCurrentTaskId(taskId);
              setCurrentScreen('taskDetail');
            }}
            onViewApplicants={(taskId) => {
              setCurrentTaskId(taskId);
              setCurrentScreen('applicants');
            }}
            onPostTask={() => setCurrentScreen('taskModeSelection')}
          />
        );

      case 'wallet':
        return (
          <WalletScreen
            onSendMoney={() => setCurrentScreen('sendMoney')}
            onWithdraw={() => setCurrentScreen('withdraw')}
            onAddFunds={() => setCurrentScreen('addFunds')}
            onTransactionHistory={() => setCurrentScreen('transactionHistory')}
          />
        );

      case 'sendMoney':
        return (
          <SendMoneyScreen
            onBack={() => setCurrentScreen('wallet')}
            onSuccess={() => setCurrentScreen('paymentSuccess')}
          />
        );

      case 'withdraw':
        return (
          <WithdrawScreen
            onBack={() => setCurrentScreen('wallet')}
            onSuccess={() => setCurrentScreen('paymentSuccess')}
          />
        );

      case 'addFunds':
        return (
          <AddFundsScreen
            onBack={() => setCurrentScreen('wallet')}
            onSuccess={() => setCurrentScreen('paymentSuccess')}
          />
        );

      case 'transactionHistory':
        return <TransactionHistoryScreen onBack={() => setCurrentScreen('wallet')} />;

      case 'profile':
        return (
          <ProfileScreen
            onEditProfile={() => setCurrentScreen('editProfile')}
            onKyc={() => setCurrentScreen('kyc')}
            onPaymentMethods={() => setCurrentScreen('paymentMethods')}
            onTaskHistory={() => setCurrentScreen('taskHistory')}
            onSettings={() => setCurrentScreen('settings')}
            onSupport={() => setCurrentScreen('support')}
            onLogout={() => {
              void authService.logout();
              setCurrentScreen('login');
            }}
          />
        );

      case 'kyc':
        return (
          <KycScreen
            onBack={() => setCurrentScreen('profile')}
            onComplete={() => setCurrentScreen('profile')}
          />
        );

      case 'editProfile':
        return (
          <EditProfileScreen
            onBack={() => setCurrentScreen('profile')}
            onSave={() => setCurrentScreen('profile')}
          />
        );

      case 'paymentMethods':
        return (
          <PaymentMethodsScreen
            onBack={() => setCurrentScreen('profile')}
            onAddPaymentMethod={() => setCurrentScreen('profile')}
          />
        );

      case 'taskHistory':
        return (
          <TaskHistoryScreen
            onBack={() => setCurrentScreen('profile')}
            onTaskDetails={(taskId) => {
              setCurrentTaskId(taskId);
              setCurrentScreen('taskDetail');
            }}
          />
        );

      case 'settings':
        return (
          <SettingsScreen
            onBack={() => setCurrentScreen('profile')}
            onSupport={() => setCurrentScreen('support')}
            onLogout={() => {
              void authService.logout();
              setCurrentScreen('login');
            }}
          />
        );

      case 'support':
        return (
          <SupportScreen
            onBack={() => setCurrentScreen('profile')}
            onFAQ={() => setCurrentScreen('faq')}
          />
        );

      case 'faq':
        return <FAQScreen onBack={() => setCurrentScreen('support')} />;

      case 'reportIssue':
        return (
          <ReportIssueScreen
            onBack={() => setCurrentScreen('taskDetail')}
            onSubmit={() => setCurrentScreen('home')}
          />
        );

      case 'loading':
        return <LoadingScreen />;

      case 'skeletonLoading':
        return <SkeletonLoadingScreen type="list" />;

      case 'error':
        return (
          <ErrorScreen
            onRetry={() => setCurrentScreen('home')}
            onBack={() => setCurrentScreen('home')}
          />
        );

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
        return <HomeScreen onPostTask={() => setCurrentScreen('taskModeSelection')} />;
    }
  };

  return (
    <ErrorBoundary>
      <div className="size-full bg-white flex flex-col max-w-md mx-auto relative">
        <div className="flex-1 overflow-hidden">
          <Suspense fallback={<LoadingScreen />}>
            {renderScreen()}
          </Suspense>
        </div>
        {showBottomNav && (
          <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
        )}
      </div>
    </ErrorBoundary>
  );
}
