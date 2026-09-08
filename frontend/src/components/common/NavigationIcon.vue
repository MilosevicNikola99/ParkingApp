<template>
  <svg
    class="navigation-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
    :data-icon="name"
  >
    <template v-if="name === 'dashboard'">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </template>
    <template v-else-if="name === 'parking'">
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 17V7h3.2a3.2 3.2 0 0 1 0 6.4H9.5M9.5 13.4h3.2" />
    </template>
    <template v-else-if="name === 'request'">
      <path d="M7 3h8l4 4v14H7z" />
      <path d="M15 3v5h4M10 12h6M10 16h6" />
    </template>
    <template v-else-if="name === 'reservation'">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 10h18M8 15l2.2 2.2L16 13" />
    </template>
    <template v-else-if="name === 'offer'">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 16V8M8.5 11.5 12 8l3.5 3.5" />
    </template>
    <template v-else-if="name === 'help'">
      <circle cx="12" cy="12" r="9" />
      <path d="M9.7 9a2.5 2.5 0 1 1 3.2 2.4c-.9.3-.9 1-.9 1.6M12 17h.01" />
    </template>
    <template v-else-if="name === 'admin'">
      <path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6z" />
      <path d="M9 13h6M10 10h4M10 16h4" />
    </template>
    <template v-else-if="name === 'teams'">
      <circle cx="9" cy="9" r="3" />
      <circle cx="17" cy="10" r="2" />
      <path d="M3.5 20a5.5 5.5 0 0 1 11 0M14.5 16.5a4 4 0 0 1 6 3.5" />
    </template>
    <template v-else-if="name === 'users'">
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 21a7.5 7.5 0 0 1 15 0" />
    </template>
    <template v-else-if="name === 'spots'">
      <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
      <path d="M10 14V7h2.4a2.3 2.3 0 0 1 0 4.6H10" />
    </template>
    <template v-else-if="name === 'inbox'">
      <path d="M4 4h16v16H4zM4 14h4l2 3h4l2-3h4M8 8h8M8 11h6" />
    </template>
    <template v-else-if="name === 'calendar'">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 10h18M8 14h3M8 17h5" />
    </template>
    <template v-else-if="name === 'audit'">
      <path d="M9 5h6M9 3h6v4H9zM7 5H5v16h14V5h-2" />
      <circle cx="11" cy="13" r="3" />
      <path d="m13.2 15.2 2.3 2.3" />
    </template>
    <template v-else-if="name === 'overrides'">
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="8" cy="17" r="2" />
    </template>
    <template v-else-if="name === 'reports'">
      <path d="M4 20V10h4v10M10 20V4h4v16M16 20v-7h4v7M3 20h18" />
    </template>
  </svg>
</template>

<script setup>
defineProps({
  name: {
    type: String,
    required: true,
  },
});
</script>
