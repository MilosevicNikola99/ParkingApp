<template>
  <AppLayout :user="currentUser" title="Assignment audit logs" @logout="handleLogout">
    <AdminPageHeader description="Review how assignments were made, which request was selected, and why other requests were not selected." title="Assignment decisions">
      <BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadAuditLogs">
        Refresh
      </BaseButton>
    </AdminPageHeader>

    <AlertMessage :message="errorMessage" />

    <section class="context-help" aria-label="Audit log help">
      <strong>Audit logs explain assignment decisions.</strong> Use availability, reservation, or selected user IDs to trace a specific parking outcome.
    </section>

    <section class="workspace-section workspace-section--form" aria-labelledby="audit-log-filters-title">
      <div class="workspace-section__header">
        <h2 id="audit-log-filters-title">Filters</h2>
        <p>Filter by operational IDs when investigating a specific assignment or override.</p>
      </div>
      <form class="admin-filters" @submit.prevent="loadAuditLogs">
        <BaseInput
          v-model="filters.availabilityId"
          label="Availability ID"
          min="1"
          name="audit-availability-filter"
          step="1"
          type="number"
        />
        <BaseInput
          v-model="filters.reservationId"
          label="Reservation ID"
          min="1"
          name="audit-reservation-filter"
          step="1"
          type="number"
        />
        <BaseInput
          v-model="filters.selectedUserId"
          label="Selected user ID"
          min="1"
          name="audit-user-filter"
          step="1"
          type="number"
        />
        <SelectField
          v-model="filters.triggerSource"
          label="Trigger source"
          name="audit-trigger-filter"
          :options="triggerSourceOptions"
          placeholder="All sources"
        />
        <BaseInput
          v-model="filters.rankingPolicy"
          label="Ranking policy"
          name="audit-policy-filter"
          placeholder="Exact policy name"
        />
        <div class="form-actions">
          <BaseButton size="compact" type="submit">Apply filters</BaseButton>
        </div>
      </form>
    </section>

    <LoadingState v-if="isLoading" message="Loading assignment audit logs" />
    <EmptyState
      v-else-if="auditLogs.length === 0"
      message="No assignment decisions match the selected filters."
      title="No audit logs"
    />
    <section v-else class="workspace-section" aria-label="Assignment audit logs">
      <div class="data-table-wrap">
        <table class="data-table data-table--wide">
          <thead>
            <tr>
              <th>Log ID</th>
              <th>Availability ID</th>
              <th>Reservation ID</th>
              <th>Selected application ID</th>
              <th>Selected user ID</th>
              <th>Trigger</th>
              <th>Ranking policy</th>
              <th>Decision details</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="auditLog in auditLogs" :key="auditLog.id">
              <td class="data-table__id" data-label="Log ID">#{{ auditLog.id }}</td><td data-label="Availability ID">#{{ auditLog.availability_id }}</td><td data-label="Reservation ID">#{{ auditLog.reservation_id }}</td><td data-label="Selected application ID">#{{ auditLog.selected_application_id }}</td><td data-label="Selected user ID">#{{ auditLog.selected_user_id }}</td><td data-label="Trigger"><StatusBadge :status="auditLog.trigger_source" /></td><td data-label="Ranking policy">{{ auditLog.ranking_policy }}</td><td class="data-table__decision" data-label="Decision details">
                <JsonDetailsViewer
                  :summary="`${auditLog.ranking_details.length} ranked requests`"
                  :value="auditLog.ranking_details"
                />
                <JsonDetailsViewer
                  :summary="`${auditLog.rejected_application_ids.length} requests not selected`"
                  :value="auditLog.rejected_application_ids"
                />
              </td>
              <td data-label="Created"><DateTimeDisplay :value="auditLog.created_at" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </AppLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AdminPageHeader from "@/components/admin/AdminPageHeader.vue";
import JsonDetailsViewer from "@/components/admin/JsonDetailsViewer.vue";
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
import { listAdminAssignmentAuditLogs } from "@/services/adminAssignmentAuditLogService";
import { getApiErrorMessage } from "@/services/apiErrors";

const { currentUser, handleLogout } = useAuthenticatedPage();
const auditLogs = ref([]);
const errorMessage = ref("");
const isLoading = ref(true);
const filters = reactive({
  availabilityId: "",
  reservationId: "",
  selectedUserId: "",
  triggerSource: "",
  rankingPolicy: "",
});
const triggerSourceOptions = [
  "system",
  "manual_owner",
  "manual_admin",
  "scheduled",
  "admin_override",
].map((value) => ({ value, label: value.replaceAll("_", " ") }));

function filterParams() {
  const params = {};
  if (filters.availabilityId) params.availability_id = Number(filters.availabilityId);
  if (filters.reservationId) params.reservation_id = Number(filters.reservationId);
  if (filters.selectedUserId) params.selected_user_id = Number(filters.selectedUserId);
  if (filters.triggerSource) params.trigger_source = filters.triggerSource;
  if (filters.rankingPolicy.trim()) params.ranking_policy = filters.rankingPolicy.trim();
  return params;
}

async function loadAuditLogs() {
  errorMessage.value = "";
  isLoading.value = true;
  try {
    auditLogs.value = await listAdminAssignmentAuditLogs(filterParams());
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "Assignment audit logs could not be loaded.");
  } finally {
    isLoading.value = false;
  }
}

onMounted(loadAuditLogs);
</script>
