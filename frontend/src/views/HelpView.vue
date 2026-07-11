<template>
  <AppLayout :user="currentUser" title="Help" @logout="handleLogout">
    <div class="page-toolbar">
      <div>
        <p class="page-toolbar__eyebrow">User guide</p>
        <h2>How to use ParkingApp</h2>
        <p class="page-toolbar__description">
          Quick role-based guidance for applying, publishing availability, and managing parking operations.
        </p>
      </div>
    </div>

    <section class="help-grid" aria-label="Role quick-start guides">
      <article class="help-card">
        <p class="help-card__eyebrow">Employee</p>
        <h2>Request parking</h2>
        <ol>
          <li>Open Available spots and choose a parking window.</li>
          <li>Apply for the spot you need.</li>
          <li>Track the request in My applications.</li>
          <li>Check My reservations after assignment.</li>
        </ol>
      </article>

      <article class="help-card">
        <p class="help-card__eyebrow">Parking owner</p>
        <h2>Publish availability</h2>
        <ol>
          <li>Ask an administrator for your parking spot ID.</li>
          <li>Open My availabilities.</li>
          <li>Enter the spot ID, start time, end time, and note.</li>
          <li>Publish and review the status in your list.</li>
        </ol>
      </article>

      <article class="help-card">
        <p class="help-card__eyebrow">Administrator</p>
        <h2>Manage operations</h2>
        <ol>
          <li>Create teams, users, and parking spots.</li>
          <li>Review applications and reservations.</li>
          <li>Use Overrides only when an assignment needs correction.</li>
          <li>Use Audit logs and Reports to review activity.</li>
        </ol>
      </article>
    </section>

    <section class="workspace-section help-reference" aria-labelledby="help-status-title">
      <div class="workspace-section__header">
        <h2 id="help-status-title">Common statuses</h2>
        <p>Statuses describe where each parking record is in the workflow.</p>
      </div>
      <div class="status-reference-grid">
        <div>
          <h3>Availability</h3>
          <p><strong>open</strong> means employees can apply. <strong>assigned</strong> means a reservation exists.</p>
        </div>
        <div>
          <h3>Applications</h3>
          <p><strong>pending</strong> is waiting, <strong>selected</strong> received a reservation, and rejected was not selected.</p>
        </div>
        <div>
          <h3>Reservations</h3>
          <p><strong>active</strong> is currently assigned. Cancelled and completed records remain in history.</p>
        </div>
      </div>
    </section>
  </AppLayout>
</template>

<script setup>
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";

const { currentUser, handleLogout } = useAuthenticatedPage();
</script>