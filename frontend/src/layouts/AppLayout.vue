<template>
  <div class="app-shell" :class="{ 'app-shell--collapsed': isCollapsed }">
    <a class="skip-link" href="#main-content">Skip to main content</a>
    <aside class="app-shell__sidebar" @keydown.esc="closeMobileMenu">
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
        <button
          ref="mobileMenuButton"
          class="app-shell__menu-toggle"
          type="button"
          aria-controls="primary-navigation"
          :aria-expanded="isMobileMenuOpen"
          @click="isMobileMenuOpen = !isMobileMenuOpen"
        >{{ isMobileMenuOpen ? "Close menu" : "Menu" }}</button>
      </div>
      <nav id="primary-navigation" class="app-shell__nav" :class="{ 'app-shell__nav--open': isMobileMenuOpen }" aria-label="Primary navigation">
        <RouterLink
          v-for="item in primaryNavItems"
          :key="item.to"
          class="app-shell__nav-link"
          :aria-label="isCollapsed ? item.label : undefined"
          :title="isCollapsed ? item.label : undefined"
          :to="item.to"
          @click="isMobileMenuOpen = false"
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
            @click="isMobileMenuOpen = false"
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

      <main id="main-content" class="app-shell__content" tabindex="-1">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

import BaseButton from "@/components/common/BaseButton.vue";
import { useOwnedSpotCapability } from "@/composables/useOwnedSpotCapability";

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
const isMobileMenuOpen = ref(false);
const mobileMenuButton = ref(null);
const userRef = computed(() => props.user);
const { canOfferSpot } = useOwnedSpotCapability(userRef);
const parkingNavItems = [
  { to: "/availabilities", label: "Available spots", icon: "A" },
  { to: "/my-applications", label: "My requests", icon: "Q" },
  { to: "/my-reservations", label: "My reservations", icon: "R" },
];
const primaryNavItems = computed(() => [
  { to: "/dashboard", label: "Dashboard", icon: "D" },
  ...parkingNavItems,
  ...(canOfferSpot.value
    ? [{ to: "/my-availabilities", label: "Offer my spot", icon: "O" }]
    : []),
  { to: "/help", label: "Help", icon: "H" },
]);
const adminNavItems = [
  { to: "/admin", label: "Admin dashboard", icon: "D" },
  { to: "/admin/teams", label: "Teams", icon: "T" },
  { to: "/admin/users", label: "Users", icon: "U" },
  { to: "/admin/parking-spots", label: "Parking spots", icon: "P" },
  { to: "/admin/parking-applications", label: "Requests", icon: "Q" },
  { to: "/admin/reservations", label: "Reservations", icon: "R" },
  { to: "/admin/audit-logs", label: "Audit logs", icon: "L" },
  { to: "/admin/overrides", label: "Overrides", icon: "O" },
  { to: "/admin/reports", label: "Reports", icon: "S" },
];

function toggleSidebar() {
  isCollapsed.value = !isCollapsed.value;
}

function closeMobileMenu() {
  if (!isMobileMenuOpen.value) return;
  isMobileMenuOpen.value = false;
  mobileMenuButton.value?.focus();
}

watch(isCollapsed, (value) => {
  localStorage.setItem(sidebarStorageKey, String(value));
});
</script>
