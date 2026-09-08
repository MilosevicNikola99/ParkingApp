<template>
  <AppLayout :user="currentUser" title="Reservation history" @logout="handleLogout">
    <AdminPageHeader description="Review current active reservations and historical reservation records." title="Reservations"><BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadReservations">Refresh</BaseButton></AdminPageHeader>
    <AlertMessage :message="errorMessage" />
    <section class="workspace-section workspace-section--form"><div class="workspace-section__header"><h2>Filters</h2><p>Use technical references, status, or history state to find a specific reservation.</p></div><form class="admin-filters" @submit.prevent="loadReservations">
      <BaseInput v-model="filters.userId" label="Reserved for user ID" min="1" name="reservation-user-filter" step="1" type="number" />
      <BaseInput v-model="filters.spotId" label="Parking spot ID" min="1" name="reservation-spot-filter" step="1" type="number" />
      <SelectField v-model="filters.status" label="Status" name="reservation-status-filter" :options="statusOptions" placeholder="All statuses" />
      <SelectField v-model="filters.currentActive" label="History state" name="reservation-history-filter" :options="historyOptions" placeholder="All history" />
      <div class="form-actions"><BaseButton size="compact" type="submit">Apply filters</BaseButton></div>
    </form></section>
    <LoadingState v-if="isLoading" message="Loading reservation history" />
    <EmptyState v-else-if="reservations.length === 0" title="No reservations" message="No records match the current filters." action-label="Clear filters or check again after assignments run." />
    <section v-else class="workspace-section" aria-label="Admin reservation history"><div class="data-table-wrap"><table class="data-table data-table--wide">
      <thead><tr><th>Reservation</th><th>Parking spot</th><th>Reserved for</th><th>Starts</th><th>Ends</th><th>Status</th><th>History state</th></tr></thead>
      <tbody><tr v-for="reservation in reservations" :key="reservation.id"><td class="data-table__id" data-label="Reservation">#{{ reservation.id }}</td><td data-label="Parking spot">{{ getParkingSpotLabel(reservation.parking_spot, reservation.parking_spot_id) }}<small class="data-table__reference">Spot #{{ reservation.parking_spot_id }}</small></td><td data-label="Reserved for"><PersonCell :fallback-id="reservation.reserved_for_user_id" show-reference :user="reservation.reserved_for_user" /></td><td data-label="Starts"><DateTimeDisplay :value="reservation.start_at" /></td><td data-label="Ends"><DateTimeDisplay :value="reservation.end_at" /></td><td data-label="Status"><StatusBadge :status="reservation.status" /></td><td data-label="History state"><StatusBadge :status="reservation.history_state" /></td></tr></tbody>
    </table></div></section>
  </AppLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import AdminPageHeader from "@/components/admin/AdminPageHeader.vue";
import SelectField from "@/components/admin/SelectField.vue";
import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import BaseInput from "@/components/common/BaseInput.vue";
import DateTimeDisplay from "@/components/common/DateTimeDisplay.vue";
import EmptyState from "@/components/common/EmptyState.vue";
import LoadingState from "@/components/common/LoadingState.vue";
import PersonCell from "@/components/common/PersonCell.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { listAdminReservationHistory } from "@/services/adminReservationService";
import { getApiErrorMessage } from "@/services/apiErrors";
import { getParkingSpotLabel, getStatusLabel } from "@/utils/display";

const { currentUser, handleLogout } = useAuthenticatedPage();
const reservations = ref([]); const isLoading = ref(true); const errorMessage = ref("");
const filters = reactive({ userId: "", spotId: "", status: "", currentActive: "" });
const statusOptions = ["active", "cancelled", "completed"].map((value) => ({ value, label: getStatusLabel(value) }));
const historyOptions = [{ value: "true", label: "Current active" }, { value: "false", label: "Historical" }];
function params() { const result = {}; if (filters.userId) result.reserved_for_user_id = Number(filters.userId); if (filters.spotId) result.parking_spot_id = Number(filters.spotId); if (filters.status) result.status = filters.status; if (filters.currentActive) result.current_active = filters.currentActive === "true"; return result; }
async function loadReservations() { errorMessage.value = ""; isLoading.value = true; try { reservations.value = await listAdminReservationHistory(params()); } catch (error) { errorMessage.value = getApiErrorMessage(error, "Reservation history could not be loaded."); } finally { isLoading.value = false; } }
onMounted(loadReservations);
</script>
