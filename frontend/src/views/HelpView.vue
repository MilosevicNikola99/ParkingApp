<template>
  <AppLayout :user="currentUser" title="Help" @logout="handleLogout">
    <div class="page-toolbar">
      <div>
        <p class="page-toolbar__eyebrow">User guide</p>
        <h2>How to use ParkingApp</h2>
        <p class="page-toolbar__description">
          Quick guidance for requesting parking, offering an assigned spot, and managing operations.
        </p>
      </div>
    </div>

    <section class="help-grid" aria-label="Role quick-start guides">
      <article class="help-card">
        <p class="help-card__eyebrow">Employee</p>
        <h2>Request parking</h2>
        <ol>
          <li>Open Available spots and choose a parking window.</li>
          <li>Request the spot you need.</li>
          <li>Track the request in My requests.</li>
          <li>Check My reservations after assignment.</li>
        </ol>
      </article>

      <article class="help-card">
        <p class="help-card__eyebrow">Parking owner</p>
        <h2>Offer a parking spot</h2>
        <ol>
          <li>Open Offer my spot.</li>
          <li>Confirm the assigned parking spot shown automatically.</li>
          <li>Choose when the spot is free and add an optional note.</li>
          <li>Publish the offer and review its status in the list.</li>
        </ol>
      </article>

      <article class="help-card">
        <p class="help-card__eyebrow">Administrator</p>
        <h2>Manage and participate</h2>
        <ol>
          <li>Use Available spots, My requests, and My reservations for your own parking.</li>
          <li>Use Offer my spot when an active parking spot is assigned to you.</li>
          <li>Create teams, users, and parking spots.</li>
          <li>Review requests and reservations.</li>
          <li>Use Overrides only when an assignment needs correction.</li>
          <li>Open readable Audit log decisions; expand Technical details only for support.</li>
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
          <h3>Parking offers</h3>
          <p><strong>Open for requests</strong> means employees can request the spot. <strong>Assigned</strong> means a reservation exists.</p>
        </div>
        <div>
          <h3>Requests</h3>
          <p><strong>Waiting for assignment</strong> means no decision yet. <strong>Selected</strong> received a reservation, and <strong>Not selected</strong> did not.</p>
        </div>
        <div>
          <h3>Reservations</h3>
          <p><strong>Active</strong> is currently assigned. Cancelled and completed records remain in history.</p>
        </div>
      </div>
    </section>

    <section class="context-help" aria-label="Identity and audit guidance">
      <strong>People are shown by name and email.</strong> Technical user and request references remain available to administrators for support, overrides, and auditing.
    </section>
  </AppLayout>
</template>

<script setup>
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";

const { currentUser, handleLogout } = useAuthenticatedPage();
</script>
