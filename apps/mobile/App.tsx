import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { LoginScreen } from "./src/screens/LoginScreen";
import { PostTaskScreen } from "./src/screens/PostTaskScreen";
import { PaymentMethodsScreen } from "./src/screens/PaymentMethodsScreen";

export type RootStackParamList = {
  Login: undefined;
  PostTask: undefined;
  Payments: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        <Stack.Screen name="Login" component={LoginScreen} />
        <Stack.Screen name="PostTask" component={PostTaskScreen} />
        <Stack.Screen name="Payments" component={PaymentMethodsScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
