<template>
  <AppLayout :user="currentUser" title="Parking spot management" @logout="handleLogout">
    <AdminPageHeader description="Manage parking inventory, ownership, and active status." title="Parking spots"><BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadData">Refresh</BaseButton></AdminPageHeader>
    <AlertMessage :message="errorMessage" /><AlertMessage :message="successMessage" variant="success" />
    <section class="workspace-section workspace-section--form">
      <div class="workspace-section__header"><h2>{{ editingId ? "Edit parking spot" : "Create parking spot" }}</h2><p>Assign an owner so that person can publish availability for the spot.</p></div>
      <form class="admin-form" @submit.prevent="saveSpot">
        <BaseInput v-model="form.code" label="Code" name="spot-code" required />
        <BaseInput v-model="form.location" label="Location" name="spot-location" />
        <BaseTextarea v-model="form.description" label="Description" name="spot-description" />
        <SelectField v-model="form.ownerId" label="Owner" name="spot-owner" :options="ownerOptions" placeholder="Unassigned" />
        <SelectField v-model="form.isActive" label="Status" name="spot-status" :options="activeOptions" required />
        <div class="form-actions"><BaseButton v-if="editingId" size="compact" variant="secondary" @click="resetForm">Cancel edit</BaseButton><BaseButton :loading="isSaving" type="submit">{{ editingId ? "Save changes" : "Create spot" }}</BaseButton></div>
      </form>
    </section>
    <section class="workspace-section workspace-section--form">
      <div class="workspace-section__header"><h2>Filters</h2><p>Filter by owner or active status to focus the inventory list.</p></div>
      <form class="admin-filters" @submit.prevent="loadSpots">
        <SelectField v-model="filters.ownerId" label="Owner" name="spot-owner-filter" :options="ownerOptions" placeholder="All owners" />
        <SelectField v-model="filters.isActive" label="Status" name="spot-status-filter" :options="activeOptions" placeholder="All statuses" />
        <div class="form-actions"><BaseButton size="compact" type="submit">Apply filters</BaseButton></div>
      </form>
    </section>
    <LoadingState v-if="isLoading" message="Loading parking spots" />
    <EmptyState v-else-if="spots.length === 0" title="No parking spots" message="No records match the current filters." action-label="Clear filters or create a new parking spot above." />
    <section v-else class="workspace-section" aria-label="Admin parking spots"><div class="data-table-wrap"><table class="data-table data-table--wide">
      <thead><tr><th>Spot ID</th><th>Code</th><th>Location</th><th>Owner</th><th>Status</th><th>Description</th><th>Actions</th></tr></thead>
      <tbody><tr v-for="spot in spots" :key="spot.id"><td class="data-table__id" data-label="Spot ID">#{{ spot.id }}</td><td data-label="Code">{{ spot.code }}</td><td data-label="Location">{{ spot.location || "-" }}</td><td data-label="Owner"><PersonCell v-if="spot.owner_id" :fallback-id="spot.owner_id" :user="userById(spot.owner_id)" /><span v-else>-</span></td><td data-label="Status"><StatusBadge :status="spot.is_active ? 'active' : 'inactive'" /></td><td class="data-table__note" data-label="Description">{{ spot.description || "-" }}</td><td data-label="Actions"><div class="admin-row-actions"><BaseButton size="compact" variant="secondary" @click="editSpot(spot)">Edit</BaseButton><ConfirmAction :loading="deletingIds.includes(spot.id)" prompt="Delete this parking spot?" @confirm="deleteSpot(spot)" /></div></td></tr></tbody>
    </table></div></section>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import AdminPageHeader from "@/components/admin/AdminPageHeader.vue";
