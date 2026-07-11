import { createRouter, createWebHistory } from "vue-router";

import { getStoredCurrentUser, hasAccessToken } from "@/services/authStorage";
import AdminAssignmentAuditLogsView from "@/views/admin/AdminAssignmentAuditLogsView.vue";
import AdminDashboardView from "@/views/admin/AdminDashboardView.vue";
import AdminOverridesView from "@/views/admin/AdminOverridesView.vue";
import AdminParkingApplicationsView from "@/views/admin/AdminParkingApplicationsView.vue";
import AdminParkingSpotsView from "@/views/admin/AdminParkingSpotsView.vue";
import AdminReservationsView from "@/views/admin/AdminReservationsView.vue";
import AdminReportsView from "@/views/admin/AdminReportsView.vue";
import AdminTeamsView from "@/views/admin/AdminTeamsView.vue";
import AdminUsersView from "@/views/admin/AdminUsersView.vue";
import AvailableSpotsView from "@/views/AvailableSpotsView.vue";
import DashboardView from "@/views/DashboardView.vue";
import HelpView from "@/views/HelpView.vue";
import LoginView from "@/views/LoginView.vue";
import MyApplicationsView from "@/views/MyApplicationsView.vue";
import MyAvailabilitiesView from "@/views/MyAvailabilitiesView.vue";
import MyReservationsView from "@/views/MyReservationsView.vue";
import NotFoundView from "@/views/NotFoundView.vue";

export const routes = [
  {
    path: "/",
    redirect: () => (hasAccessToken() ? "/dashboard" : "/login"),
  },
  {
    path: "/login",
    name: "login",
    component: LoginView,
    meta: { guestOnly: true },
  },
  {
    path: "/dashboard",
    name: "dashboard",
    component: DashboardView,
    meta: { requiresAuth: true },
  },
  {
    path: "/availabilities",
    name: "availabilities",
    component: AvailableSpotsView,
    meta: { requiresAuth: true },
  },
  {
    path: "/my-availabilities",
    name: "my-availabilities",
    component: MyAvailabilitiesView,
    meta: { requiresAuth: true },
  },
  {
    path: "/my-applications",
    name: "my-applications",
    component: MyApplicationsView,
    meta: { requiresAuth: true },
  },
  {
    path: "/my-reservations",
    name: "my-reservations",
    component: MyReservationsView,
    meta: { requiresAuth: true },
  },
  {
    path: "/help",
    name: "help",
    component: HelpView,
    meta: { requiresAuth: true },
  },
  {
    path: "/admin",
    name: "admin",
    component: AdminDashboardView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/admin/teams",
    name: "admin-teams",
    component: AdminTeamsView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/admin/users",
    name: "admin-users",
    component: AdminUsersView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/admin/parking-spots",
    name: "admin-parking-spots",
    component: AdminParkingSpotsView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/admin/parking-applications",
    name: "admin-parking-applications",
    component: AdminParkingApplicationsView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/admin/reservations",
    name: "admin-reservations",
    component: AdminReservationsView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/admin/audit-logs",
    name: "admin-audit-logs",
    component: AdminAssignmentAuditLogsView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/admin/overrides",
    name: "admin-overrides",
    component: AdminOverridesView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/admin/reports",
    name: "admin-reports",
    component: AdminReportsView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/:pathMatch(.*)*",
    name: "not-found",
    component: NotFoundView,
  },
];

export function createAppRouter(history = createWebHistory()) {
  const router = createRouter({
    history,
    routes,
  });

  router.beforeEach((to) => {
    const isAuthenticated = hasAccessToken();

    if (to.meta.requiresAuth && !isAuthenticated) {
      return { name: "login", query: { redirect: to.fullPath } };
    }

    if (to.meta.requiresAdmin && getStoredCurrentUser()?.role !== "admin") {
      return { name: "dashboard" };
    }

    if (to.meta.guestOnly && isAuthenticated) {
      return { name: "dashboard" };
    }

    return true;
  });

  return router;
}

const router = createAppRouter();

export default router;
