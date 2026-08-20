<template>
  <AppLayout :user="currentUser" title="Operational reports" @logout="handleLogout">
    <AdminPageHeader description="Monitor reservations, parking offers, employee requests, and audit activity." title="Reports">
      <BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadReports">
        Refresh
      </BaseButton>
    </AdminPageHeader>

    <AlertMessage :message="errorMessage" />

    <section class="context-help" aria-label="Reports help">
      <strong>Reports summarize operational activity.</strong> CSV exports use the active filters and include IDs, statuses, and timestamps for offline review.
    </section>

    <section class="workspace-section workspace-section--form" aria-labelledby="report-filters-title">
      <div class="workspace-section__header">
        <h2 id="report-filters-title">Created-date filters</h2>
        <p>Filters use inclusive UTC calendar dates for each record's creation time.</p>
      </div>
      <form class="admin-filters" @submit.prevent="loadReports">
        <BaseInput v-model="filters.dateFrom" label="From date" name="report-date-from" type="date" />
        <BaseInput v-model="filters.dateTo" label="To date" name="report-date-to" type="date" />
        <div class="form-actions">
          <BaseButton size="compact" type="submit">Apply filters</BaseButton>
        </div>
      </form>
    </section>

    <LoadingState v-if="isLoading" message="Loading operational reports" />
    <template v-else-if="summary">
      <section class="report-summary-grid" aria-label="Operational report summaries">
        <DashboardCard
          label="Active, cancelled, and completed"
          :metric="String(summary.reservation_summary.total)"
          status="Reservations"
          title="Total reservations"
        />
        <DashboardCard
          label="Published parking offers"
          :metric="String(summary.availability_summary.total)"
          status="Parking offers"
          title="Total offers"
        />
        <DashboardCard
          label="Submitted parking requests"
          :metric="String(summary.application_summary.total)"
          status="Requests"
          title="Total requests"
        />
        <DashboardCard
          label="Open records without reservations"
          :metric="String(summary.availability_summary.open_without_reservation)"
          status="Needs review"
          title="Open without reservation"
        />
      </section>

      <section class="report-lifecycle-grid" aria-label="Lifecycle summary counts">
        <div class="report-lifecycle-panel">
          <h2>Reservation lifecycle</h2>
          <dl class="report-status-list">
            <div><dt>Active reservations</dt><dd>{{ summary.reservation_summary.active }}</dd></div>
            <div><dt>Cancelled reservations</dt><dd>{{ summary.reservation_summary.cancelled }}</dd></div>
            <div><dt>Completed reservations</dt><dd>{{ summary.reservation_summary.completed }}</dd></div>
          </dl>
        </div>
        <div class="report-lifecycle-panel">
          <h2>Parking offer lifecycle</h2>
          <dl class="report-status-list">
            <div><dt>Open for requests</dt><dd>{{ summary.availability_summary.open }}</dd></div>
            <div><dt>Assigned</dt><dd>{{ summary.availability_summary.assigned }}</dd></div>
            <div><dt>Cancelled</dt><dd>{{ summary.availability_summary.cancelled }}</dd></div>
            <div><dt>Expired</dt><dd>{{ summary.availability_summary.expired }}</dd></div>
          </dl>
        </div>
        <div class="report-lifecycle-panel">
          <h2>Request lifecycle</h2>
          <dl class="report-status-list">
            <div><dt>Waiting for assignment</dt><dd>{{ summary.application_summary.pending }}</dd></div>
            <div><dt>Selected</dt><dd>{{ summary.application_summary.selected }}</dd></div>
            <div><dt>Not selected</dt><dd>{{ summary.application_summary.rejected }}</dd></div>
            <div><dt>Cancelled</dt><dd>{{ summary.application_summary.cancelled }}</dd></div>
          </dl>
        </div>
      </section>

      <section class="workspace-section workspace-section--form" aria-labelledby="exports-title">
        <div class="workspace-section__header">
          <h2 id="exports-title">CSV exports</h2>
          <p>Exports use the active created-date filters and contain operational IDs and status data only.</p>
        </div>
        <div class="report-export-actions">
          <BaseButton
            v-for="report in exportReports"
            :key="report.name"
            :loading="exportingReport === report.name"
            size="compact"
            variant="secondary"
            @click="downloadCsv(report.name)"
          >
            {{ report.label }}
          </BaseButton>
        </div>
      </section>

      <section class="report-table-grid">
        <div class="workspace-section report-table-section">
          <div class="workspace-section__header"><h2>Top reserved users</h2></div>
          <EmptyState v-if="topUsers.length === 0" action-label="Reservations will appear here after assignments are created." title="No reservation winners" />
          <div v-else class="data-table-wrap">
            <table class="data-table report-table">
              <thead><tr><th>User</th><th>Reservations</th></tr></thead>
              <tbody><tr v-for="user in topUsers" :key="user.user_id"><td class="data-table__id">#{{ user.user_id }}</td><td>{{ user.reservation_count }}</td></tr></tbody>
            </table>
          </div>
        </div>

        <div class="workspace-section report-table-section">
          <div class="workspace-section__header"><h2>Parking spot usage</h2></div>
          <EmptyState v-if="parkingSpotUsage.length === 0" action-label="Parking spot usage appears after reservations are created." title="No parking spot usage" />
          <div v-else class="data-table-wrap">
            <table class="data-table report-table">
              <thead><tr><th>Parking spot</th><th>Reservations</th></tr></thead>
              <tbody><tr v-for="spot in parkingSpotUsage" :key="spot.parking_spot_id"><td class="data-table__id">#{{ spot.parking_spot_id }}</td><td>{{ spot.reservation_count }}</td></tr></tbody>
            </table>
          </div>
        </div>

        <div class="workspace-section report-table-section">
          <div class="workspace-section__header"><h2>Assignment audit triggers</h2></div>
          <EmptyState v-if="summary.audit_trigger_summary.length === 0" action-label="Audit activity appears after assignment runs or overrides." title="No audit activity" />
          <div v-else class="data-table-wrap">
            <table class="data-table report-table">
              <thead><tr><th>Trigger source</th><th>Events</th></tr></thead>
              <tbody><tr v-for="item in summary.audit_trigger_summary" :key="item.trigger_source"><td><StatusBadge :status="item.trigger_source" /></td><td>{{ item.count }}</td></tr></tbody>
            </table>
          </div>
        </div>
      </section>
    </template>
  </AppLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AdminPageHeader from "@/components/admin/AdminPageHeader.vue";
