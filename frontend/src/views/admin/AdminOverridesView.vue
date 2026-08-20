<template>
  <AppLayout :user="currentUser" title="Reservation overrides" @logout="handleLogout">
    <AdminPageHeader
      description="Use overrides only when an administrator needs to correct or manually replace an assignment. Every action requires an audit reason."
      title="Override assignments"
    />

    <section class="context-help context-help--warning" aria-label="Override guidance">
      <strong>Before you submit:</strong> Find the request and reservation in the admin lists first. Manual assignment creates a reservation from a waiting request on an open parking offer. Replacement changes the active reservation for an assigned offer.
    </section>

    <AlertMessage :message="errorMessage" />
    <AlertMessage :message="successMessage" variant="success" />

    <div class="admin-action-grid">
      <div>
        <AdminOverrideForm
          description="Use this when an open parking offer has no reservation and a waiting request should be assigned."
          :loading="manualLoading"
          mode="manual"
          submit-label="Assign request"
          title="Manual assignment"
          @submit="submitManualOverride"
        />
        <ReservationSummaryCard :reservation="manualReservation" />
      </div>

      <div>
        <AdminOverrideForm
          description="Use this when an assigned parking offer must move from the current reservation holder to another employee."
          :loading="replacementLoading"
          mode="replacement"
          submit-label="Replace reservation"
          title="Replacement assignment"
          @submit="submitReplacementOverride"
        />
        <ReservationSummaryCard :reservation="replacementReservation" />
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref } from "vue";

import AdminOverrideForm from "@/components/admin/AdminOverrideForm.vue";
import AdminPageHeader from "@/components/admin/AdminPageHeader.vue";
import ReservationSummaryCard from "@/components/admin/ReservationSummaryCard.vue";
import AlertMessage from "@/components/common/AlertMessage.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { getApiErrorMessage } from "@/services/apiErrors";
import {
  manualOverrideAssignment,
  replaceReservationAssignment,
} from "@/services/adminReservationOverrideService";

const { currentUser, handleLogout } = useAuthenticatedPage();
const manualReservation = ref(null);
const replacementReservation = ref(null);
const manualLoading = ref(false);
const replacementLoading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

async function submitManualOverride({ availabilityId, applicationId, reason }) {
  if (manualLoading.value) {
    return;
  }

  errorMessage.value = "";
  successMessage.value = "";
  manualLoading.value = true;
  try {
    manualReservation.value = await manualOverrideAssignment(availabilityId, applicationId, reason);
    successMessage.value = `Reservation #${manualReservation.value.id} created by manual override.`;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The manual assignment could not be completed.");
  } finally {
    manualLoading.value = false;
  }
}

async function submitReplacementOverride({ availabilityId, applicationId, applicantId, reason }) {
  if (replacementLoading.value) {
    return;
  }

  errorMessage.value = "";
  successMessage.value = "";
  replacementLoading.value = true;
  try {
    const selector = applicantId === undefined ? applicationId : { applicantId };
    replacementReservation.value = await replaceReservationAssignment(availabilityId, selector, reason);
    successMessage.value = `Reservation #${replacementReservation.value.id} replaced successfully.`;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The replacement assignment could not be completed.");
  } finally {
    replacementLoading.value = false;
  }
}
</script>
