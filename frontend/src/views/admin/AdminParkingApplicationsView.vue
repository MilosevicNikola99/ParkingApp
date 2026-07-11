<template>
  <AppLayout :user="currentUser" title="Parking applications" @logout="handleLogout">
    <AdminPageHeader description="Review submitted requests and their current assignment status." title="Application activity"><BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadApplications">Refresh</BaseButton></AdminPageHeader>
    <AlertMessage :message="errorMessage" />
    <section class="workspace-section workspace-section--form"><div class="workspace-section__header"><h2>Filters</h2><p>Use availability ID or status to narrow the application list.</p></div><form class="admin-filters" @submit.prevent="loadApplications">
      <BaseInput v-model="filters.availabilityId" label="Availability ID" min="1" name="application-availability-filter" step="1" type="number" />
      <SelectField v-model="filters.status" label="Status" name="application-status-filter" :options="statusOptions" placeholder="All statuses" />
      <div class="form-actions"><BaseButton size="compact" type="submit">Apply filters</BaseButton></div>
    </form></section>
    <LoadingState v-if="isLoading" message="Loading parking applications" />
    <EmptyState v-else-if="applications.length === 0" title="No applications" message="No records match the current filters." action-label="Clear filters or check again after employees apply." />
    <section v-else class="workspace-section" aria-label="Admin parking applications"><div class="data-table-wrap"><table class="data-table">
      <thead><tr><th>Application ID</th><th>Availability ID</th><th>Applicant ID</th><th>Status</th><th>Note</th><th>Created</th></tr></thead>
      <tbody><tr v-for="application in applications" :key="application.id"><td class="data-table__id" data-label="Application ID">#{{ application.id }}</td><td data-label="Availability ID">#{{ application.availability_id }}</td><td data-label="Applicant ID">#{{ application.applicant_id }}</td><td data-label="Status"><StatusBadge :status="application.status" /></td><td class="data-table__note" data-label="Note">{{ application.note || "-" }}</td><td data-label="Created"><DateTimeDisplay :value="application.created_at" /></td></tr></tbody>
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
import StatusBadge from "@/components/common/StatusBadge.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { listAdminParkingApplications } from "@/services/adminParkingApplicationService";
import { getApiErrorMessage } from "@/services/apiErrors";

const { currentUser, handleLogout } = useAuthenticatedPage();
const applications = ref([]); const isLoading = ref(true); const errorMessage = ref("");
const filters = reactive({ availabilityId: "", status: "" });
const statusOptions = ["pending", "selected", "rejected", "cancelled"].map((value) => ({ value, label: value.replace("_", " ") }));
function params() { const result = {}; if (filters.availabilityId) result.availability_id = Number(filters.availabilityId); if (filters.status) result.status = filters.status; return result; }
async function loadApplications() { errorMessage.value = ""; isLoading.value = true; try { applications.value = await listAdminParkingApplications(params()); } catch (error) { errorMessage.value = getApiErrorMessage(error, "Parking applications could not be loaded."); } finally { isLoading.value = false; } }
onMounted(loadApplications);
</script>