import ConfirmAction from "@/components/admin/ConfirmAction.vue";
import SelectField from "@/components/admin/SelectField.vue";
import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import BaseInput from "@/components/common/BaseInput.vue";
import BaseTextarea from "@/components/common/BaseTextarea.vue";
import EmptyState from "@/components/common/EmptyState.vue";
import LoadingState from "@/components/common/LoadingState.vue";
import PersonCell from "@/components/common/PersonCell.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { getApiErrorMessage } from "@/services/apiErrors";
import { createAdminParkingSpot, deleteAdminParkingSpot, listAdminParkingSpots, updateAdminParkingSpot } from "@/services/adminParkingSpotService";
import { listAdminUsers } from "@/services/adminUserService";

const { currentUser, handleLogout } = useAuthenticatedPage();
const spots = ref([]); const users = ref([]); const editingId = ref(null); const deletingIds = ref([]);
const isLoading = ref(true); const isSaving = ref(false); const errorMessage = ref(""); const successMessage = ref("");
const activeOptions = [{ value: "true", label: "Active" }, { value: "false", label: "Inactive" }];
const ownerOptions = computed(() => users.value.map((user) => ({ value: user.id, label: `${user.first_name} ${user.last_name} (#${user.id})` })));
const form = reactive({ code: "", location: "", description: "", ownerId: "", isActive: "true" });
const filters = reactive({ ownerId: "", isActive: "" });
function resetForm() { editingId.value = null; Object.assign(form, { code: "", location: "", description: "", ownerId: "", isActive: "true" }); }
function userById(userId) { return users.value.find((user) => user.id === userId) || null; }
function editSpot(spot) { editingId.value = spot.id; Object.assign(form, { code: spot.code, location: spot.location || "", description: spot.description || "", ownerId: spot.owner_id ?? "", isActive: String(spot.is_active) }); }
function payloadFromForm() { return { code: form.code.trim(), location: form.location.trim() || null, description: form.description.trim() || null, owner_id: form.ownerId === "" ? null : Number(form.ownerId), is_active: form.isActive === "true" }; }
function filterParams() { const params = {}; if (filters.ownerId) params.owner_id = Number(filters.ownerId); if (filters.isActive) params.is_active = filters.isActive === "true"; return params; }
async function loadSpots() { errorMessage.value = ""; isLoading.value = true; try { spots.value = await listAdminParkingSpots(filterParams()); } catch (error) { errorMessage.value = getApiErrorMessage(error, "Parking spots could not be loaded."); } finally { isLoading.value = false; } }
async function loadData() { errorMessage.value = ""; isLoading.value = true; try { [spots.value, users.value] = await Promise.all([listAdminParkingSpots(filterParams()), listAdminUsers()]); } catch (error) { errorMessage.value = getApiErrorMessage(error, "Parking spots could not be loaded."); } finally { isLoading.value = false; } }
async function saveSpot() { errorMessage.value = ""; successMessage.value = ""; isSaving.value = true; try { const saved = editingId.value ? await updateAdminParkingSpot(editingId.value, payloadFromForm()) : await createAdminParkingSpot(payloadFromForm()); spots.value = editingId.value ? spots.value.map((spot) => spot.id === saved.id ? saved : spot) : [saved, ...spots.value]; successMessage.value = `Parking spot "${saved.code}" saved.`; resetForm(); } catch (error) { errorMessage.value = getApiErrorMessage(error, "The parking spot could not be saved."); } finally { isSaving.value = false; } }
async function deleteSpot(spot) { if (deletingIds.value.includes(spot.id)) return; deletingIds.value = [...deletingIds.value, spot.id]; errorMessage.value = ""; successMessage.value = ""; try { await deleteAdminParkingSpot(spot.id); spots.value = spots.value.filter((item) => item.id !== spot.id); successMessage.value = `Parking spot "${spot.code}" deleted.`; } catch (error) { errorMessage.value = getApiErrorMessage(error, "The parking spot could not be deleted."); } finally { deletingIds.value = deletingIds.value.filter((id) => id !== spot.id); } }
onMounted(loadData);
</script>
