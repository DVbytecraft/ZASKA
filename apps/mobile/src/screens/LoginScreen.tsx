import { useState } from "react";
import { Alert, Pressable, Text, TextInput, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { authService } from "@zaska/shared-services";

export function LoginScreen() {
  const navigation = useNavigation<any>();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    try {
      await authService.login({ email, password });
      navigation.navigate("PostTask");
    } catch (error) {
      console.error(error);
      Alert.alert("Erreur", "Connexion impossible.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, justifyContent: "center", padding: 20, backgroundColor: "#fff" }}>
      <Text style={{ fontSize: 32, fontWeight: "800", color: "#6D28D9", marginBottom: 24 }}>ZASKA</Text>
      <Text style={{ marginBottom: 8, color: "#111827" }}>Adresse e-mail</Text>
      <TextInput
        value={email}
        onChangeText={setEmail}
        placeholder="exemple@email.com"
        keyboardType="email-address"
        autoCapitalize="none"
        style={{
          borderWidth: 1,
          borderColor: "#D1D5DB",
          borderRadius: 12,
          padding: 14,
          marginBottom: 12,
        }}
      />
      <TextInput
        value={password}
        onChangeText={setPassword}
        placeholder="Mot de passe"
        secureTextEntry
        style={{
          borderWidth: 1,
          borderColor: "#D1D5DB",
          borderRadius: 12,
          padding: 14,
          marginBottom: 12,
        }}
      />
      <Pressable
        onPress={handleLogin}
        disabled={!email || !password || loading}
        style={{
          backgroundColor: "#6D28D9",
          borderRadius: 12,
          padding: 14,
          opacity: !email || !password || loading ? 0.6 : 1,
        }}
      >
        <Text style={{ color: "#fff", textAlign: "center", fontWeight: "700" }}>
          {loading ? "Connexion..." : "Continuer"}
        </Text>
      </Pressable>
    </View>
  );
}
