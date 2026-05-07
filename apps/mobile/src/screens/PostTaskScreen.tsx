import { useState } from "react";
import { Alert, Pressable, Text, TextInput, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { taskService } from "@zaska/shared-services";

export function PostTaskScreen() {
  const navigation = useNavigation<any>();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [loading, setLoading] = useState(false);

  const lat = parseFloat(latitude);
  const lon = parseFloat(longitude);
  const isValid =
    title.trim().length >= 3 &&
    description.trim().length >= 3 &&
    Number(price) > 0 &&
    !isNaN(lat) && lat >= -90 && lat <= 90 &&
    !isNaN(lon) && lon >= -180 && lon <= 180;

  const handleCreateTask = async () => {
    if (!isValid) {
      Alert.alert("Champs invalides", "Titre (3 car. min), description, prix et coordonnées GPS requis.");
      return;
    }
    setLoading(true);
    try {
      await taskService.createTask({
        title: title.trim(),
        description: description.trim(),
        price: Number(price),
        currency,
        latitude: lat,
        longitude: lon,
        status: "OPEN",
      });
      navigation.navigate("Payments");
    } catch (error) {
      console.error(error);
      Alert.alert("Erreur", "Impossible de créer la tâche.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, padding: 20, backgroundColor: "#fff" }}>
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 16 }}>Poster une tâche</Text>

      <Text style={{ fontSize: 13, color: "#374151", marginBottom: 4 }}>Titre *</Text>
      <TextInput
        placeholder="Ex: Livraison de colis"
        value={title}
        onChangeText={setTitle}
        style={{ borderWidth: 1, borderColor: "#D1D5DB", borderRadius: 12, padding: 12, marginBottom: 12 }}
      />

      <Text style={{ fontSize: 13, color: "#374151", marginBottom: 4 }}>Description *</Text>
      <TextInput
        placeholder="Décrivez votre tâche..."
        value={description}
        onChangeText={setDescription}
        multiline
        style={{ borderWidth: 1, borderColor: "#D1D5DB", borderRadius: 12, padding: 12, marginBottom: 12, minHeight: 100 }}
      />

      <View style={{ flexDirection: "row", gap: 10, marginBottom: 12 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13, color: "#374151", marginBottom: 4 }}>Prix *</Text>
          <TextInput
            placeholder="5000"
            value={price}
            onChangeText={setPrice}
            keyboardType="numeric"
            style={{ borderWidth: 1, borderColor: "#D1D5DB", borderRadius: 12, padding: 12 }}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13, color: "#374151", marginBottom: 4 }}>Devise</Text>
          <TextInput
            value={currency}
            onChangeText={setCurrency}
            placeholder="XOF"
            autoCapitalize="characters"
            style={{ borderWidth: 1, borderColor: "#D1D5DB", borderRadius: 12, padding: 12 }}
          />
        </View>
      </View>

      <View style={{ flexDirection: "row", gap: 10, marginBottom: 16 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13, color: "#374151", marginBottom: 4 }}>Latitude *</Text>
          <TextInput
            placeholder="6.1375"
            value={latitude}
            onChangeText={setLatitude}
            keyboardType="numeric"
            style={{ borderWidth: 1, borderColor: "#D1D5DB", borderRadius: 12, padding: 12 }}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13, color: "#374151", marginBottom: 4 }}>Longitude *</Text>
          <TextInput
            placeholder="1.2123"
            value={longitude}
            onChangeText={setLongitude}
            keyboardType="numeric"
            style={{ borderWidth: 1, borderColor: "#D1D5DB", borderRadius: 12, padding: 12 }}
          />
        </View>
      </View>

      <Pressable
        onPress={handleCreateTask}
        disabled={loading || !isValid}
        style={{ backgroundColor: "#6D28D9", borderRadius: 12, padding: 14, opacity: loading || !isValid ? 0.6 : 1 }}
      >
        <Text style={{ color: "#fff", textAlign: "center", fontWeight: "700" }}>
          {loading ? "Envoi..." : "Créer la tâche"}
        </Text>
      </Pressable>
    </View>
  );
}
