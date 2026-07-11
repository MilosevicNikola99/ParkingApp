<template>
  <AppLayout :user="currentUser" title="Team management" @logout="handleLogout">
    <AdminPageHeader description="Create and maintain teams used for user organization and assignment context." title="Teams">
      <BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadTeams">Refresh</BaseButton>
    </AdminPageHeader>

    <AlertMessage :message="errorMessage" />
    <AlertMessage :message="successMessage" variant="success" />

    <section class="workspace-section workspace-section--form" aria-labelledby="team-form-title">
      <div class="workspace-section__header">
        <h2 id="team-form-title">{{ editingId ? "Edit team" : "Create team" }}</h2>
        <p>Use clear team names that employees and administrators can recognize.</p>
      </div>
      <form class="admin-form" @submit.prevent="saveTeam">
        <BaseInput v-model="form.name" label="Name" name="team-name" required />
        <BaseTextarea v-model="form.description" label="Description" name="team-description" />
        <div class="form-actions">
          <BaseButton v-if="editingId" size="compact" variant="secondary" @click="resetForm">Cancel edit</BaseButton>
          <BaseButton :loading="isSaving" type="submit">{{ editingId ? "Save changes" : "Create team" }}</BaseButton>
        </div>
      </form>
    </section>

    <LoadingState v-if="isLoading" message="Loading teams" />
    <EmptyState v-else-if="teams.length === 0" title="No teams" message="Create the first company team." action-label="Use the form above to add a team." />
    <section v-else class="workspace-section" aria-label="Admin teams">
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Team ID</th><th>Name</th><th>Description</th><th>Updated</th><th>Actions</th></tr></thead>
          <tbody>
            <tr v-for="team in teams" :key="team.id">
              <td class="data-table__id" data-label="Team ID">#{{ team.id }}</td>
              <td data-label="Name">{{ team.name }}</td>
              <td class="data-table__note" data-label="Description">{{ team.description || "-" }}</td>
              <td data-label="Updated"><DateTimeDisplay :value="team.updated_at" /></td>
              <td data-label="Actions"><div class="admin-row-actions">
                <BaseButton size="compact" variant="secondary" @click="editTeam(team)">Edit</BaseButton>
                <ConfirmAction :loading="deletingIds.includes(team.id)" prompt="Delete this team?" @confirm="deleteTeam(team)" />
              </div></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </AppLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AdminPageHeader from "@/components/admin/AdminPageHeader.vue";
import ConfirmAction from "@/components/admin/ConfirmAction.vue";
import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import BaseInput from "@/components/common/BaseInput.vue";
import BaseTextarea from "@/components/common/BaseTextarea.vue";
import DateTimeDisplay from "@/components/common/DateTimeDisplay.vue";
import EmptyState from "@/components/common/EmptyState.vue";
import LoadingState from "@/components/common/LoadingState.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { getApiErrorMessage } from "@/services/apiErrors";
import { createAdminTeam, deleteAdminTeam, listAdminTeams, updateAdminTeam } from "@/services/adminTeamService";

const { currentUser, handleLogout } = useAuthenticatedPage();
const teams = ref([]);
const editingId = ref(null);
const deletingIds = ref([]);
const isLoading = ref(true);
const isSaving = ref(false);
const errorMessage = ref("");
const successMessage = ref("");
const form = reactive({ name: "", description: "" });

function resetForm() {
  editingId.value = null;
  form.name = "";
  form.description = "";
}

function editTeam(team) {
  editingId.value = team.id;
  form.name = team.name;
  form.description = team.description || "";
}

async function loadTeams() {
  errorMessage.value = "";
  isLoading.value = true;
  try {
    teams.value = await listAdminTeams();
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "Teams could not be loaded.");
  } finally {
    isLoading.value = false;
  }
}

async function saveTeam() {
  errorMessage.value = "";
  successMessage.value = "";
  isSaving.value = true;
  const payload = { name: form.name.trim(), description: form.description.trim() || null };
  try {
    const saved = editingId.value
      ? await updateAdminTeam(editingId.value, payload)
      : await createAdminTeam(payload);
    teams.value = editingId.value
      ? teams.value.map((team) => team.id === saved.id ? saved : team)
      : [saved, ...teams.value];
    successMessage.value = `Team "${saved.name}" saved.`;
    resetForm();
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The team could not be saved.");
  } finally {
    isSaving.value = false;
  }
}

async function deleteTeam(team) {
  if (deletingIds.value.includes(team.id)) return;
  deletingIds.value = [...deletingIds.value, team.id];
  errorMessage.value = "";
  successMessage.value = "";
  try {
    await deleteAdminTeam(team.id);
    teams.value = teams.value.filter((item) => item.id !== team.id);
    if (editingId.value === team.id) resetForm();
    successMessage.value = `Team "${team.name}" deleted.`;
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "The team could not be deleted.");
  } finally {
    deletingIds.value = deletingIds.value.filter((id) => id !== team.id);
  }
}

onMounted(loadTeams);
</script>
