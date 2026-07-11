<template>
  <AppLayout :user="currentUser" title="Available spots" @logout="handleLogout">
    <div class="page-toolbar">
      <div>
        <p class="page-toolbar__eyebrow">Open parking</p>
        <h2>Available spots</h2>
        <p class="page-toolbar__description">Browse parking spaces that owners have made available and apply for the time you need.</p>
      </div>
      <BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadAvailabilities">
        Refresh
      </BaseButton>
    </div>

    <AlertMessage :message="errorMessage" />
    <AlertMessage :message="successMessage" variant="success" />

    <section class="context-help" aria-label="Available spots help">
      <strong>How it works:</strong> Open spots can receive applications. If priority is active, same-team applicants may be considered first until the priority time ends.
    </section>

    <LoadingState v-if="isLoading" />
    <EmptyState
      v-else-if="availabilities.length === 0"
      action-label="Check again later or ask a parking owner to publish availability."
      message="No parking spots are available right now."
      title="No open spots"
    />
    <section v-else class="workspace-section" aria-label="Open parking availability">
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th scope="col">Spot ID</th>
              <th scope="col">Owner ID</th>
              <th scope="col">Starts</th>
              <th scope="col">Ends</th>
              <th scope="col">Team priority until</th>
              <th scope="col">Status</th>
              <th scope="col">Note</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="availability in availabilities" :key="availability.id">
              <td class="data-table__id" data-label="Spot ID">#{{ availability.parking_spot_id }}</td>
              <td data-label="Owner ID">#{{ availability.owner_id }}</td>
              <td data-label="Starts"><DateTimeDisplay :value="availability.start_at" /></td>
              <td data-label="Ends"><DateTimeDisplay :value="availability.end_at" /></td>
              <td data-label="Team priority until"><DateTimeDisplay :value="availability.priority_until || ''" /></td>
              <td data-label="Status"><StatusBadge :status="availability.status" /></td>
              <td class="data-table__note" data-label="Note">{{ availability.note || "-" }}</td>
              <td data-label="Action"><BaseButton
                  :disabled="!currentUser || isOwnAvailability(availability) || appliedIds.includes(availability.id)"
                  :loading="applyingIds.includes(availability.id)"
                  size="compact"
                  @click="apply(availability)"
                >
                  {{ applyLabel(availability) }}
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
import { applyForAvailability } from "@/services/applicationService";
import { listOpenAvailabilities } from "@/services/availabilityService";

const { currentUser, handleLogout } = useAuthenticatedPage();
const availabilities = ref([]);
const appliedIds = ref([]);
const applyingIds = ref([]);
const errorMessage = ref("");
const successMessage = ref("");
const isLoading = ref(true);

function isOwnAvailability(availability) {
  return availability.owner_id === currentUser.value?.id;
}

function applyLabel(availability) {
  if (isOwnAvailability(availability)) {
    return "Own spot";
  }
  if (appliedIds.value.includes(availability.id)) {
    return "Applied";
  }
  return "Apply";
}

async function loadAvailabilities() {
  errorMessage.value = "";
  isLoading.value = true;
  try {
    availabilities.value = await listOpenAvailabilities();
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "Open parking availability could not be loaded.");
  } finally {
    isLoading.value = false;
  }
}

async function apply(availability) {
  if (
    !currentUser.value ||
    applyingIds.value.includes(availability.id) ||
    appliedIds.value.includes(availability.id)
  ) {
    return;
  }

  errorMessage.value = "";
  successMessage.value = "";
  applyingIds.value = [...applyingIds.value, availability.id];
  try {
    await applyForAvailability(availability.id);
    appliedIds.value = [...appliedIds.value, availability.id];
    successMessage.value = `Application submitted for parking spot #${availability.parking_spot_id}.`;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The parking application could not be submitted.");
  } finally {
    applyingIds.value = applyingIds.value.filter((id) => id !== availability.id);
  }
}

onMounted(loadAvailabilities);
</script>
