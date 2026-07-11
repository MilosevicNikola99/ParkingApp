<template>
  <AppLayout :user="currentUser" title="My reservations" @logout="handleLogout">
    <div class="page-toolbar">
      <div>
        <p class="page-toolbar__eyebrow">Assigned parking</p>
        <h2>Reservation history</h2>
        <p class="page-toolbar__description">Review your assigned parking reservations and cancel when you no longer need the spot.</p>
      </div>
      <BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadReservations">
        Refresh
      </BaseButton>
    </div>

    <AlertMessage :message="errorMessage" />
    <AlertMessage :message="successMessage" variant="success" />

    <LoadingState v-if="isLoading" message="Loading parking reservations" />
    <EmptyState
      v-else-if="reservations.length === 0"
      message="Assigned parking reservations will appear here."
      title="No parking reservations"
    />
    <section v-else class="workspace-section" aria-label="My parking reservations">
      <div class="data-table-wrap">
        <table class="data-table data-table--wide">
          <thead>
            <tr>
              <th scope="col">Reservation ID</th>
              <th scope="col">Spot ID</th>
              <th scope="col">Starts</th>
              <th scope="col">Ends</th>
              <th scope="col">Status</th>
              <th scope="col">Cancellation reason</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="reservation in reservations" :key="reservation.id">
              <td class="data-table__id" data-label="Reservation ID">#{{ reservation.id }}</td>
              <td data-label="Spot ID">#{{ reservation.parking_spot_id }}</td>
              <td data-label="Starts"><DateTimeDisplay :value="reservation.start_at" /></td>
              <td data-label="Ends"><DateTimeDisplay :value="reservation.end_at" /></td>
              <td data-label="Status"><StatusBadge :status="reservation.status" /></td>
              <td class="data-table__reason" data-label="Cancellation reason">
                <input
                  v-model="cancellationReasons[reservation.id]"
                  :aria-label="`Cancellation reason for reservation #${reservation.id}`"
                  :disabled="reservation.status !== 'active'"
                  maxlength="1000"
                  placeholder="Optional"
                  type="text"
                />
              </td>
              <td>
                <BaseButton
                  :disabled="reservation.status !== 'active'"
                  :loading="cancellingIds.includes(reservation.id)"
                  size="compact"
                  variant="danger"
                  @click="cancel(reservation)"
                >
                  Cancel
                </BaseButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </AppLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import DateTimeDisplay from "@/components/common/DateTimeDisplay.vue";
import EmptyState from "@/components/common/EmptyState.vue";
import LoadingState from "@/components/common/LoadingState.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { getApiErrorMessage } from "@/services/apiErrors";
import { cancelReservation, listMyReservations } from "@/services/reservationService";

const { currentUser, handleLogout } = useAuthenticatedPage();
const reservations = ref([]);
const cancellationReasons = reactive({});
const cancellingIds = ref([]);
const errorMessage = ref("");
const successMessage = ref("");
const isLoading = ref(true);

async function loadReservations() {
  errorMessage.value = "";
  isLoading.value = true;
  try {
    reservations.value = await listMyReservations();
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "Parking reservations could not be loaded.");
  } finally {
    isLoading.value = false;
  }
}

async function cancel(reservation) {
  if (cancellingIds.value.includes(reservation.id)) {
    return;
  }

  errorMessage.value = "";
  successMessage.value = "";
  cancellingIds.value = [...cancellingIds.value, reservation.id];
  try {
    const updatedReservation = await cancelReservation(
      reservation.id,
      cancellationReasons[reservation.id],
    );
    reservations.value = reservations.value.map((item) =>
      item.id === updatedReservation.id ? updatedReservation : item,
    );
    cancellationReasons[reservation.id] = "";
    successMessage.value = `Reservation #${reservation.id} cancelled.`;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The parking reservation could not be cancelled.");
  } finally {
    cancellingIds.value = cancellingIds.value.filter((id) => id !== reservation.id);
  }
}

onMounted(loadReservations);
</script>
