import { computed, ref, watch } from "vue";

import { listMyActiveParkingSpots } from "@/services/parkingSpotService";

export function useOwnedSpotCapability(user) {
  const hasOwnedActiveSpot = ref(false);

  async function refreshOwnedSpotCapability() {
    const userId = user.value?.id;
    hasOwnedActiveSpot.value = false;
    if (!userId) return;

    try {
      const spots = await listMyActiveParkingSpots({ limit: 1 });
      if (user.value?.id === userId) {
        hasOwnedActiveSpot.value = spots.length > 0;
      }
    } catch {
      hasOwnedActiveSpot.value = false;
    }
  }

  watch(() => user.value?.id, refreshOwnedSpotCapability, { immediate: true });

  const canOfferSpot = computed(
    () => user.value?.role === "parking_owner" || hasOwnedActiveSpot.value,
  );

  return { canOfferSpot, hasOwnedActiveSpot, refreshOwnedSpotCapability };
}
