import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ConfirmAction from "./ConfirmAction.vue";

describe("ConfirmAction", () => {
  it("requires explicit confirmation before emitting a destructive action", async () => {
    const wrapper = mount(ConfirmAction, {
      props: { prompt: "Delete this team?" },
    });

    await wrapper.get("button").trigger("click");

    expect(wrapper.emitted("confirm")).toBeUndefined();
    expect(wrapper.text()).toContain("Delete this team?");

    await wrapper.findAll("button")[0].trigger("click");

    expect(wrapper.emitted("confirm")).toHaveLength(1);
  });
});
