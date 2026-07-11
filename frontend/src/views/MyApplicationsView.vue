<template>
  <AppLayout :user="currentUser" title="My applications" @logout="handleLogout">
    <div class="page-toolbar">
      <div>
        <p class="page-toolbar__eyebrow">Parking requests</p>
        <h2>Application history</h2>
        <p class="page-toolbar__description">Track your parking requests and cancel pending requests if needed.</p>
      </div>
      <BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadApplications">
        Refresh
      </BaseButton>
    </div>

    <AlertMessage :message="errorMessage" />
    <AlertMessage :message="successMessage" variant="success" />

    <LoadingState v-if="isLoading" message="Loading parking applications" />
    <EmptyState
      v-else-if="applications.length === 0"
      message="Applications submitted for open parking availability will appear here."
      title="No parking applications"
    />
    <section v-else class="workspace-section" aria-label="My parking applications">
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th scope="col">Application ID</th>
              <th scope="col">Availability ID</th>
              <th scope="col">Status</th>
              <th scope="col">Note</th>
              <th scope="col">Created</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="application in applications" :key="application.id">
              <td class="data-table__id" data-label="Application ID">#{{ application.id }}</td>
              <td data-label="Availability ID">#{{ application.availability_id }}</td>
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
    errorMessage.value = getApiErrorMessage(error, "Parking applications could not be loaded.");
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
    successMessage.value = `Application #${application.id} cancelled.`;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The parking application could not be cancelled.");
  } finally {
    cancellingIds.value = cancellingIds.value.filter((id) => id !== application.id);
  }
}

onMounted(loadApplications);
</script>
