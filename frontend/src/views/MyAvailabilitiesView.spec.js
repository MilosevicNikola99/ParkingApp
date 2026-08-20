import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const availabilityService = vi.hoisted(() => ({
  cancelAvailability: vi.fn(),
  createAvailability: vi.fn(),
  listMyAvailabilities: vi.fn(),
}));
const parkingSpotService = vi.hoisted(() => ({
  listMyActiveParkingSpots: vi.fn(),
}));

vi.mock("@/services/availabilityService", () => availabilityService);
vi.mock("@/services/parkingSpotService", () => parkingSpotService);
vi.mock("@/composables/useAuthenticatedPage", () => ({
  useAuthenticatedPage: () => ({
    currentUser: ref({ id: 1, first_name: "Owner", last_name: "User", role: "parking_owner" }),
    handleLogout: vi.fn(),
  }),
}));

import MyAvailabilitiesView from "./MyAvailabilitiesView.vue";

const AppLayoutStub = { template: "<div><slot /></div>" };
const activeSpot = {
  id: 5,
  code: "QA-SPOT-01",
  location: "Garage level 1",
  description: null,
  owner_id: 1,
  is_active: true,
};

function mountView() {
  return mount(MyAvailabilitiesView, {
    global: { stubs: { AppLayout: AppLayoutStub } },
  });
}

async function fillTimes(wrapper, start = "2026-08-10T10:00", end = "2026-08-10T12:00") {
  await wrapper.get('input[name="availability-start"]').setValue(start);
  await wrapper.get('input[name="availability-end"]').setValue(end);
}

describe("MyAvailabilitiesView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    availabilityService.listMyAvailabilities.mockResolvedValue([]);
    parkingSpotService.listMyActiveParkingSpots.mockResolvedValue([activeSpot]);
  });

  it("loads owned active parking spots on mount", async () => {
    mountView();
    await flushPromises();

    expect(parkingSpotService.listMyActiveParkingSpots).toHaveBeenCalledOnce();
    expect(availabilityService.listMyAvailabilities).toHaveBeenCalledOnce();
  });

  it("shows one owned spot as a read-only summary without a raw ID input", async () => {
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("Your parking spot");
    expect(wrapper.text()).toContain("QA-SPOT-01 - Garage level 1");
    expect(wrapper.find('input[name="parking-spot-id"]').exists()).toBe(false);
    expect(wrapper.find('select[name="parking-spot"]').exists()).toBe(false);
  });

  it("shows an owner-scoped selector when multiple active spots exist", async () => {
    parkingSpotService.listMyActiveParkingSpots.mockResolvedValue([
      activeSpot,
      { ...activeSpot, id: 6, code: "QA-SPOT-02", location: "Garage level 2" },
    ]);

    const wrapper = mountView();
    await flushPromises();

    const select = wrapper.get('select[name="parking-spot"]');
    expect(select.text()).toContain("QA-SPOT-01 - Garage level 1");
    expect(select.text()).toContain("QA-SPOT-02 - Garage level 2");
    expect(wrapper.find('input[name="parking-spot-id"]').exists()).toBe(false);
  });

  it("disables publishing and shows administrator guidance when no active spot exists", async () => {
    parkingSpotService.listMyActiveParkingSpots.mockResolvedValue([]);

    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain(
      "You do not have an active parking spot assigned. Contact an administrator.",
    );
    expect(wrapper.get("fieldset").attributes()).toHaveProperty("disabled");
    expect(wrapper.get('button[type="submit"]').attributes()).toHaveProperty("disabled");
  });

  it("disables publishing and shows a helpful error when owned spots cannot load", async () => {
    parkingSpotService.listMyActiveParkingSpots.mockRejectedValue(new Error("network"));

    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain(
      "Your assigned parking spots could not be loaded. Try again or contact an administrator.",
    );
    expect(wrapper.get("fieldset").attributes()).toHaveProperty("disabled");
    expect(wrapper.get('button[type="submit"]').attributes()).toHaveProperty("disabled");
  });

  it("validates start and end times without asking for a parking spot ID", async () => {
    const wrapper = mountView();
    await flushPromises();

    await fillTimes(wrapper, "2026-08-10T10:00", "2026-08-10T09:00");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.text()).toContain("End time must be after start time.");
    expect(wrapper.text()).not.toContain("Enter a valid parking spot ID.");
    expect(availabilityService.createAvailability).not.toHaveBeenCalled();
  });

  it("submits the auto-selected spot ID and adds the published availability to the list", async () => {
    availabilityService.createAvailability.mockResolvedValue({
      id: 10,
      parking_spot_id: 5,
      owner_id: 1,
      status: "open",
      start_at: "2026-08-10T10:00:00.000Z",
      end_at: "2026-08-10T12:00:00.000Z",
      priority_until: null,
      note: "Morning",
    });
    const wrapper = mountView();
    await flushPromises();

    await fillTimes(wrapper);
    await wrapper.get('textarea[name="availability-note"]').setValue("  Morning  ");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(availabilityService.createAvailability).toHaveBeenCalledWith({
      parking_spot_id: 5,
      start_at: new Date("2026-08-10T10:00").toISOString(),
      end_at: new Date("2026-08-10T12:00").toISOString(),
      note: "Morning",
    });
    expect(wrapper.text()).toContain("Parking offer published for QA-SPOT-01 - Garage level 1.");
    expect(wrapper.get('[aria-label="My published parking offers"]').text()).toContain("Morning");
  });

  it("submits the spot selected from multiple owned spots", async () => {
    parkingSpotService.listMyActiveParkingSpots.mockResolvedValue([
      activeSpot,
      { ...activeSpot, id: 6, code: "QA-SPOT-02", location: "Garage level 2" },
    ]);
    availabilityService.createAvailability.mockResolvedValue({
      id: 11,
      parking_spot_id: 6,
      owner_id: 1,
      status: "open",
      start_at: "2026-08-10T10:00:00.000Z",
      end_at: "2026-08-10T12:00:00.000Z",
      priority_until: null,
      note: null,
    });
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('select[name="parking-spot"]').setValue("6");
    await fillTimes(wrapper);
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(availabilityService.createAvailability).toHaveBeenCalledWith(
      expect.objectContaining({ parking_spot_id: 6 }),
    );
  });
});
