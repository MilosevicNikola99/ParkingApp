<template>
  <AppLayout :user="currentUser" title="Dashboard" @logout="handleLogout">
    <section class="dashboard-hero">
      <div>
        <p class="dashboard-hero__eyebrow">Today</p>
        <h2>{{ greeting }}</h2>
        <p class="dashboard-hero__description">Choose the parking workflow you need. Your available actions depend on your role.</p>
      </div>
      <span class="dashboard-hero__status">{{ roleLabel }}</span>
    </section>

    <AlertMessage v-if="errorMessage" :message="errorMessage" />

    <section class="dashboard-grid dashboard-grid--focused" aria-label="Dashboard modules">
      <DashboardCard
        label="Find open parking windows and apply for the time you need."
        metric="Browse"
        status="Employee"
        title="Browse available spots"
        to="/availabilities"
      />
      <DashboardCard
        label="Track pending, selected, cancelled, and rejected requests."
        metric="Review"
        status="Requests"
        title="Review applications"
        to="/my-applications"
      />
      <DashboardCard
        label="See assigned parking and cancel when you no longer need it."
        metric="Review"
        status="Reservations"
        title="Review reservations"
        to="/my-reservations"
      />
      <DashboardCard
        label="Publish the times when your spot is available to others."
        metric="Manage"
        status="Owner"
        title="Manage my availabilities"
        to="/my-availabilities"
      />
    </section>
  </AppLayout>
</template>

<script setup>
import { computed } from "vue";

import AlertMessage from "@/components/common/AlertMessage.vue";
import DashboardCard from "@/components/dashboard/DashboardCard.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
const { currentUser, handleLogout, sessionError: errorMessage } = useAuthenticatedPage();

const greeting = computed(() => {
  if (!currentUser.value) {
    return "Parking dashboard";
  }

  return `Welcome, ${currentUser.value.first_name}`;
});

const roleLabel = computed(() => currentUser.value?.role?.replace("_", " ") || "Authenticated");
</script>