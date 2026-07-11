<template>
  <section v-if="reservation" class="reservation-summary" aria-label="Reservation summary">
    <div class="reservation-summary__header">
      <h2>Reservation #{{ reservation.id }}</h2>
      <StatusBadge :status="reservation.status" />
    </div>
    <dl>
      <div><dt>Availability</dt><dd>#{{ reservation.availability_id }}</dd></div>
      <div><dt>Application</dt><dd>{{ reservation.application_id ? `#${reservation.application_id}` : "-" }}</dd></div>
      <div><dt>Parking spot</dt><dd>#{{ reservation.parking_spot_id }}</dd></div>
      <div><dt>Reserved for</dt><dd>#{{ reservation.reserved_for_user_id }}</dd></div>
      <div><dt>Starts</dt><dd><DateTimeDisplay :value="reservation.start_at" /></dd></div>
      <div><dt>Ends</dt><dd><DateTimeDisplay :value="reservation.end_at" /></dd></div>
    </dl>
  </section>
</template>

<script setup>
import DateTimeDisplay from "@/components/common/DateTimeDisplay.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";

defineProps({
  reservation: {
    type: Object,
    default: null,
  },
});
</script>
