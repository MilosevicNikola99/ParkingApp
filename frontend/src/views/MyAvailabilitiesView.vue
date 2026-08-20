<template>
  <AppLayout :user="currentUser" title="Offer my spot" @logout="handleLogout">
    <div class="page-toolbar">
      <div>
        <p class="page-toolbar__eyebrow">Parking owner</p>
        <h2>Offer your parking spot</h2>
        <p class="page-toolbar__description">Tell colleagues when one of your assigned parking spots is free.</p>
      </div>
      <BaseButton :loading="isPageLoading" size="compact" variant="secondary" @click="loadPage">Refresh</BaseButton>
    </div>

    <AlertMessage :message="errorMessage" />
    <AlertMessage :message="spotErrorMessage" />
    <AlertMessage :message="successMessage" variant="success" />

    <section class="context-help" aria-label="Parking offer help">
      <strong>Your assigned parking spots are shown automatically.</strong> Choose when your spot is free; no parking spot ID is needed.
    </section>

    <section class="workspace-section workspace-section--form" aria-labelledby="publish-availability-title">
      <div class="workspace-section__header">
        <h2 id="publish-availability-title">Create a parking offer</h2>
        <p>Select an assigned parking spot when needed, then choose when colleagues may use it.</p>
      </div>

      <p v-if="!isSpotLoading && !spotErrorMessage && ownedSpots.length === 0" class="context-help context-help--warning" role="status">
        You do not have an active parking spot assigned. Contact an administrator.
      </p>

      <form @submit.prevent="publishAvailability">
        <fieldset class="availability-form" :disabled="publishDisabled">
          <div v-if="ownedSpots.length === 1" class="owned-spot-summary">
            <span>Your parking spot</span>
            <strong>{{ parkingSpotLabel(ownedSpots[0]) }}</strong>
          </div>
          <SelectField
            v-else-if="ownedSpots.length > 1"
            v-model="form.parkingSpotId"
            label="Select parking spot"
            name="parking-spot"
            :options="parkingSpotOptions"
            placeholder="Choose your parking spot"
            required
          />
          <div v-else class="owned-spot-summary owned-spot-summary--empty" aria-hidden="true">
            <span>Your parking spot</span>
            <strong>{{ isSpotLoading ? "Loading assigned spots..." : "No active spot assigned" }}</strong>
          </div>

          <BaseInput v-model="form.startAt" label="Start" name="availability-start" required type="datetime-local" />
          <BaseInput v-model="form.endAt" label="End" name="availability-end" required type="datetime-local" />
          <BaseTextarea v-model="form.note" label="Note" name="availability-note" placeholder="Optional" />
          <AlertMessage :message="formError" />
          <div class="form-actions">
            <BaseButton :disabled="publishDisabled" :loading="isPublishing" type="submit">Publish offer</BaseButton>
          </div>
        </fieldset>
      </form>
    </section>

    <LoadingState v-if="isAvailabilityLoading" message="Loading published parking offers" />
    <EmptyState v-else-if="availabilities.length === 0" message="Parking offers you publish will appear here." title="No published offers" />
    <section v-else class="workspace-section" aria-label="My published parking offers">
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th scope="col">Parking spot</th><th scope="col">Starts</th><th scope="col">Ends</th>
              <th scope="col">Team priority until</th><th scope="col">Status</th><th scope="col">Note</th><th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="availability in availabilities" :key="availability.id">
              <td data-label="Parking spot"><strong class="data-table__primary">{{ availabilitySpotLabel(availability) }}</strong><small class="data-table__reference">Offer #{{ availability.id }}</small></td>
              <td data-label="Starts"><DateTimeDisplay :value="availability.start_at" /></td>
              <td data-label="Ends"><DateTimeDisplay :value="availability.end_at" /></td>
              <td data-label="Team priority until"><DateTimeDisplay :value="availability.priority_until || ''" /></td>
              <td data-label="Status"><StatusBadge :status="availability.status" /></td>
              <td class="data-table__note" data-label="Note">{{ availability.note || "-" }}</td>
              <td data-label="Action">
                <BaseButton :disabled="availability.status !== 'open'" :loading="cancellingIds.includes(availability.id)" size="compact" variant="danger" @click="cancel(availability)">Cancel</BaseButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import SelectField from "@/components/admin/SelectField.vue";
import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import BaseInput from "@/components/common/BaseInput.vue";
import BaseTextarea from "@/components/common/BaseTextarea.vue";
import DateTimeDisplay from "@/components/common/DateTimeDisplay.vue";
import EmptyState from "@/components/common/EmptyState.vue";
import LoadingState from "@/components/common/LoadingState.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { getApiErrorMessage } from "@/services/apiErrors";
import { cancelAvailability, createAvailability, listMyAvailabilities } from "@/services/availabilityService";
import { listMyActiveParkingSpots } from "@/services/parkingSpotService";
import { getParkingSpotLabel } from "@/utils/display";

