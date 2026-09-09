<template>
  <div class="app-shell" :class="{ 'app-shell--collapsed': isCollapsed }">
    <a class="skip-link" href="#main-content">Skip to main content</a>
    <aside class="app-shell__sidebar" @keydown.esc="closeMobileMenu">
      <div class="app-shell__brand-row">
        <RouterLink class="app-shell__brand" to="/dashboard" :aria-label="isCollapsed ? 'Parking dashboard' : undefined">
          <span class="app-shell__brand-mark" aria-hidden="true">
            <svg class="app-shell__brand-logo" viewBox="0 0 32 32" focusable="false">
              <path class="app-shell__brand-sign" d="M9 26V6h8.1a6.6 6.6 0 0 1 0 13.2H9" />
              <path class="app-shell__brand-road" d="M9 19.2h8.1" />
            </svg>
          </span>
          <span class="app-shell__brand-text">Parking</span>
        </RouterLink>
        <button
          class="app-shell__collapse"
          type="button"
          :aria-label="isCollapsed ? 'Expand sidebar navigation' : 'Collapse sidebar navigation'"
          :aria-pressed="isCollapsed"
          @click="toggleSidebar"
        >
          <svg class="app-shell__collapse-icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
            <path :d="isCollapsed ? 'm7 4 6 6-6 6' : 'm13 4-6 6 6 6'" />
          </svg>
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
          <span class="app-shell__nav-icon"><NavigationIcon :name="item.icon" /></span>
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
            <span class="app-shell__nav-icon"><NavigationIcon :name="item.icon" /></span>
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
import NavigationIcon from "@/components/common/NavigationIcon.vue";
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
  { to: "/availabilities", label: "Available spots", icon: "parking" },
  { to: "/my-applications", label: "My requests", icon: "request" },
  { to: "/my-reservations", label: "My reservations", icon: "reservation" },
];
const primaryNavItems = computed(() => [
  { to: "/dashboard", label: "Dashboard", icon: "dashboard" },
  ...parkingNavItems,
  ...(canOfferSpot.value
    ? [{ to: "/my-availabilities", label: "Offer my spot", icon: "offer" }]
    : []),
  { to: "/help", label: "Help", icon: "help" },
]);
const adminNavItems = [
  { to: "/admin", label: "Admin dashboard", icon: "admin" },
  { to: "/admin/teams", label: "Teams", icon: "teams" },
  { to: "/admin/users", label: "Users", icon: "users" },
  { to: "/admin/parking-spots", label: "Parking spots", icon: "spots" },
  { to: "/admin/parking-applications", label: "Requests", icon: "inbox" },
  { to: "/admin/reservations", label: "Reservations", icon: "calendar" },
  { to: "/admin/audit-logs", label: "Audit logs", icon: "audit" },
  { to: "/admin/overrides", label: "Overrides", icon: "overrides" },
  { to: "/admin/reports", label: "Reports", icon: "reports" },
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
