import { useEffect, useState } from "react";
import { paymentService, type PaymentMethod } from "@zaska/shared-services";

export function usePayments() {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await paymentService.getPaymentMethods();
        setMethods(data);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  return {
    methods,
    loading,
  };
}