const { currentUser, handleLogout } = useAuthenticatedPage();
const availabilities = ref([]);
const ownedSpots = ref([]);
const cancellingIds = ref([]);
const errorMessage = ref("");
const spotErrorMessage = ref("");
const successMessage = ref("");
const formError = ref("");
const isAvailabilityLoading = ref(true);
const isSpotLoading = ref(true);
const isPublishing = ref(false);
const form = reactive({ parkingSpotId: "", startAt: "", endAt: "", note: "" });

const isPageLoading = computed(() => isAvailabilityLoading.value || isSpotLoading.value);
const publishDisabled = computed(
  () => isSpotLoading.value || Boolean(spotErrorMessage.value) || ownedSpots.value.length === 0,
);
const parkingSpotOptions = computed(() =>
  ownedSpots.value.map((spot) => ({ value: spot.id, label: parkingSpotLabel(spot) })),
);

function parkingSpotLabel(spot) {
  return getParkingSpotLabel(spot);
}

function availabilitySpotLabel(availability) {
  const spot = availability.parking_spot || ownedSpots.value.find((item) => item.id === availability.parking_spot_id);
  return getParkingSpotLabel(spot, availability.parking_spot_id);
}

function selectedParkingSpotId() {
  if (ownedSpots.value.length === 1) return ownedSpots.value[0].id;
  return Number(form.parkingSpotId);
}

function resetForm() {
  form.startAt = "";
  form.endAt = "";
  form.note = "";
}

function validateForm() {
  const parkingSpotId = selectedParkingSpotId();
  const startAt = new Date(form.startAt);
  const endAt = new Date(form.endAt);
  if (!Number.isInteger(parkingSpotId) || parkingSpotId < 1) return "Select a parking spot.";
  if (!form.startAt || !form.endAt || Number.isNaN(startAt.getTime()) || Number.isNaN(endAt.getTime())) {
    return "Enter valid start and end times.";
  }
  if (endAt <= startAt) return "End time must be after start time.";
  return "";
}

async function loadAvailabilities() {
  errorMessage.value = "";
  isAvailabilityLoading.value = true;
  try {
    availabilities.value = await listMyAvailabilities();
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "Published parking offers could not be loaded.");
  } finally {
    isAvailabilityLoading.value = false;
  }
}

async function loadOwnedSpots() {
  spotErrorMessage.value = "";
  isSpotLoading.value = true;
  try {
    ownedSpots.value = await listMyActiveParkingSpots();
    if (ownedSpots.value.length === 1) {
      form.parkingSpotId = String(ownedSpots.value[0].id);
    } else if (!ownedSpots.value.some((spot) => spot.id === Number(form.parkingSpotId))) {
      form.parkingSpotId = "";
    }
  } catch (error) {
    ownedSpots.value = [];
    spotErrorMessage.value = getApiErrorMessage(
      error,
      "Your assigned parking spots could not be loaded. Try again or contact an administrator.",
    );
  } finally {
    isSpotLoading.value = false;
  }
}

async function loadPage() {
  await Promise.all([loadAvailabilities(), loadOwnedSpots()]);
}

async function publishAvailability() {
  formError.value = validateForm();
  errorMessage.value = "";
  successMessage.value = "";
  if (formError.value || publishDisabled.value) return;

  const parkingSpotId = selectedParkingSpotId();
  isPublishing.value = true;
  try {
    const availability = await createAvailability({
      parking_spot_id: parkingSpotId,
      start_at: new Date(form.startAt).toISOString(),
      end_at: new Date(form.endAt).toISOString(),
      note: form.note.trim() || null,
    });
    availabilities.value = [availability, ...availabilities.value];
    resetForm();
    const spot = ownedSpots.value.find((item) => item.id === parkingSpotId);
    successMessage.value = "Parking offer published for " + (spot ? parkingSpotLabel(spot) : "your parking spot") + ".";
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The parking offer could not be published.");
  } finally {
    isPublishing.value = false;
  }
}

async function cancel(availability) {
  if (cancellingIds.value.includes(availability.id)) return;
  errorMessage.value = "";
  successMessage.value = "";
  cancellingIds.value = [...cancellingIds.value, availability.id];
  try {
    const updatedAvailability = await cancelAvailability(availability.id);
    availabilities.value = availabilities.value.map((item) =>
      item.id === updatedAvailability.id ? updatedAvailability : item,
    );
    successMessage.value = "Parking offer for " + availabilitySpotLabel(availability) + " cancelled.";
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The parking offer could not be cancelled.");
  } finally {
    cancellingIds.value = cancellingIds.value.filter((id) => id !== availability.id);
  }
}

onMounted(loadPage);
</script>
