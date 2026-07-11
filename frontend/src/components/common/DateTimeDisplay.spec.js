import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import DateTimeDisplay from "./DateTimeDisplay.vue";

describe("DateTimeDisplay", () => {
  it("renders a semantic time element for a valid value", () => {
    const value = "2026-06-04T12:00:00Z";
    const wrapper = mount(DateTimeDisplay, { props: { value } });

    expect(wrapper.element.tagName).toBe("TIME");
    expect(wrapper.attributes("datetime")).toBe(value);
    expect(wrapper.text()).not.toBe("Invalid date");
  });

  it("renders stable fallback text for missing and invalid values", async () => {
    const wrapper = mount(DateTimeDisplay);
    expect(wrapper.text()).toBe("Not set");

    await wrapper.setProps({ value: "not-a-date" });
    expect(wrapper.text()).toBe("Invalid date");
  });
});
