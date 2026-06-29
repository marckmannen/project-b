// Customer order management
class OrderManager {
  static async fetchOrdersByPin(pin) {
    try {
      const response = await fetch(`/api/orders/pin/${pin}`);
      if (!response.ok) {
        throw new Error('Failed to fetch orders');
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching orders by PIN:', error);
      return [];
    }
  }

  static async fetchOrdersByBirthDate(birthDate) {
    try {
      const response = await fetch(`/api/orders/birthdate/${birthDate}`);
      if (!response.ok) {
        throw new Error('Failed to fetch orders');
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching orders by birthdate:', error);
      return [];
    }
  }
}

window.OrderManager = OrderManager;
