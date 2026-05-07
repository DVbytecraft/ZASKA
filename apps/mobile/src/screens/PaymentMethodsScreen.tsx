import { useEffect, useState } from "react";
import { Alert, Pressable, Text, View } from "react-native";
import { paymentService, type PaymentMethod } from "@zaska/shared-services";

export function PaymentMethodsScreen() {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await paymentService.getPaymentMethods();
        setMethods(data);
      } catch (error) {
        console.error(error);
        Alert.alert("Erreur", "Impossible de charger les moyens de paiement.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  return (
    <View style={{ flex: 1, backgroundColor: "#F9FAFB", padding: 20 }}>
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 16 }}>Méthodes de paiement</Text>
      {loading ? <Text style={{ color: "#6B7280", marginBottom: 10 }}>Chargement...</Text> : null}
      {!loading && methods.length === 0 ? (
        <Text style={{ color: "#6B7280", marginBottom: 10 }}>Aucune méthode disponible.</Text>
      ) : null}
      {methods.map((method) => (
        <View key={method.id} style={{ backgroundColor: "#fff", borderRadius: 12, padding: 14, marginBottom: 10 }}>
          <Text style={{ fontWeight: "700", marginBottom: 4 }}>{method.type}</Text>
          <Text style={{ color: "#6B7280", marginBottom: 6 }}>{method.details}</Text>
          {method.isDefault ? <Text style={{ color: "#16A34A", fontSize: 12 }}>Par défaut</Text> : null}
        </View>
      ))}
      <Pressable style={{ backgroundColor: "#EDE9FE", borderRadius: 12, padding: 12 }}>
        <Text style={{ textAlign: "center", color: "#6D28D9", fontWeight: "700" }}>Ajouter une méthode</Text>
      </Pressable>
    </View>
  );
}