import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import BaseInput from "@/components/common/BaseInput.vue";
import EmptyState from "@/components/common/EmptyState.vue";
import LoadingState from "@/components/common/LoadingState.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";
import DashboardCard from "@/components/dashboard/DashboardCard.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { getApiErrorMessage } from "@/services/apiErrors";
import {
  downloadReportCsv,
  getParkingSpotUsage,
  getSummaryReport,
  getTopUsers,
} from "@/services/adminReportService";

const { currentUser, handleLogout } = useAuthenticatedPage();
const summary = ref(null);
const topUsers = ref([]);
const parkingSpotUsage = ref([]);
const errorMessage = ref("");
const isLoading = ref(true);
const exportingReport = ref("");
const filters = reactive({ dateFrom: "", dateTo: "" });
const exportReports = [
  { name: "reservations", label: "Export reservations" },
  { name: "availabilities", label: "Export parking offers" },
  { name: "applications", label: "Export requests" },
  { name: "audit-logs", label: "Export audit logs" },
];

function reportParams() {
  const params = {};
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  return params;
}

function validateFilters() {
  if (filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo) {
    return "From date must be before or equal to the to date.";
  }
  return "";
}

async function loadReports() {
  errorMessage.value = validateFilters();
  if (errorMessage.value) return;

  isLoading.value = true;
  try {
    const params = reportParams();
    [summary.value, topUsers.value, parkingSpotUsage.value] = await Promise.all([
      getSummaryReport(params),
      getTopUsers(params),
      getParkingSpotUsage(params),
    ]);
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "Operational reports could not be loaded.");
  } finally {
    isLoading.value = false;
  }
}

async function downloadCsv(reportName) {
  if (exportingReport.value) return;
  errorMessage.value = validateFilters();
  if (errorMessage.value) return;

  exportingReport.value = reportName;
  try {
    await downloadReportCsv(reportName, reportParams());
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The CSV report could not be downloaded.");
  } finally {
    exportingReport.value = "";
  }
}

onMounted(loadReports);
</script>
