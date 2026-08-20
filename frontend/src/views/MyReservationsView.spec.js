import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

const reservationService = vi.hoisted(() => ({
  cancelReservation: vi.fn(),
  listMyReservations: vi.fn(),
}));

vi.mock("@/services/reservationService", () => reservationService);
vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Employee", last_name: "User" }),
    handleLogout: vi.fn(),
  }),
}));

import MyReservationsView from "./MyReservationsView.vue";

const AppLayoutStub = {
  template: "<div><slot /></div>",
};

describe("MyReservationsView", () => {
  it("allows only active reservations to be cancelled and prevents duplicate requests", async () => {
    reservationService.listMyReservations.mockResolvedValue([
      {
        id: 41,
        parking_spot_id: 22,
        start_at: "2026-06-10T10:00:00Z",
        end_at: "2026-06-10T12:00:00Z",
        status: "active",
        parking_spot: { id: 22, code: "A-22", location: "North garage" },
      },
      {
        id: 42,
        parking_spot_id: 23,
        start_at: "2026-06-09T10:00:00Z",
        end_at: "2026-06-09T12:00:00Z",
        status: "cancelled",
      },
    ]);
    let resolveCancellation;
    reservationService.cancelReservation.mockImplementation(
      () => new Promise((resolve) => {
        resolveCancellation = resolve;
      }),
    );
    const wrapper = mount(MyReservationsView, {
      global: { stubs: { AppLayout: AppLayoutStub } },
    });
    await flushPromises();

    const reasonInput = wrapper.get('input[aria-label="Cancellation reason for reservation #41"]');
    const disabledReasonInput = wrapper.get('input[aria-label="Cancellation reason for reservation #42"]');
    expect(disabledReasonInput.attributes()).toHaveProperty("disabled");

    await reasonInput.setValue("Changed plans");
    const cancelButtons = wrapper.findAll("button").filter((button) => button.text() === "Cancel");
    expect(cancelButtons[1].attributes()).toHaveProperty("disabled");

    await cancelButtons[0].trigger("click");
    await cancelButtons[0].trigger("click");
    expect(reservationService.cancelReservation).toHaveBeenCalledTimes(1);
    expect(reservationService.cancelReservation).toHaveBeenCalledWith(41, "Changed plans");

    resolveCancellation({
      id: 41,
      parking_spot_id: 22,
      start_at: "2026-06-10T10:00:00Z",
      end_at: "2026-06-10T12:00:00Z",
      status: "cancelled",
    });
    await flushPromises();
    expect(wrapper.text()).toContain("Reservation for A-22 - North garage cancelled.");
    expect(wrapper.get('input[aria-label="Cancellation reason for reservation #41"]').attributes()).toHaveProperty(
      "disabled",
    );
  });
});
