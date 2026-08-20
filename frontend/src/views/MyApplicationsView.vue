<template>
  <AppLayout :user="currentUser" title="My requests" @logout="handleLogout">
    <div class="page-toolbar">
      <div>
        <p class="page-toolbar__eyebrow">Parking requests</p>
        <h2>My parking requests</h2>
        <p class="page-toolbar__description">Track your parking requests and cancel pending requests if needed.</p>
      </div>
      <BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadApplications">
        Refresh
      </BaseButton>
    </div>

    <AlertMessage :message="errorMessage" />
    <AlertMessage :message="successMessage" variant="success" />

    <LoadingState v-if="isLoading" message="Loading parking requests" />
    <EmptyState
      v-else-if="applications.length === 0"
      message="Requests submitted for available parking spots will appear here."
      title="No parking requests"
    />
    <section v-else class="workspace-section" aria-label="My parking requests">
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th scope="col">Parking spot</th>
              <th scope="col">Parking window</th>
              <th scope="col">Status</th>
              <th scope="col">Note</th>
              <th scope="col">Created</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="application in applications" :key="application.id">
              <td data-label="Parking spot">
                <strong class="data-table__primary">{{ getParkingSpotLabel(application.availability?.parking_spot) }}</strong>
                <small class="data-table__reference">Request #{{ application.id }} · Offer #{{ application.availability_id }}</small>
              </td>
              <td data-label="Parking window">
                <DateTimeDisplay :value="application.availability?.start_at || ''" />
                <span class="data-table__range-separator">to</span>
                <DateTimeDisplay :value="application.availability?.end_at || ''" />
              </td>
              <td data-label="Status"><StatusBadge :status="application.status" /></td>
              <td class="data-table__note" data-label="Note">{{ application.note || "-" }}</td>
              <td data-label="Created"><DateTimeDisplay :value="application.created_at" /></td>
              <td>
                <BaseButton
                  :disabled="application.status !== 'pending'"
                  :loading="cancellingIds.includes(application.id)"
                  size="compact"
                  variant="danger"
                  @click="cancel(application)"
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
import { onMounted, ref } from "vue";

import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import DateTimeDisplay from "@/components/common/DateTimeDisplay.vue";
import EmptyState from "@/components/common/EmptyState.vue";
import LoadingState from "@/components/common/LoadingState.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { getApiErrorMessage } from "@/services/apiErrors";
import { cancelApplication, listMyApplications } from "@/services/applicationService";
import { getParkingSpotLabel } from "@/utils/display";

const { currentUser, handleLogout } = useAuthenticatedPage();
const applications = ref([]);
const cancellingIds = ref([]);
const errorMessage = ref("");
const successMessage = ref("");
const isLoading = ref(true);

async function loadApplications() {
  errorMessage.value = "";
  isLoading.value = true;
  try {
    applications.value = await listMyApplications();
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "Parking requests could not be loaded.");
  } finally {
    isLoading.value = false;
  }
}

async function cancel(application) {
  if (cancellingIds.value.includes(application.id)) {
    return;
  }

  errorMessage.value = "";
  successMessage.value = "";
  cancellingIds.value = [...cancellingIds.value, application.id];
  try {
    const updatedApplication = await cancelApplication(application.id);
    applications.value = applications.value.map((item) =>
      item.id === updatedApplication.id ? updatedApplication : item,
    );
    successMessage.value = `Parking request for ${getParkingSpotLabel(application.availability?.parking_spot)} cancelled.`;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The parking request could not be cancelled.");
  } finally {
    cancellingIds.value = cancellingIds.value.filter((id) => id !== application.id);
  }
}

onMounted(loadApplications);
</script>
