<template>
  <AppLayout :user="currentUser" title="Dashboard" @logout="handleLogout">
    <section class="dashboard-hero">
      <div>
        <p class="dashboard-hero__eyebrow">Today</p>
        <h2>{{ greeting }}</h2>
        <p class="dashboard-hero__description">Choose the parking workflow you need. Administrative access adds tools without replacing your personal parking tasks.</p>
      </div>
      <span class="dashboard-hero__status">{{ roleLabel }}</span>
    </section>

    <AlertMessage v-if="errorMessage" :message="errorMessage" />

    <section class="dashboard-grid dashboard-grid--focused" :aria-label="`${roleLabel} dashboard tasks`">
      <DashboardCard
        v-for="card in dashboardCards"
        :key="`${card.to}-${card.title}`"
        v-bind="card"
      />
    </section>
  </AppLayout>
</template>

<script setup>
import { computed } from "vue";

import AlertMessage from "@/components/common/AlertMessage.vue";
import DashboardCard from "@/components/dashboard/DashboardCard.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import { useOwnedSpotCapability } from "@/composables/useOwnedSpotCapability";
import AppLayout from "@/layouts/AppLayout.vue";
const { currentUser, handleLogout, sessionError: errorMessage } = useAuthenticatedPage();
const { canOfferSpot } = useOwnedSpotCapability(currentUser);

const greeting = computed(() => {
  if (!currentUser.value) {
    return "Parking dashboard";
  }

  return `Welcome, ${currentUser.value.first_name}`;
});

const roleLabel = computed(() => currentUser.value?.role?.replace("_", " ") || "Authenticated");

const dashboardCards = computed(() => {
  const cards = [
    { label: "Find open parking windows and request the time you need.", metric: "Browse", status: "Parking", title: "Browse available spots", to: "/availabilities" },
    { label: "Track requests that are waiting, selected, cancelled, or not selected.", metric: "Review", status: "Requests", title: "Review my requests", to: "/my-applications" },
    { label: "See assigned parking and cancel when you no longer need it.", metric: "Review", status: "Reservations", title: "Review reservations", to: "/my-reservations" },
  ];

  if (canOfferSpot.value) {
    cards.push(
      {
        label: "Choose one of your assigned spots and tell employees when it is free.",
        metric: "Publish",
        status: "Parking offers",
        title: "Offer your parking spot",
        to: "/my-availabilities",
      },
      {
        label: "Review upcoming, assigned, cancelled, and past parking offers.",
        metric: "Review",
        status: "Your spots",
        title: "Review published offers",
        to: "/my-availabilities",
      },
    );
  }

  if (currentUser.value?.role === "admin") {
    cards.push(
      { label: "Manage teams, users, and assigned parking spots.", metric: "Setup", status: "Administration", title: "People and parking", to: "/admin" },
      { label: "Review employee requests, reservations, and corrections.", metric: "Operate", status: "Daily work", title: "Parking operations", to: "/admin/parking-applications" },
      { label: "Trace assignment decisions and administrator actions.", metric: "Audit", status: "Governance", title: "Audit activity", to: "/admin/audit-logs" },
      { label: "Review operational summaries and export supporting data.", metric: "Report", status: "Insights", title: "Reports", to: "/admin/reports" },
    );
  }

  return cards;
});
</script>
