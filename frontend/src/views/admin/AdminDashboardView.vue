<template>
  <AppLayout :user="currentUser" title="Administration" @logout="handleLogout">
    <section class="dashboard-hero">
      <div>
        <p class="dashboard-hero__eyebrow">Admin workspace</p>
        <h2>Manage parking operations</h2>
        <p class="dashboard-hero__description">Set up people and parking spots, review operational activity, and use overrides only when a correction is needed.</p>
      </div>
      <span class="dashboard-hero__status">Administrator</span>
    </section>

    <section class="admin-dashboard-groups" aria-label="Admin modules">
      <div class="dashboard-group">
        <div class="dashboard-group__header">
          <p>People and teams</p>
          <span>Setup</span>
        </div>
        <div class="dashboard-grid dashboard-grid--admin-group">
          <DashboardCard title="Teams" metric="Teams" label="Create and maintain company teams for assignment context." to="/admin/teams" />
          <DashboardCard title="Users" metric="Users" label="Manage access, roles, team membership, and account status." to="/admin/users" />
        </div>
      </div>

      <div class="dashboard-group">
        <div class="dashboard-group__header">
          <p>Parking spots</p>
          <span>Inventory</span>
        </div>
        <div class="dashboard-grid dashboard-grid--admin-group">
          <DashboardCard title="Parking spots" metric="Spots" label="Manage spot codes, owners, status, and descriptions." to="/admin/parking-spots" />
        </div>
      </div>

      <div class="dashboard-group">
        <div class="dashboard-group__header">
          <p>Operations</p>
          <span>Daily work</span>
        </div>
        <div class="dashboard-grid dashboard-grid--admin-group">
          <DashboardCard title="Applications" metric="Review" label="Inspect submitted requests and their assignment status." to="/admin/parking-applications" />
          <DashboardCard title="Reservations" metric="History" label="Review active and historical reservation records." to="/admin/reservations" />
          <DashboardCard title="Overrides" metric="Override" label="Perform reason-required manual or replacement assignments." to="/admin/overrides" />
        </div>
      </div>

      <div class="dashboard-group">
        <div class="dashboard-group__header">
          <p>Reports and audit</p>
          <span>Review</span>
        </div>
        <div class="dashboard-grid dashboard-grid--admin-group">
          <DashboardCard title="Audit logs" metric="Audit" label="Review assignment decisions and override history." to="/admin/audit-logs" />
          <DashboardCard title="Reports" metric="Reports" label="Monitor summaries and export CSV data." to="/admin/reports" />
        </div>
      </div>
    </section>
  </AppLayout>
</template>

<script setup>
import DashboardCard from "@/components/dashboard/DashboardCard.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";

const { currentUser, handleLogout } = useAuthenticatedPage();
</script>