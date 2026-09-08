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
    <section v-else class="audit-log-list" aria-label="Assignment audit logs">
      <article v-for="auditLog in auditLogs" :key="auditLog.id" class="audit-log-card">
        <header class="audit-log-card__header">
          <div>
            <p class="audit-log-card__reference">Audit log #{{ auditLog.id }}</p>
            <h2>Reservation #{{ auditLog.reservation_id }}</h2>
          </div>
          <div class="audit-log-card__meta">
            <StatusBadge :status="auditLog.trigger_source" />
            <DateTimeDisplay :value="auditLog.created_at" />
          </div>
        </header>
        <div class="audit-log-card__summary">
          <div>
            <span class="audit-log-card__label">Selected employee</span>
            <PersonCell :fallback-id="auditLog.selected_user_id" show-reference :user="userById(auditLog.selected_user_id)" />
          </div>
          <div>
            <span class="audit-log-card__label">Outcome references</span>
            <strong>Offer #{{ auditLog.availability_id }}</strong>
            <small>Request #{{ auditLog.selected_application_id }}</small>
          </div>
          <div>
            <span class="audit-log-card__label">Ranking policy</span>
            <strong>{{ auditLog.ranking_policy }}</strong>
          </div>
        </div>
        <AuditDecisionDetails :audit-log="auditLog" :users-by-id="usersById" />
      </article>
    </section>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AdminPageHeader from "@/components/admin/AdminPageHeader.vue";
import AuditDecisionDetails from "@/components/admin/AuditDecisionDetails.vue";
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
import { listAdminAssignmentAuditLogs } from "@/services/adminAssignmentAuditLogService";
import { listAdminUsers } from "@/services/adminUserService";
import { getApiErrorMessage } from "@/services/apiErrors";

const { currentUser, handleLogout } = useAuthenticatedPage();
const auditLogs = ref([]);
const users = ref([]);
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
const usersById = computed(() => Object.fromEntries(users.value.map((user) => [user.id, user])));

function userById(userId) {
  return usersById.value[userId] || null;
}

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
    [auditLogs.value, users.value] = await Promise.all([
      listAdminAssignmentAuditLogs(filterParams()),
      listAdminUsers({ limit: 1000 }),
    ]);
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "Assignment audit logs could not be loaded.");
  } finally {
    isLoading.value = false;
  }
}

onMounted(loadAuditLogs);
</script>
