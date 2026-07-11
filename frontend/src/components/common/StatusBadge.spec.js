import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import StatusBadge from "./StatusBadge.vue";

describe("StatusBadge", () => {
  it("renders a readable label and lifecycle-specific class", () => {
    const wrapper = mount(StatusBadge, {
      props: { status: "current_active" },
    });

    expect(wrapper.text()).toBe("current active");
    expect(wrapper.classes()).toContain("status-badge--current-active");
  });
});
