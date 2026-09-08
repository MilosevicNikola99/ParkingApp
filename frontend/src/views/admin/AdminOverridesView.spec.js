import { flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

const overrideService = vi.hoisted(() => ({
  manualOverrideAssignment: vi.fn(),
  replaceReservationAssignment: vi.fn(),
}));

vi.mock("@/services/adminReservationOverrideService", () => overrideService);
vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Ada", last_name: "Admin", role: "admin" }),
    handleLogout: vi.fn(),
  }),
}));

import AdminOverridesView from "./AdminOverridesView.vue";

const AppLayoutStub = { template: "<div><slot /></div>" };
const reservation = {
  id: 21,
  availability_id: 22,
  application_id: 23,
  parking_spot_id: 24,
  reserved_for_user_id: 25,
  start_at: "2026-06-04T10:00:00Z",
  end_at: "2026-06-04T12:00:00Z",
  status: "active",
  parking_spot: { id: 24, code: "A-24", location: "North garage" },
  reserved_for_user: { id: 25, first_name: "Erin", last_name: "Employee", email: "erin@example.com" },
};

async function submitOverride(wrapper, mode, reason, options = {}) {
  const applicationId = options.applicationId === undefined ? "23" : options.applicationId;
  await wrapper.get(`input[name="${mode}-availability-id"]`).setValue("22");
  if (applicationId !== null) {
    await wrapper.get(`input[name="${mode}-application-id"]`).setValue(applicationId);
  }
  if (options.applicantId !== undefined) {
    await wrapper.get(`input[name="${mode}-applicant-id"]`).setValue(options.applicantId);
  }
  await wrapper.get(`textarea[name="${mode}-reason"]`).setValue(reason);
  await wrapper.get(`#${mode}-override-title`).element.closest("section").querySelector("form").dispatchEvent(
    new Event("submit", { bubbles: true, cancelable: true }),
  );
  await flushPromises();
}

describe("AdminOverridesView", () => {
  it("keeps a replacement error beside its form and removes stale result context on retry", async () => {
    overrideService.replaceReservationAssignment.mockResolvedValueOnce(reservation);
    const wrapper = mount(AdminOverridesView, {
      global: { stubs: { AppLayout: AppLayoutStub, RouterLink: RouterLinkStub } },
    });
    await submitOverride(wrapper, "replacement", "First correction");
    expect(wrapper.find('[aria-label="Reservation summary"]').exists()).toBe(true);

    overrideService.replaceReservationAssignment.mockRejectedValueOnce(new Error("Unavailable"));
    await submitOverride(wrapper, "replacement", "Retry correction");
    expect(wrapper.find('[aria-label="Reservation summary"]').exists()).toBe(false);
    expect(wrapper.get('[aria-labelledby="replacement-override-title"]').text()).toContain("could not be completed");
    expect(wrapper.get('[aria-labelledby="manual-override-title"]').text()).not.toContain("could not be completed");
    expect(wrapper.text()).not.toContain("replaced successfully");
    expect(wrapper.get('textarea[name="replacement-reason"]').element.value).toBe("Retry correction");
  });
  it("shows the returned reservation after a successful manual override", async () => {
    overrideService.manualOverrideAssignment.mockResolvedValue(reservation);
    const wrapper = mount(AdminOverridesView, {
      global: { stubs: { AppLayout: AppLayoutStub, RouterLink: RouterLinkStub } },
    });

    await submitOverride(wrapper, "manual", "Approved exception");

    expect(overrideService.manualOverrideAssignment).toHaveBeenCalledWith(22, 23, "Approved exception");
    expect(wrapper.text()).toContain("Reservation #21 created by manual override.");
    expect(wrapper.text()).toContain("Reservation #21");
    expect(wrapper.text()).toContain("A-24 - North garage");
    expect(wrapper.text()).toContain("Erin Employee");
    expect(wrapper.text()).toContain("erin@example.com");
  });

  it("shows the returned reservation after a successful replacement override", async () => {
    overrideService.replaceReservationAssignment.mockResolvedValue(reservation);
    const wrapper = mount(AdminOverridesView, {
      global: { stubs: { AppLayout: AppLayoutStub, RouterLink: RouterLinkStub } },
    });

    await submitOverride(wrapper, "replacement", "Replace active assignment");

    expect(overrideService.replaceReservationAssignment).toHaveBeenCalledWith(
      22,
      23,
      "Replace active assignment",
    );
    expect(wrapper.text()).toContain("Reservation #21 replaced successfully.");
    expect(wrapper.text()).toContain("Parking spot");
  });

  it("submits replacement override by applicant ID", async () => {
    overrideService.replaceReservationAssignment.mockResolvedValue(reservation);
    const wrapper = mount(AdminOverridesView, {
      global: { stubs: { AppLayout: AppLayoutStub, RouterLink: RouterLinkStub } },
    });

    await submitOverride(wrapper, "replacement", "Replace by applicant", {
      applicationId: null,
      applicantId: "25",
    });

    expect(overrideService.replaceReservationAssignment).toHaveBeenCalledWith(
      22,
      { applicantId: 25 },
      "Replace by applicant",
    );
    expect(wrapper.text()).toContain("Reservation #21 replaced successfully.");
  });
});
