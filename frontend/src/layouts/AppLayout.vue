<template>
  <div class="app-shell" :class="{ 'app-shell--collapsed': isCollapsed }">
    <aside class="app-shell__sidebar">
      <div class="app-shell__brand-row">
        <RouterLink class="app-shell__brand" to="/dashboard" :aria-label="isCollapsed ? 'Parking dashboard' : undefined">
          <span class="app-shell__brand-mark" aria-hidden="true">P</span>
          <span class="app-shell__brand-text">Parking</span>
        </RouterLink>
        <button
          class="app-shell__collapse"
          type="button"
          :aria-label="isCollapsed ? 'Expand sidebar navigation' : 'Collapse sidebar navigation'"
          :aria-pressed="isCollapsed"
          @click="toggleSidebar"
        >
          <span aria-hidden="true">{{ isCollapsed ? ">" : "<" }}</span>
        </button>
      </div>
      <nav class="app-shell__nav" aria-label="Primary navigation">
        <RouterLink
          v-for="item in primaryNavItems"
          :key="item.to"
          class="app-shell__nav-link"
          :aria-label="isCollapsed ? item.label : undefined"
          :title="isCollapsed ? item.label : undefined"
          :to="item.to"
        >
          <span class="app-shell__nav-icon" aria-hidden="true">{{ item.icon }}</span>
          <span class="app-shell__nav-label">{{ item.label }}</span>
        </RouterLink>
        <template v-if="isAdmin">
          <p class="app-shell__nav-heading">Admin</p>
          <RouterLink
            v-for="item in adminNavItems"
            :key="item.to"
            class="app-shell__nav-link"
            :aria-label="isCollapsed ? item.label : undefined"
            :title="isCollapsed ? item.label : undefined"
            :to="item.to"
          >
            <span class="app-shell__nav-icon" aria-hidden="true">{{ item.icon }}</span>
            <span class="app-shell__nav-label">{{ item.label }}</span>
          </RouterLink>
        </template>
      </nav>
    </aside>

    <div class="app-shell__main">
      <header class="app-shell__topbar">
        <div>
          <p class="app-shell__eyebrow">Company Parking</p>
          <h1>{{ title }}</h1>
        </div>
        <div class="app-shell__user">
          <RouterLink class="app-shell__help-link" to="/help">Help</RouterLink>
          <span v-if="user">{{ user.first_name }} {{ user.last_name }}</span>
          <BaseButton variant="secondary" @click="$emit('logout')">Sign out</BaseButton>
        </div>
      </header>

      <main class="app-shell__content">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

import BaseButton from "@/components/common/BaseButton.vue";

const props = defineProps({
  title: {
    type: String,
    default: "Dashboard",
  },
  user: {
    type: Object,
    default: null,
  },
});

defineEmits(["logout"]);

const sidebarStorageKey = "parking-app-sidebar-collapsed";
const isAdmin = computed(() => props.user?.role === "admin");
const isCollapsed = ref(localStorage.getItem(sidebarStorageKey) === "true");
const primaryNavItems = [
  { to: "/dashboard", label: "Dashboard", icon: "D" },
  { to: "/availabilities", label: "Available spots", icon: "A" },
  { to: "/my-availabilities", label: "My availabilities", icon: "O" },
  { to: "/my-applications", label: "My applications", icon: "Q" },
  { to: "/my-reservations", label: "My reservations", icon: "R" },
  { to: "/help", label: "Help", icon: "H" },
];
const adminNavItems = [
  { to: "/admin", label: "Admin dashboard", icon: "D" },
  { to: "/admin/teams", label: "Teams", icon: "T" },
  { to: "/admin/users", label: "Users", icon: "U" },
  { to: "/admin/parking-spots", label: "Parking spots", icon: "P" },
  { to: "/admin/parking-applications", label: "Applications", icon: "A" },
  { to: "/admin/reservations", label: "Reservations", icon: "R" },
  { to: "/admin/audit-logs", label: "Audit logs", icon: "L" },
  { to: "/admin/overrides", label: "Overrides", icon: "O" },
  { to: "/admin/reports", label: "Reports", icon: "S" },
];

function toggleSidebar() {
  isCollapsed.value = !isCollapsed.value;
}

watch(isCollapsed, (value) => {
  localStorage.setItem(sidebarStorageKey, String(value));
});
</script>