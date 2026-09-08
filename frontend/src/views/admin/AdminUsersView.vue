<template>
  <AppLayout :user="currentUser" title="User management" @logout="handleLogout">
    <AdminPageHeader description="Manage access, roles, team assignments, and active account status." title="Users">
      <BaseButton :loading="isLoading" size="compact" variant="secondary" @click="loadData">Refresh</BaseButton>
    </AdminPageHeader>
    <AlertMessage :message="errorMessage" />
    <AlertMessage :message="successMessage" variant="success" />

    <section class="workspace-section workspace-section--form" aria-labelledby="user-form-title">
      <div class="workspace-section__header"><h2 id="user-form-title">{{ editingId ? "Edit user" : "Create user" }}</h2><p>Choose the role carefully; it controls which navigation and workflows the user can access.</p></div>
      <form class="admin-form" @submit.prevent="saveUser">
        <BaseInput v-model="form.email" label="Email" name="user-email" required type="email" />
        <BaseInput v-model="form.username" label="Username" name="user-username" required />
        <BaseInput v-model="form.firstName" label="First name" name="user-first-name" required />
        <BaseInput v-model="form.lastName" label="Last name" name="user-last-name" required />
        <BaseInput v-if="!editingId" v-model="form.password" autocomplete="new-password" label="Password" name="user-password" required type="password" />
        <SelectField v-model="form.role" label="Role" name="user-role" :options="roleOptions" required />
        <SelectField v-model="form.teamId" label="Team" name="user-team" :options="teamOptions" placeholder="No team" />
        <SelectField v-model="form.isActive" label="Status" name="user-status" :options="activeOptions" required />
        <div class="form-actions">
          <BaseButton v-if="editingId" size="compact" variant="secondary" @click="resetForm">Cancel edit</BaseButton>
          <BaseButton :loading="isSaving" type="submit">{{ editingId ? "Save changes" : "Create user" }}</BaseButton>
        </div>
      </form>
    </section>

    <LoadingState v-if="isLoading" message="Loading users" />
    <EmptyState v-else-if="users.length === 0" title="No users" message="Create the first user account." action-label="Use the form above to add an employee, owner, or administrator." />
    <section v-else class="workspace-section" aria-label="Admin users">
      <div class="data-table-wrap"><table class="data-table data-table--wide">
        <thead><tr><th>User ID</th><th>User</th><th>Role</th><th>Team</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody><tr v-for="user in users" :key="user.id">
          <td class="data-table__id" data-label="User ID">#{{ user.id }}</td><td data-label="User"><PersonCell show-username :user="user" /></td><td data-label="Role"><StatusBadge :status="user.role" /></td><td data-label="Team">{{ teamName(user.team_id) }}</td><td data-label="Status"><StatusBadge :status="user.is_active ? 'active' : 'inactive'" /></td><td data-label="Actions"><div class="admin-row-actions">
            <BaseButton size="compact" variant="secondary" @click="editUser(user)">Edit</BaseButton>
            <ConfirmAction :loading="deletingIds.includes(user.id)" prompt="Delete this user?" @confirm="deleteUser(user)" />
          </div></td>
        </tr></tbody>
      </table></div>
    </section>
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
import EmptyState from "@/components/common/EmptyState.vue";
import LoadingState from "@/components/common/LoadingState.vue";
import PersonCell from "@/components/common/PersonCell.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";
import { useAuthenticatedPage } from "@/composables/useAuthenticatedPage";
import AppLayout from "@/layouts/AppLayout.vue";
import { getApiErrorMessage } from "@/services/apiErrors";
import { listAdminTeams } from "@/services/adminTeamService";
import { createAdminUser, deleteAdminUser, listAdminUsers, updateAdminUser } from "@/services/adminUserService";

const { currentUser, handleLogout } = useAuthenticatedPage();
const users = ref([]);
const teams = ref([]);
const editingId = ref(null);
const deletingIds = ref([]);
const isLoading = ref(true);
const isSaving = ref(false);
const errorMessage = ref("");
const successMessage = ref("");
const roleOptions = [{ value: "admin", label: "Admin" }, { value: "employee", label: "Employee" }, { value: "parking_owner", label: "Parking owner" }];
const activeOptions = [{ value: "true", label: "Active" }, { value: "false", label: "Inactive" }];
const teamOptions = computed(() => teams.value.map((team) => ({ value: team.id, label: team.name })));
const form = reactive({ email: "", username: "", firstName: "", lastName: "", password: "", role: "employee", teamId: "", isActive: "true" });

function resetForm() {
  editingId.value = null;
  Object.assign(form, { email: "", username: "", firstName: "", lastName: "", password: "", role: "employee", teamId: "", isActive: "true" });
}
function teamName(teamId) { return teams.value.find((team) => team.id === teamId)?.name || "-"; }
function editUser(user) {
  editingId.value = user.id;
  Object.assign(form, { email: user.email, username: user.username, firstName: user.first_name, lastName: user.last_name, password: "", role: user.role, teamId: user.team_id ?? "", isActive: String(user.is_active) });
}
function payloadFromForm(includePassword) {
  const payload = { email: form.email.trim(), username: form.username.trim(), first_name: form.firstName.trim(), last_name: form.lastName.trim(), role: form.role, team_id: form.teamId === "" ? null : Number(form.teamId), is_active: form.isActive === "true" };
  if (includePassword) payload.password = form.password;
  return payload;
}
async function loadData() {
  errorMessage.value = ""; isLoading.value = true;
  try { [users.value, teams.value] = await Promise.all([listAdminUsers(), listAdminTeams()]); }
  catch (error) { errorMessage.value = getApiErrorMessage(error, "Users could not be loaded."); }
  finally { isLoading.value = false; }
}
async function saveUser() {
  errorMessage.value = ""; successMessage.value = ""; isSaving.value = true;
  try {
    const saved = editingId.value ? await updateAdminUser(editingId.value, payloadFromForm(false)) : await createAdminUser(payloadFromForm(true));
    users.value = editingId.value ? users.value.map((user) => user.id === saved.id ? saved : user) : [saved, ...users.value];
    successMessage.value = `User "${saved.username}" saved.`; resetForm();
  } catch (error) { errorMessage.value = getApiErrorMessage(error, "The user could not be saved."); }
  finally { isSaving.value = false; }
}
async function deleteUser(user) {
  if (deletingIds.value.includes(user.id)) return;
  deletingIds.value = [...deletingIds.value, user.id]; errorMessage.value = ""; successMessage.value = "";
  try { await deleteAdminUser(user.id); users.value = users.value.filter((item) => item.id !== user.id); successMessage.value = `User "${user.username}" deleted.`; }
  catch (error) { errorMessage.value = getApiErrorMessage(error, "The user could not be deleted."); }
  finally { deletingIds.value = deletingIds.value.filter((id) => id !== user.id); }
}
onMounted(loadData);
</script>
